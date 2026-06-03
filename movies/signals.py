from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MovieDownload


@receiver(post_save, sender=MovieDownload)
def notify_admin_movie_purchase(sender, instance, created, **kwargs):
    """Create an ADMIN notification when a user pays for a movie."""
    if not created:
        return  # Only fire on new purchases, not updates

    from notifications.models import Notification

    username = instance.user.get_full_name() or instance.user.email
    amount = instance.amount_paid

    # Premium users have amount_paid=0 and reference='PREMIUM' — skip those
    if str(instance.payment_reference).upper() == 'PREMIUM' or float(amount) == 0:
        return

    Notification.objects.create(
        recipient=None,
        notification_type='ADMIN',
        title='Movie Purchase',
        message=(
            f'{username} paid ₦{float(amount):,.2f} '
            f'for "{instance.movie.title}"'
        ),
    )
