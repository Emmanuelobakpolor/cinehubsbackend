from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Movie(models.Model):
    title = models.CharField(max_length=255)
    synopsis = models.TextField()
    thumbnail = models.URLField(max_length=500)
    trailer_url = models.URLField(blank=True, null=True)
    thriller_clip = models.URLField(max_length=500, blank=True, null=True, help_text='Short 30-second preview clip')
    movie_file = models.URLField(max_length=500)
    categories = models.ManyToManyField(Category, related_name='movies', blank=True)
    release_year = models.CharField(max_length=4, blank=True, default='')
    runtime = models.CharField(max_length=20, blank=True, default='')
    rating = models.CharField(max_length=10, blank=True, default='')
    director = models.CharField(max_length=150, blank=True, default='')
    cast = models.TextField(help_text='Comma-separated cast names', blank=True, default='')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    views_count = models.IntegerField(default=0)
    is_trending = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class MovieDownload(models.Model):
    """Tracks a Basic user's per-movie download payment."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='movie_downloads',
    )
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='downloads')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    # payment_reference stored here once a real gateway is wired
    payment_reference = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        unique_together = ('user', 'movie')

    def __str__(self):
        return f'{self.user.email} → {self.movie.title} (₦{self.amount_paid})'


class WatchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watch_history')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='watched_by')
    watched_at = models.DateTimeField(auto_now=True)
    watch_duration = models.IntegerField(default=0, help_text='Seconds watched')

    class Meta:
        unique_together = ('user', 'movie')
        verbose_name_plural = 'Watch Histories'

    def __str__(self):
        return f'{self.user.email} watched {self.movie.title}'


class SavedMovie(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_movies')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'movie')

    def __str__(self):
        return f'{self.user.email} saved {self.movie.title}'


class UserMovieAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='movie_access',
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='user_access',
    )
    watched_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'movie')

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=10)
        super().save(*args, **kwargs)

    @property
    def has_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f'{self.user.email} → {self.movie.title} (expires {self.expires_at.date()})'


class MovieStream(models.Model):
    """
    The protected streaming version of a movie: an AES-128 encrypted HLS ladder
    built from Movie.movie_file by movies.packaging, and/or a DRM playback ID
    from a commercial provider (see movies.drm).

    Segments are stored encrypted on the CDN; the key never leaves the backend
    except through the token-gated key endpoint (movies.views.StreamKeyView).
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('READY', 'Ready'),
        ('FAILED', 'Failed'),
    )
    movie = models.OneToOneField(Movie, on_delete=models.CASCADE, related_name='stream')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    # Random folder name for the segments, so their CDN paths can't be guessed.
    package_id = models.CharField(max_length=64, blank=True, default='')
    key = models.BinaryField(max_length=16, blank=True, null=True, editable=False)
    # [{"height": 720, "bandwidth": 3000000, "width": 1280, "playlist": "<m3u8 text>"}]
    # Each playlist has a {{KEY_URI}} placeholder filled in per playback session.
    variants = models.JSONField(default=list, blank=True)
    duration = models.FloatField(default=0)
    error = models.TextField(blank=True, default='')
    # Playback ID at the DRM provider (e.g. a Mux playback ID with a DRM policy).
    # When set and DRM_PROVIDER is configured, playback uses DRM instead of AES HLS.
    drm_playback_id = models.CharField(max_length=128, blank=True, default='')
    packaged_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_ready(self):
        return self.status == 'READY' and bool(self.key) and bool(self.variants)

    def __str__(self):
        return f'{self.movie.title} stream ({self.status})'


class PlaybackSession(models.Model):
    """
    A short-lived, revocable authorization to play one movie.

    The raw token is only ever returned to the client once; the database keeps
    its SHA-256 so a leaked database dump can't be replayed as playback URLs.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='playback_sessions',
    )
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='playback_sessions')
    token_hash = models.CharField(max_length=64, unique=True)
    mode = models.CharField(max_length=20, default='hls')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        indexes = [models.Index(fields=['user', 'expires_at'])]

    @property
    def is_valid(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f'{self.user.email} → {self.movie.title} ({self.mode})'
