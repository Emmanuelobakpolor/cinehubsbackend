from django.core.management.base import BaseCommand, CommandError

from movies.models import Movie
from movies.packaging import package_movie
from movies.tasks import package_movie_stream


class Command(BaseCommand):
    help = 'Build the encrypted HLS stream for movies (needs ffmpeg/ffprobe).'

    def add_arguments(self, parser):
        parser.add_argument('movie_ids', nargs='*', type=int, help='Movies to package')
        parser.add_argument('--missing', action='store_true', help='Every movie without a ready stream')
        parser.add_argument('--queue', action='store_true', help='Queue on the Celery worker instead of running here')

    def handle(self, *args, **options):
        if options['missing']:
            ids = list(
                Movie.objects.exclude(stream__status='READY').exclude(movie_file='')
                .values_list('id', flat=True)
            )
        else:
            ids = options['movie_ids']
        if not ids:
            raise CommandError('Pass movie ids or --missing.')

        for movie_id in ids:
            if options['queue']:
                package_movie_stream.delay(movie_id)
                self.stdout.write(f'Queued movie {movie_id}')
                continue
            try:
                stream = package_movie(movie_id)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'Movie {movie_id} failed: {exc}'))
                continue
            self.stdout.write(self.style.SUCCESS(
                f'Movie {movie_id} packaged ({len(stream.variants)} renditions)'
            ))
