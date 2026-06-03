from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import Notification, DeviceToken
from .serializers import NotificationSerializer, BroadcastSerializer, DeviceTokenSerializer
from users.models import User


class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(
            recipient=request.user
        ).order_by('-created_at') | Notification.objects.filter(
            notification_type='BROADCAST',
            recipient__isnull=True,
        ).order_by('-created_at')
        notifications = notifications.distinct().order_by('-created_at')
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

    def post(self, request):
        serializer = BroadcastSerializer(data=request.data)
        if serializer.is_valid():
            Notification.objects.create(
                recipient=None,
                title=serializer.validated_data['title'],
                message=serializer.validated_data['message'],
                notification_type='BROADCAST',
            )
            return Response({'message': 'Broadcast sent to all users.'}, status=status.HTTP_201_CREATED)
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
