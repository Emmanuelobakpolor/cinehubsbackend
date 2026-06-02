from datetime import timedelta

from rest_framework import serializers
from .models import Category, Movie, WatchHistory, SavedMovie, MovieDownload, UserMovieAccess


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class MovieSerializer(serializers.ModelSerializer):
    category_names = serializers.SerializerMethodField(read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = Movie
        fields = '__all__'
        read_only_fields = ['uploaded_by', 'views_count', 'created_at']

    def get_category_names(self, obj):
        return list(obj.categories.values_list('name', flat=True))

    def create(self, validated_data):
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)


class WatchHistorySerializer(serializers.ModelSerializer):
    movie_title = serializers.CharField(source='movie.title', read_only=True)
    movie_thumbnail = serializers.URLField(source='movie.thumbnail', read_only=True)
    # expires_at from UserMovieAccess — more accurate than watched_at + 10 days
    # because watched_at resets on every update (auto_now=True).
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = WatchHistory
        fields = ['id', 'movie', 'movie_title', 'movie_thumbnail', 'watched_at', 'watch_duration', 'expires_at']
        read_only_fields = ['watched_at']

    def get_expires_at(self, obj):
        # Don't filter by is_active — we want to show the expiry date even for
        # expired records so Flutter can display "Expired" with the correct date.
        access = UserMovieAccess.objects.filter(
            user=obj.user, movie=obj.movie,
        ).order_by('-watched_at').first()
        if access:
            return access.expires_at.isoformat()
        # Fallback: no access record yet (edge case before first play completes).
        # Return 10 days from the watch history timestamp so something shows.
        return (obj.watched_at + timedelta(days=10)).isoformat()


class SavedMovieSerializer(serializers.ModelSerializer):
    movie_id = serializers.IntegerField(source='movie.id', read_only=True)
    movie_title = serializers.CharField(source='movie.title', read_only=True)
    movie_thumbnail = serializers.URLField(source='movie.thumbnail', read_only=True)
    movie_synopsis = serializers.CharField(source='movie.synopsis', read_only=True)
    movie_rating = serializers.CharField(source='movie.rating', read_only=True)
    movie_release_year = serializers.CharField(source='movie.release_year', read_only=True)
    movie_runtime = serializers.CharField(source='movie.runtime', read_only=True)
    movie_categories = serializers.SerializerMethodField()

    class Meta:
        model = SavedMovie
        fields = [
            'id', 'movie', 'movie_id', 'movie_title', 'movie_thumbnail',
            'movie_synopsis', 'movie_rating', 'movie_release_year',
            'movie_runtime', 'movie_categories', 'saved_at',
        ]
        read_only_fields = ['saved_at']

    def get_movie_categories(self, obj):
        return list(obj.movie.categories.values_list('name', flat=True))


class MovieDownloadSerializer(serializers.ModelSerializer):
    movie_title = serializers.CharField(source='movie.title', read_only=True)
    movie_thumbnail = serializers.URLField(source='movie.thumbnail', read_only=True)
    movie_file = serializers.URLField(source='movie.movie_file', read_only=True)

    class Meta:
        model = MovieDownload
        fields = ['id', 'movie', 'movie_title', 'movie_thumbnail', 'movie_file', 'amount_paid', 'paid_at']
        read_only_fields = ['paid_at']
