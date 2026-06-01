from django.urls import path
from .views import MyNotificationsView, BroadcastView, RegisterDeviceTokenView, AdminAnalyticsView

urlpatterns = [
    path('my/', MyNotificationsView.as_view()),
    path('<int:pk>/read/', MyNotificationsView.as_view()),
    path('broadcast/', BroadcastView.as_view()),
    path('device-token/', RegisterDeviceTokenView.as_view()),
    path('analytics/', AdminAnalyticsView.as_view()),
]
