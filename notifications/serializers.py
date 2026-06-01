from rest_framework import serializers
from .models import Notification, DeviceToken


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['created_at']


class BroadcastSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'platform', 'created_at']
        read_only_fields = ['created_at']
