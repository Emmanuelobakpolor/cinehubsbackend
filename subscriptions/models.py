from django.db import models
from django.conf import settings


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = (
        ('BASIC', 'Basic'),
        ('PREMIUM', 'Premium'),
    )
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Created on demand so a fresh database never breaks checkout.
    DEFAULTS = {
        'BASIC': {
            'price': 1000,
            'duration_days': 1,
            'description': 'Pay per movie - ₦1,000 charged at download time.',
        },
        'PREMIUM': {
            'price': 5500,
            'duration_days': 30,
            'description': 'Unlimited access to all movies for 30 days - ₦5,500 per month.',
        },
    }

    @classmethod
    def get_or_create_by_name(cls, name):
        """Return the plan called [name] ('BASIC' or 'PREMIUM'), creating it with defaults if missing."""
        return cls.objects.get_or_create(name=name, defaults=cls.DEFAULTS[name])

    def __str__(self):
        return f'{self.name} - {self.price}'


class UserSubscription(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.email} - {self.plan.name} ({self.status})'

    @property
    def is_active(self):
        from django.utils import timezone
        return self.status == 'ACTIVE' and self.end_date > timezone.now()
