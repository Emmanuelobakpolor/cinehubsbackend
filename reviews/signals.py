from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Review


@receiver(post_save, sender=Review)
def notify_admin_new_review(sender, instance, created, **kwargs):
    """Create an ADMIN notification when a user submits a new rating/review."""
    if not created:
        return  # Only fire on creation, not on edits

    from notifications.models import Notification

    stars = '★' * instance.rating + '☆' * (5 - instance.rating)
    username = instance.user.get_full_name() or instance.user.email
    comment_preview = (
        f' — "{instance.comment[:80]}…"' if len(instance.comment) > 80
        else (f' — "{instance.comment}"' if instance.comment else '')
    )

    Notification.objects.create(
        recipient=None,
        notification_type='ADMIN',
        title='New Rating Received',
        message=(
            f'{username} rated "{instance.movie.title}" '
            f'{stars} ({instance.rating}/5){comment_preview}'
        ),
    )
