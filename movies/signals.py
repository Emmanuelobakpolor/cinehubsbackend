import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Movie, MovieDownload, MovieStream
from .playback import parse_cloudinary_video

logger = logging.getLogger(__name__)


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


def _source_key(url):
    """Identity of the underlying file; protecting a source changes its URL but not this."""
    source = parse_cloudinary_video(url)
    return source[1] if source else (url or '')


@receiver(pre_save, sender=Movie)
def remember_old_movie_file(sender, instance, **kwargs):
    instance._old_movie_file = (
        Movie.objects.filter(pk=instance.pk).values_list('movie_file', flat=True).first()
        if instance.pk else None
    )


@receiver(post_save, sender=Movie)
def repackage_on_new_movie_file(sender, instance, created, **kwargs):
    """A new movie file makes the old encrypted stream stale; rebuild it if enabled."""
    if not instance.movie_file:
        return
    if not created and _source_key(getattr(instance, '_old_movie_file', None)) == _source_key(instance.movie_file):
        return

    MovieStream.objects.filter(movie=instance).update(status='PENDING')
    if not settings.HLS_AUTO_PACKAGE:
        return

    def enqueue():
        from .tasks import package_movie_stream
        try:
            package_movie_stream.delay(instance.pk)
        except Exception:
            # Broker down: the movie still saves; package later with `manage.py package_movies`.
            logger.warning('Could not queue HLS packaging for movie %s', instance.pk, exc_info=True)

    transaction.on_commit(enqueue)
