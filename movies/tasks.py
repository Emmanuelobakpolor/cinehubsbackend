from celery import shared_task
from django.utils import timezone

from .models import UserMovieAccess


@shared_task
def deactivate_expired_movie_access():
    expired = UserMovieAccess.objects.filter(
        expires_at__lte=timezone.now(),
        is_active=True,
    )
    count = expired.update(is_active=False)
    return f'{count} access record(s) expired and deactivated'
