from django.core.management.base import BaseCommand

from movies.models import Movie
from movies.packaging import protect_source
from movies.playback import cloudinary_video_source


class Command(BaseCommand):
    help = (
        "Move original movie files to Cloudinary 'authenticated' delivery so their "
        'permanent public URLs stop working. Only movies with a ready stream are '
        'touched. Dry run unless --apply is given.'
    )

    def add_arguments(self, parser):
        parser.add_argument('movie_ids', nargs='*', type=int, help='Limit to these movies')
        parser.add_argument('--apply', action='store_true', help='Actually change Cloudinary')

    def handle(self, *args, **options):
        movies = Movie.objects.filter(stream__status='READY')
        if options['movie_ids']:
            movies = movies.filter(id__in=options['movie_ids'])

        for movie in movies:
            source = cloudinary_video_source(movie)
            if not source:
                self.stdout.write(f'skip {movie.id} "{movie.title}": not a Cloudinary video')
                continue
            if source[0] == 'authenticated':
                self.stdout.write(f'skip {movie.id} "{movie.title}": already protected')
                continue
            if not options['apply']:
                self.stdout.write(f'would protect {movie.id} "{movie.title}"')
                continue
            try:
                protect_source(movie)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'{movie.id} failed: {exc}'))
                continue
            self.stdout.write(self.style.SUCCESS(f'protected {movie.id} "{movie.title}"'))

        if not options['apply']:
            self.stdout.write('Dry run - re-run with --apply to make these changes.')
