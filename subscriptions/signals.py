from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserSubscription


@receiver(post_save, sender=UserSubscription)
def notify_admin_new_subscription(sender, instance, created, **kwargs):
    """Create an ADMIN notification when a user activates a subscription."""
    if not created:
        return  # Only fire on new subscriptions, not status updates

    from notifications.models import Notification

    username = instance.user.get_full_name() or instance.user.email
    plan_name = instance.plan.get_name_display()
    price = instance.plan.price

    Notification.objects.create(
        recipient=None,
        notification_type='ADMIN',
        title='New Subscription',
        message=(
            f'{username} subscribed to the {plan_name} plan '
            f'(₦{price:,.2f}/month)'
        ),
    )
