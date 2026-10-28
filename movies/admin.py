from django.contrib import admin
from django.utils import timezone
from .models import (
    Category, Movie, WatchHistory, SavedMovie, UserMovieAccess, MovieDownload,
    MovieStream, PlaybackSession,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['title', 'views_count', 'is_trending', 'is_featured', 'created_at']
    list_filter = ['categories', 'is_trending', 'is_featured']
    search_fields = ['title', 'cast']
    list_editable = ['is_trending', 'is_featured']


@admin.register(MovieDownload)
class MovieDownloadAdmin(admin.ModelAdmin):
    list_display = ['user', 'movie', 'amount_paid', 'payment_reference', 'paid_at']
    search_fields = ['user__email', 'movie__title']
    readonly_fields = ['paid_at']


@admin.register(WatchHistory)
class WatchHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'movie', 'watched_at', 'watch_duration']


@admin.register(SavedMovie)
class SavedMovieAdmin(admin.ModelAdmin):
    list_display = ['user', 'movie', 'saved_at']


@admin.register(UserMovieAccess)
class UserMovieAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'movie', 'watched_at', 'expires_at', 'is_active']
    list_filter = ['is_active']
    search_fields = ['user__email', 'movie__title']
    readonly_fields = ['watched_at']


@admin.register(MovieStream)
class MovieStreamAdmin(admin.ModelAdmin):
    list_display = ['movie', 'status', 'packaged_at', 'drm_playback_id', 'updated_at']
    list_filter = ['status']
    search_fields = ['movie__title']
    # The key and playlists are never shown or edited here.
    fields = ['movie', 'status', 'drm_playback_id', 'duration', 'packaged_at', 'error']
    readonly_fields = ['movie', 'status', 'duration', 'packaged_at', 'error']
    actions = ['queue_packaging']

    @admin.action(description='Re-package selected movies (encrypted HLS)')
    def queue_packaging(self, request, queryset):
        from .tasks import package_movie_stream
        for stream in queryset:
            package_movie_stream.delay(stream.movie_id)
        self.message_user(request, f'Queued {queryset.count()} movie(s) for packaging.')


@admin.register(PlaybackSession)
class PlaybackSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'movie', 'mode', 'created_at', 'expires_at', 'revoked_at', 'ip_address']
    list_filter = ['mode']
    search_fields = ['user__email', 'movie__title']
    exclude = ['token_hash']
    readonly_fields = ['user', 'movie', 'mode', 'created_at', 'expires_at', 'revoked_at', 'ip_address', 'user_agent']
    actions = ['revoke']

    @admin.action(description='Revoke selected playback sessions')
    def revoke(self, request, queryset):
        count = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f'Revoked {count} session(s).')
