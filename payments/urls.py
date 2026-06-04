from django.urls import path
from .views import (
    InitiatePaymentView,
    VerifyPaymentView,
    FlutterwaveWebhookView,
    MyPaymentsView,
    AdminPaymentsView,
    MockPaymentView,
)

urlpatterns = [
    path('initiate/', InitiatePaymentView.as_view()),
    path('verify/', VerifyPaymentView.as_view()),
    path('webhook/flutterwave/', FlutterwaveWebhookView.as_view()),
    path('my-payments/', MyPaymentsView.as_view()),
    path('admin/all/', AdminPaymentsView.as_view()),
    path('mock-pay/', MockPaymentView.as_view()),
]
