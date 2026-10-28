from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['public_name', 'user', 'movie', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['display_name', 'user__username', 'user__email', 'movie__title', 'comment']
    raw_id_fields = ['user']
