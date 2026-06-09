from django.urls import path
from .views import (
    RegisterView, LoginView, AdminLoginView, LogoutView, ProfileView,
    ProfilePictureView, ChangePasswordView, SendEmailOTPView, VerifyEmailView,
    ForgotPasswordView, ResetPasswordView, DashboardStatsView, DeleteUserView,
    AdminUpdateAccountView, AdminAllUsersView,
)

urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
    path('admin-login/', AdminLoginView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('profile/', ProfileView.as_view()),
    path('profile/picture/', ProfilePictureView.as_view()),
    path('change-password/', ChangePasswordView.as_view()),
    path('admin/account/', AdminUpdateAccountView.as_view()),
    path('admin/users/', AdminAllUsersView.as_view()),
    path('send-email-otp/', SendEmailOTPView.as_view()),
    path('verify-email/', VerifyEmailView.as_view()),
    path('forgot-password/', ForgotPasswordView.as_view()),
    path('reset-password/', ResetPasswordView.as_view()),
    path('dashboard-stats/', DashboardStatsView.as_view()),
    path('<int:user_id>/delete/', DeleteUserView.as_view()),
]
