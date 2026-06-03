from django.urls import path
from .views import (
    MyNotificationsView,
    BroadcastView,
    RegisterDeviceTokenView,
    AdminAnalyticsView,
    AdminNotificationsView,
)

urlpatterns = [
    path('my/', MyNotificationsView.as_view()),
    path('<int:pk>/read/', MyNotificationsView.as_view()),
    path('broadcast/', BroadcastView.as_view()),
    path('device-token/', RegisterDeviceTokenView.as_view()),
    path('analytics/', AdminAnalyticsView.as_view()),
    # Admin-only event notifications (ratings, subscriptions, purchases)
    path('admin/', AdminNotificationsView.as_view()),
    path('admin/<int:pk>/read/', AdminNotificationsView.as_view()),
    path('admin/read-all/', AdminNotificationsView.as_view()),
]
