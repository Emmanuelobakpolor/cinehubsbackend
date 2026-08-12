from django.utils import timezone
from django.conf import settings

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
    """Send a transactional email via SendGrid HTTP API. Falls back to console if USE_CONSOLE_EMAIL=True."""
    if settings.USE_CONSOLE_EMAIL:
        print(f"\n[EMAIL] To: {to_email} | Subject: {subject}\n{body}\n")
        return
    import sendgrid
    from sendgrid.helpers.mail import Mail
    print(f"[EMAIL] Attempting to send to: {to_email} | Subject: {subject}")
    print(f"[EMAIL] API KEY set: {bool(settings.SENDGRID_API_KEY)}")
    try:
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
        )
        response = sg.send(message)
        print(f"[EMAIL] Sent successfully to {to_email} | Status: {response.status_code}")
    except Exception as e:
        print(f"[EMAIL ERROR]: {repr(e)}")
        raise


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
                import threading
                threading.Thread(target=send_email_otp, args=(user,), daemon=True).start()
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


class CreateAdminView(APIView):
    """Create a new admin (staff) account. Open - no auth required."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data={**request.data, 'role': 'admin'})
        if serializer.is_valid():
            user = serializer.save()
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username
            return Response({
                'message': 'Admin account created successfully.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'full_name': full_name,
                },
            }, status=status.HTTP_201_CREATED)
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
        import cloudinary.uploader
        try:
            result = cloudinary.uploader.upload(
                request.FILES['profile_picture'],
                resource_type='image',
                folder='profiles',
                timeout=60,
            )
            url = result.get('secure_url')
            if not url:
                raise ValueError('Cloudinary returned no URL')
        except Exception as exc:
            return Response(
                {'error': f'Image upload failed: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        request.user.profile_picture = url
        request.user.save(update_fields=['profile_picture'])
        serializer = UserProfileSerializer(request.user)
        data = serializer.data
        data.update(_get_stats(request.user))
        return Response(data)

    def delete(self, request):
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


class AdminAllUsersView(APIView):
    """Admin-only: list all non-staff users with full profile + subscription + purchase stats."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from subscriptions.models import UserSubscription
        from movies.models import MovieDownload
        from django.db.models import Count, Q, Prefetch

        users = (
            User.objects.filter(is_staff=False)
            .annotate(
                # Only count per-movie paid purchases (amount_paid > 0).
                # Premium "free" downloads have amount_paid=0 and are excluded here.
                movies_bought=Count(
                    'movie_downloads',
                    filter=Q(movie_downloads__amount_paid__gt=0),
                    distinct=True,
                )
            )
            .prefetch_related(
                Prefetch(
                    'subscriptions',
                    queryset=UserSubscription.objects.select_related('plan').order_by('-start_date'),
                    to_attr='_subs',
                )
            )
            .order_by('-date_joined')
        )

        results = []
        for user in users:
            sub = user._subs[0] if user._subs else None
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username
            results.append({
                'id': user.id,
                'full_name': full_name,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number or '',
                'profile_picture': user.profile_picture or '',
                'is_email_verified': user.is_email_verified,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat(),
                'subscription': {
                    'plan': sub.plan.name,
                    'status': sub.status,
                    'is_active': sub.is_active,
                    'end_date': sub.end_date.isoformat(),
                } if sub else None,
                'movies_bought': user.movies_bought,
            })

        return Response({'count': len(results), 'results': results})


class AdminUpdateAccountView(APIView):
    """Admin-only: change own email and/or password without OTP verification."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request):
        user = request.user
        new_email = request.data.get('email', '').strip()
        new_password = request.data.get('new_password', '').strip()
        current_password = request.data.get('current_password', '').strip()

        if new_email:
            if User.objects.exclude(pk=user.pk).filter(email=new_email).exists():
                return Response({'error': 'That email is already in use.'}, status=status.HTTP_400_BAD_REQUEST)
            user.email = new_email
            user.username = new_email

        if new_password:
            if not current_password:
                return Response({'error': 'Current password is required to set a new password.'}, status=status.HTTP_400_BAD_REQUEST)
            if not user.check_password(current_password):
                return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
            if len(new_password) < 6:
                return Response({'error': 'New password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(new_password)

        user.save()
        return Response({
            'message': 'Account updated successfully.',
            'email': user.email,
        })


class SendEmailOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from users.tasks import send_email_otp_task
        send_email_otp_task.delay(request.user.id)
        return Response({'message': 'OTP sent to your email.'})


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
