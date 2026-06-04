from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import SubscriptionPlan, UserSubscription
from .serializers import SubscriptionPlanSerializer, UserSubscriptionSerializer, AdminSubscriberSerializer


class SubscriptionPlanListView(generics.ListCreateAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticated()]


class SubscriptionPlanDetailView(generics.RetrieveUpdateAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAdminUser]


class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscriptions = UserSubscription.objects.filter(user=request.user).order_by('-created_at')
        serializer = UserSubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data)


class AllSubscribersView(generics.ListAPIView):
    """
    GET /api/subscriptions/subscribers/
    Admin-only list of all subscriptions with user info.
    Supports ?plan=BASIC|PREMIUM and ?status=ACTIVE|EXPIRED|CANCELLED filters.
    """
    serializer_class = AdminSubscriberSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = UserSubscription.objects.select_related('user', 'plan').order_by('-start_date')
        plan = self.request.query_params.get('plan')
        status = self.request.query_params.get('status')
        if plan:
            qs = qs.filter(plan__name=plan.upper())
        if status:
            qs = qs.filter(status=status.upper())
        return qs

    def list(self, request, *args, **kwargs):
        from django.utils import timezone
        # Counts always reflect ALL subscriptions regardless of active filter
        all_qs = UserSubscription.objects.select_related('user', 'plan')
        total = all_qs.count()
        basic = all_qs.filter(plan__name='BASIC').count()
        premium = all_qs.filter(plan__name='PREMIUM').count()
        active = all_qs.filter(status='ACTIVE', end_date__gt=timezone.now()).count()
        # Results respect the requested filter
        filtered_qs = self.get_queryset()
        serializer = self.get_serializer(filtered_qs, many=True)
        return Response({
            'counts': {
                'total': total,
                'basic': basic,
                'premium': premium,
                'active': active,
            },
            'results': serializer.data,
        })
