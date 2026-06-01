from django.urls import path
from .views import MovieReviewsView, ReviewDetailView

urlpatterns = [
    path('movie/<int:movie_id>/', MovieReviewsView.as_view()),
    path('<int:pk>/', ReviewDetailView.as_view()),
]
