from django.urls import path
from .views import MovieReviewsView, ReviewDetailView, AdminReviewListCreateView, AdminReviewDetailView

urlpatterns = [
    path('movie/<int:movie_id>/', MovieReviewsView.as_view()),
    path('<int:pk>/', ReviewDetailView.as_view()),
    path('admin/', AdminReviewListCreateView.as_view()),
    path('admin/<int:pk>/', AdminReviewDetailView.as_view()),
]
