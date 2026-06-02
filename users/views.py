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


def _send_email(to_email, subject, body, html_body=None):
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
            html_content=html_body,
        )
        response = sg.send(message)
        print(f"[EMAIL] Sent successfully to {to_email} | Status: {response.status_code}")
    except Exception as e:
        print(f"[EMAIL ERROR]: {repr(e)}")
        raise


def _otp_email_html(otp):
    logo_url = settings.CINEHUBS_LOGO_URL
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Email Verification</title>
</head>
<body style="margin:0;padding:0;background-color:#0d0d14;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#0d0d14;padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="max-width:520px;">

          <!-- ── HEADER ── -->
          <tr>
            <td align="center"
                style="background-color:#13131f;border-radius:16px 16px 0 0;
                       padding:36px 40px 28px;
                       border-top:3px solid #f59e0b;">
              <img src="{logo_url}" alt="CineHubs" width="72" height="72"
                   style="display:block;margin:0 auto 14px;" />
              <span style="font-size:22px;font-weight:800;letter-spacing:2px;
                           color:#f59e0b;text-transform:uppercase;">CineHubs</span>
            </td>
          </tr>

          <!-- ── BODY ── -->
          <tr>
            <td style="background-color:#1a1a2e;padding:40px 40px 36px;">
              <h1 style="margin:0 0 10px;font-size:20px;font-weight:700;color:#ffffff;">
                Verify your email address
              </h1>
              <p style="margin:0 0 32px;font-size:14px;color:#8888aa;line-height:1.7;">
                Enter the code below inside the CineHubs app to complete your
                email verification. This code expires in
                <strong style="color:#e2e2f0;">10 minutes</strong>.
              </p>

              <!-- OTP box -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center"
                      style="background-color:#0d0d14;border:2px solid #f59e0b;
                             border-radius:12px;padding:28px 20px;">
                    <p style="margin:0 0 6px;font-size:11px;font-weight:600;
                              letter-spacing:3px;color:#f59e0b;text-transform:uppercase;">
                      Your verification code
                    </p>
                    <p style="margin:0;font-size:42px;font-weight:900;
                              letter-spacing:14px;color:#ffffff;
                              font-family:'Courier New',monospace;">
                      {otp}
                    </p>
                  </td>
                </tr>
              </table>

              <p style="margin:32px 0 0;font-size:13px;color:#55556a;line-height:1.6;">
                If you didn't create a CineHubs account, you can safely ignore
                this email. Someone may have entered your address by mistake.
              </p>
            </td>
          </tr>

          <!-- ── FOOTER ── -->
          <tr>
            <td align="center"
                style="background-color:#13131f;border-radius:0 0 16px 16px;
                       padding:20px 40px 24px;border-top:1px solid #22223a;">
              <p style="margin:0;font-size:12px;color:#3d3d55;">
                &copy; 2026 CineHubs &nbsp;&middot;&nbsp; All rights reserved
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_email_otp(user):
    otp = user.set_email_otp()
    _send_email(
        to_email=user.email,
        subject='Email Verification OTP — CineHubs',
        body=f'Your CineHubs OTP is: {otp}. It expires in 10 minutes.',
        html_body=_otp_email_html(otp),
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
