from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_email_otp_task(self, user_id):
    from django.contrib.auth import get_user_model
    from users.views import send_email_otp
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        send_email_otp(user)
    except Exception as exc:
        raise self.retry(exc=exc)
