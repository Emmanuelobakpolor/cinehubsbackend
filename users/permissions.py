from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated


EMAIL_NOT_VERIFIED = 'email_not_verified'


class IsVerifiedUser(IsAuthenticated):
    """Authenticated users who have verified their email. Staff are always allowed.

    Unverified users get a 403 with code 'email_not_verified' so the web and
    mobile clients can send them to the OTP screen.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if user.is_staff or user.is_email_verified:
            return True
        raise PermissionDenied({
            'detail': 'Please verify your email address to continue.',
            'code': EMAIL_NOT_VERIFIED,
        })


class IsVerifiedUserOrReadOnly(IsVerifiedUser):
    """Anyone may browse (GET/HEAD/OPTIONS); writes need a verified user.

    Guests can see the catalogue before signing up (App Store guideline 5.1.1).
    Signed-in but unverified users still get the 'email_not_verified' 403 on
    reads, so the apps keep routing them to the OTP screen.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS and not (
            request.user and request.user.is_authenticated
        ):
            return True
        return super().has_permission(request, view)
