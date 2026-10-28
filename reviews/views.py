from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from users.permissions import IsVerifiedUser

from .models import Review
from .serializers import ReviewSerializer, AdminReviewSerializer


class MovieReviewsView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsVerifiedUser]

    def get_queryset(self):
        movie_id = self.kwargs['movie_id']
        return Review.objects.filter(movie_id=movie_id).select_related('user', 'movie').order_by('-created_at')

    def perform_create(self, serializer):
        movie_id = self.kwargs['movie_id']
        serializer.save(user=self.request.user, movie_id=movie_id)


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsVerifiedUser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        return Review.objects.filter(user=self.request.user)


class AdminReviewListCreateView(generics.ListCreateAPIView):
    """Admin-only: list every review (optionally ?movie=<id>) and add custom reviews."""
    serializer_class = AdminReviewSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = Review.objects.select_related('user', 'movie').order_by('-created_at')
        movie_id = self.request.query_params.get('movie')
        if movie_id:
            qs = qs.filter(movie_id=movie_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=None)


class AdminReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin-only: edit or delete any review."""
    serializer_class = AdminReviewSerializer
    permission_classes = [IsAdminUser]
    queryset = Review.objects.select_related('user', 'movie')
