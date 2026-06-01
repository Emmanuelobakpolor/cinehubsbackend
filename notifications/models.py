from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_CHOICES = (
        ('BROADCAST', 'Broadcast'),
        ('PERSONAL', 'Personal'),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        blank=True, null=True,
        help_text='Null means broadcast to all users'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='PERSONAL')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.recipient:
            return f'{self.title} -> {self.recipient.email}'
        return f'{self.title} (Broadcast)'


class DeviceToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.TextField()
    platform = models.CharField(max_length=20, choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')], default='android')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'token')

    def __str__(self):
        return f'{self.user.email} - {self.platform}'
