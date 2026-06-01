from django.contrib import admin
from .models import Category, Movie, WatchHistory, SavedMovie, UserMovieAccess, MovieDownload


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
