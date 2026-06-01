from django.urls import path
from .views import InitiatePaymentView, VerifyPaymentView, MyPaymentsView, AdminPaymentsView

urlpatterns = [
    path('initiate/', InitiatePaymentView.as_view()),
    path('verify/', VerifyPaymentView.as_view()),
    path('my-payments/', MyPaymentsView.as_view()),
    path('admin/all/', AdminPaymentsView.as_view()),
]
