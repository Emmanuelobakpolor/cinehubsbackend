from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'is_email_verified', 'is_staff']
    list_filter = ['is_email_verified', 'is_staff']
    search_fields = ['email', 'username', 'phone_number']
    ordering = ['-created_at']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile', {'fields': ('phone_number', 'profile_picture', 'bio')}),
        ('Verification', {'fields': ('is_email_verified',)}),
    )
