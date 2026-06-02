from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(choices=['user', 'admin'], default='user', required=False)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', '').strip()
        role = validated_data.pop('role', 'user')
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        is_admin = role == 'admin'
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            phone_number=validated_data.get('phone_number', ''),
            password=validated_data['password'],
            first_name=first_name,
            last_name=last_name,
            is_staff=is_admin,
            is_email_verified=is_admin,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        if not user.is_active:
            raise serializers.ValidationError('Account is disabled.')
        data['user'] = user
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    # profile_picture is now a URLField (Cloudinary URL) — expose as plain string.
    profile_picture = serializers.CharField(allow_null=True, allow_blank=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'username', 'email', 'phone_number',
            'profile_picture', 'bio',
            'is_email_verified',
            'created_at',
        ]
        read_only_fields = ['id', 'email', 'is_email_verified', 'created_at']

    def get_full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name if name else obj.username

    def update(self, instance, validated_data):
        full_name = self.initial_data.get('full_name', '')
        if full_name:
            name_parts = full_name.strip().split(' ', 1)
            instance.first_name = name_parts[0]
            instance.last_name = name_parts[1] if len(name_parts) > 1 else ''
        return super().update(instance, validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=6)


class VerifyEmailSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)
