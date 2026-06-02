from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import User
from .serializers import (
    RegisterSerializer, LoginSerializer, UserProfileSerializer,
    ChangePasswordSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer, VerifyEmailSerializer,
)

# Lazy imports to avoid circular-import issues at module load time
def _get_stats(user):
    from movies.models import WatchHistory, SavedMovie
    from reviews.models import Review
    return {
        'watched_count': WatchHistory.objects.filter(user=user).count(),
        'saved_count': SavedMovie.objects.filter(user=user).count(),
        'reviews_count': Review.objects.filter(user=user).count(),
    }


def _send_email(to_email, subject, body):
    """Send a transactional email via SendGrid. Falls back to console if USE_CONSOLE_EMAIL=True."""
    if settings.USE_CONSOLE_EMAIL:
        print(f"\n[EMAIL] To: {to_email} | Subject: {subject}\n{body}\n")
        return
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )


def send_email_otp(user):
    otp = user.set_email_otp()
    _send_email(
        to_email=user.email,
        subject='Email Verification OTP',
        body=f'Your OTP is: {otp}. It expires in 10 minutes.',
    )



class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            if not user.is_staff:
                from .tasks import send_email_otp_task
                send_email_otp_task.delay(user.pk)
            refresh = RefreshToken.for_user(user)
            message = (
                'Registration successful.'
                if user.is_staff
                else 'Registration successful. Check your email for OTP verification.'
            )
            return Response({
                'message': message,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Login successful',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteUserView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id, is_staff=False)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response({'message': 'User deleted successfully.'}, status=status.HTTP_200_OK)


class DashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from .models import User
        from subscriptions.models import UserSubscription
        total_users = User.objects.filter(is_staff=False).count()
        basic_subs = UserSubscription.objects.filter(
            plan__name='BASIC', status='ACTIVE'
        ).count()
        premium_subs = UserSubscription.objects.filter(
            plan__name='PREMIUM', status='ACTIVE'
        ).count()
        return Response({
            'total_users': total_users,
            'basic_subs': basic_subs,
            'premium_subs': premium_subs,
        })


class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            if not user.is_staff:
                return Response(
                    {'error': 'You do not have admin access.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            refresh = RefreshToken.for_user(user)
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username
            return Response({
                'message': 'Admin login successful',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user': {
                    'email': user.email,
                    'full_name': full_name,
                },
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logged out successfully.'})
        except TokenError:
            return Response({'error': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        data = serializer.data
        data.update(_get_stats(request.user))
        return Response(data)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            data = serializer.data
            data.update(_get_stats(request.user))
            return Response(data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        if 'profile_picture' not in request.FILES:
            return Response({'error': 'No image file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.profile_picture = request.FILES['profile_picture']
        request.user.save(update_fields=['profile_picture'])
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def delete(self, request):
        request.user.profile_picture.delete(save=False)
        request.user.profile_picture = None
        request.user.save(update_fields=['profile_picture'])
        return Response({'message': 'Profile picture removed.'})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({'error': 'Old password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Password changed successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendEmailOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            send_email_otp(request.user)
            return Response({'message': 'OTP sent to your email.'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            otp = serializer.validated_data['otp']
            if user.email_otp != otp:
                return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            if user.email_otp_expiry < timezone.now():
                return Response({'error': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)
            user.is_email_verified = True
            user.email_otp = None
            user.email_otp_expiry = None
            user.save()
            return Response({'message': 'Email verified successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.validated_data['email'])
                otp = user.set_password_reset_otp()
                _send_email(
                    to_email=user.email,
                    subject='Password Reset OTP',
                    body=f'Your password reset OTP is: {otp}. It expires in 10 minutes.',
                )
            except User.DoesNotExist:
                pass
            return Response({'message': 'If that email exists, an OTP has been sent.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.validated_data['email'])
            except User.DoesNotExist:
                return Response({'error': 'Invalid request.'}, status=status.HTTP_400_BAD_REQUEST)
            if user.password_reset_otp != serializer.validated_data['otp']:
                return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            if user.password_reset_otp_expiry < timezone.now():
                return Response({'error': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data['new_password'])
            user.password_reset_otp = None
            user.password_reset_otp_expiry = None
            user.save()
            return Response({'message': 'Password reset successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
