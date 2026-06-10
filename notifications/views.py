import json
import logging
import threading

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q
from django.conf import settings

from .models import Notification, DeviceToken
from .serializers import NotificationSerializer, BroadcastSerializer, DeviceTokenSerializer
from users.models import User

logger = logging.getLogger(__name__)


def _init_firebase():
    """Initialise the firebase-admin SDK once. Returns True if ready."""
    sa_json = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
    if not sa_json:
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred)
        return True
    except Exception as e:
        logger.error('Firebase init error: %s', e)
        return False


def _send_fcm(title: str, body: str, audience: str, tokens: list):
    """Send a multicast FCM notification. Called in a background thread."""
    if not tokens:
        return
    if not _init_firebase():
        return
    try:
        from firebase_admin import messaging
        msg = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=body),
            data={'type': 'BROADCAST', 'audience': audience},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='cinehubs_broadcasts',
                    default_sound=True,
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default', badge=1),
                ),
            ),
        )
        # FCM multicast is capped at 500 tokens per call
        for i in range(0, len(tokens), 500):
            batch = tokens[i:i + 500]
            msg.tokens = batch
            resp = messaging.send_each_for_multicast(msg)
            # Remove stale tokens so we don't keep sending to uninstalled apps
            if resp.failure_count > 0:
                stale = [
                    batch[j] for j, r in enumerate(resp.responses)
                    if not r.success
                ]
                if stale:
                    DeviceToken.objects.filter(token__in=stale).delete()
                    logger.info('Removed %d stale FCM tokens', len(stale))
    except Exception as e:
        logger.error('FCM send error: %s', e)


def _tokens_for_audience(audience: str) -> list:
    """Return device tokens for the target audience."""
    from django.utils import timezone
    from subscriptions.models import UserSubscription

    if audience == 'ALL':
        user_ids = User.objects.filter(is_staff=False).values_list('id', flat=True)
    elif audience == 'PREMIUM':
        user_ids = UserSubscription.objects.filter(
            plan__name='PREMIUM', status='ACTIVE', end_date__gt=timezone.now()
        ).values_list('user_id', flat=True)
    elif audience == 'BASIC':
        user_ids = UserSubscription.objects.filter(
            plan__name='BASIC', status='ACTIVE', end_date__gt=timezone.now()
        ).values_list('user_id', flat=True)
    else:
        user_ids = []

    return list(
        DeviceToken.objects.filter(user_id__in=user_ids).values_list('token', flat=True)
    )


class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from subscriptions.models import UserSubscription
        from django.utils import timezone

        active_sub = (
            UserSubscription.objects
            .filter(user=request.user, status='ACTIVE', end_date__gt=timezone.now())
            .select_related('plan')
            .order_by('-start_date')
            .first()
        )
        user_plan = active_sub.plan.name if active_sub else None

        audience_filter = ['ALL']
        if user_plan:
            audience_filter.append(user_plan)

        notifications = Notification.objects.filter(
            Q(recipient=request.user) |
            Q(notification_type='BROADCAST', recipient__isnull=True, target_audience__in=audience_filter)
        ).distinct().order_by('-created_at')

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    def patch(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
            notif.is_read = True
            notif.save()
            return Response({'message': 'Marked as read.'})
        except Notification.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class BroadcastView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        broadcasts = (
            Notification.objects
            .filter(notification_type='BROADCAST', recipient__isnull=True)
            .order_by('-created_at')
        )
        serializer = NotificationSerializer(broadcasts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = BroadcastSerializer(data=request.data)
        if serializer.is_valid():
            title = serializer.validated_data['title']
            message = serializer.validated_data['message']
            audience = serializer.validated_data.get('target_audience', 'ALL')

            Notification.objects.create(
                recipient=None,
                title=title,
                message=message,
                notification_type='BROADCAST',
                target_audience=audience,
            )

            # Send FCM push in background so the API response isn't delayed
            tokens = _tokens_for_audience(audience)
            threading.Thread(
                target=_send_fcm,
                args=(title, message, audience, tokens),
                daemon=True,
            ).start()

            return Response({'message': 'Broadcast sent.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterDeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        if serializer.is_valid():
            DeviceToken.objects.update_or_create(
                user=request.user,
                token=serializer.validated_data['token'],
                defaults={'platform': serializer.validated_data.get('platform', 'android')},
            )
            return Response({'message': 'Device token registered.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminNotificationsView(APIView):
    """
    GET  /api/notifications/admin/          — list latest 50 ADMIN notifications
    PATCH /api/notifications/admin/<pk>/read/ — mark one as read
    POST  /api/notifications/admin/read-all/ — mark all as read
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        notifications = (
            Notification.objects
            .filter(notification_type='ADMIN')
            .order_by('-created_at')[:50]
        )
        serializer = NotificationSerializer(notifications, many=True)
        unread = Notification.objects.filter(
            notification_type='ADMIN', is_read=False
        ).count()
        return Response({'results': serializer.data, 'unread_count': unread})

    def patch(self, request, pk=None):
        if pk is None:
            return Response({'error': 'pk required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            notif = Notification.objects.get(pk=pk, notification_type='ADMIN')
            notif.is_read = True
            notif.save()
            return Response({'message': 'Marked as read.'})
        except Notification.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        """Mark all ADMIN notifications as read."""
        Notification.objects.filter(notification_type='ADMIN', is_read=False).update(is_read=True)
        return Response({'message': 'All marked as read.'})


class AdminAnalyticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from subscriptions.models import UserSubscription, SubscriptionPlan
        from payments.models import Payment
        from django.db.models import Sum

        total_users = User.objects.count()
        basic_plan = SubscriptionPlan.objects.filter(name='BASIC').first()
        premium_plan = SubscriptionPlan.objects.filter(name='PREMIUM').first()

        basic_subs = UserSubscription.objects.filter(plan=basic_plan, status='ACTIVE').count() if basic_plan else 0
        premium_subs = UserSubscription.objects.filter(plan=premium_plan, status='ACTIVE').count() if premium_plan else 0

        total_revenue = Payment.objects.filter(status='SUCCESS').aggregate(
            total=Sum('amount')
        )['total'] or 0

        return Response({
            'total_users': total_users,
            'basic_subscribers': basic_subs,
            'premium_subscribers': premium_subs,
            'total_revenue': total_revenue,
        })
