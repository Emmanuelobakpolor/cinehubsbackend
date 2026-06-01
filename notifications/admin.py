from django.contrib import admin
from .models import Notification, DeviceToken


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'notification_type', 'recipient', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'created_at']
