from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_price = serializers.DecimalField(source='plan.price', max_digits=10, decimal_places=2, read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = '__all__'
        read_only_fields = ['user', 'status', 'start_date', 'end_date', 'created_at']


class AdminSubscriberSerializer(serializers.ModelSerializer):
    """Full subscriber info for the admin panel."""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ['id', 'username', 'email', 'plan_name', 'status', 'is_active', 'start_date', 'end_date']
