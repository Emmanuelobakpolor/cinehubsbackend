import random
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    is_email_verified = models.BooleanField(default=False)

    email_otp = models.CharField(max_length=6, blank=True, null=True)
    email_otp_expiry = models.DateTimeField(blank=True, null=True)

    password_reset_otp = models.CharField(max_length=6, blank=True, null=True)
    password_reset_otp_expiry = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    def generate_otp(self):
        return str(random.randint(100000, 999999))

    def set_email_otp(self):
        self.email_otp = self.generate_otp()
        self.email_otp_expiry = timezone.now() + timedelta(minutes=10)
        self.save()
        return self.email_otp

    def set_password_reset_otp(self):
        self.password_reset_otp = self.generate_otp()
        self.password_reset_otp_expiry = timezone.now() + timedelta(minutes=10)
        self.save()
        return self.password_reset_otp
