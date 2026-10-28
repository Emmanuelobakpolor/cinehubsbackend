from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='public_name', read_only=True)
    movie_title = serializers.CharField(source='movie.title', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'user', 'username', 'movie', 'movie_title', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['user', 'movie', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class AdminReviewSerializer(serializers.ModelSerializer):
    """Admin view of reviews: can create reviews under any name and edit any review."""
    username = serializers.CharField(source='public_name', read_only=True)
    movie_title = serializers.CharField(source='movie.title', read_only=True)
    is_custom = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'movie', 'movie_title', 'display_name', 'username',
            'rating', 'comment', 'is_custom', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_is_custom(self, obj):
        return obj.user_id is None

    def validate_display_name(self, value):
        return value.strip()

    def validate(self, attrs):
        is_new = self.instance is None
        is_custom = is_new or self.instance.user_id is None
        name = attrs.get('display_name', '' if is_new else self.instance.display_name)
        if is_custom and not name:
            raise serializers.ValidationError({'display_name': 'A username is required.'})
        return attrs
