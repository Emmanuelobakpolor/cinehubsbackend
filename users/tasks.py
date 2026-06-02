from celery import shared_task


@shared_task
def send_email_otp_task(user_id):
    from .models import User
    from .views import send_email_otp
    try:
        user = User.objects.get(pk=user_id)
        send_email_otp(user)
    except User.DoesNotExist:
        pass
