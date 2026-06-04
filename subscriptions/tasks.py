from celery import shared_task
from django.utils import timezone


@shared_task
def expire_subscriptions():
    """Mark subscriptions as EXPIRED when their end_date has passed."""
    from .models import UserSubscription
    updated = UserSubscription.objects.filter(
        status='ACTIVE',
        end_date__lte=timezone.now(),
    ).update(status='EXPIRED')
    return f'Expired {updated} subscription(s)'
