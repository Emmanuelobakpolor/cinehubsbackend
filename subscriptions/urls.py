from django.urls import path
from .views import SubscriptionPlanListView, SubscriptionPlanDetailView, MySubscriptionView, AllSubscribersView

urlpatterns = [
    path('plans/', SubscriptionPlanListView.as_view()),
    path('plans/<int:pk>/', SubscriptionPlanDetailView.as_view()),
    path('my-subscription/', MySubscriptionView.as_view()),
    path('subscribers/', AllSubscribersView.as_view()),
]
