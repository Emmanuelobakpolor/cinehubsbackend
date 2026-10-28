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


@shared_task
def package_movie_stream(movie_id):
    """Build the encrypted HLS stream for a movie (see movies.packaging)."""
    from .packaging import package_movie

    try:
        stream = package_movie(movie_id)
    except Exception as exc:
        return f'packaging failed for movie {movie_id}: {exc.__class__.__name__}'
    return f'movie {movie_id} packaged ({len(stream.variants)} renditions)'
