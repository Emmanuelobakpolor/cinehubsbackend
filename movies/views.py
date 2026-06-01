import os
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import NotFound
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import MultiPartParser, FormParser

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Category, Movie, WatchHistory, SavedMovie, UserMovieAccess, MovieDownload
from .serializers import (
    CategorySerializer, MovieSerializer,
    WatchHistorySerializer, SavedMovieSerializer, MovieDownloadSerializer,
)
from subscriptions.models import SubscriptionPlan, UserSubscription


class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticated()]


class MovieListCreateView(generics.ListCreateAPIView):
    queryset = Movie.objects.all().order_by('-created_at')
    serializer_class = MovieSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['categories', 'is_trending']
    search_fields = ['title', 'synopsis', 'cast']
    ordering_fields = ['created_at', 'views_count']
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticated()]


class MovieDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Check if user's 10-day access has expired
        access = UserMovieAccess.objects.filter(
            user=request.user,
            movie=instance,
            is_active=True,
            expires_at__gt=timezone.now(),
        ).first()

        # If they had access before but it expired, block them
        expired = UserMovieAccess.objects.filter(
            user=request.user,
            movie=instance,
            is_active=False,
        ).exists()
        if expired and not access:
            return Response(
                {'error': 'Your 10-day access to this movie has expired.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # First time watching — create access record (10 days from now)
        if not access and not expired:
            UserMovieAccess.objects.get_or_create(
                user=request.user,
                movie=instance,
                defaults={'expires_at': timezone.now() + timedelta(days=10)},
            )

        instance.views_count += 1
        instance.save(update_fields=['views_count'])

        # Create watch history entry on first view only — never reset watch_duration
        # so resuming works correctly after the player reports progress.
        WatchHistory.objects.get_or_create(
            user=request.user,
            movie=instance,
            defaults={'watch_duration': 0},
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class TrendingMoviesView(generics.ListAPIView):
    queryset = Movie.objects.filter(is_trending=True).order_by('-views_count')
    serializer_class = MovieSerializer
    permission_classes = [IsAuthenticated]


class FeaturedMovieView(generics.RetrieveAPIView):
    serializer_class = MovieSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        movie = Movie.objects.filter(is_featured=True).first()
        if not movie:
            raise NotFound("No featured movie set.")
        return movie


class SetFeaturedMovieView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        Movie.objects.filter(is_featured=True).update(is_featured=False)
        movie = get_object_or_404(Movie, pk=pk)
        movie.is_featured = True
        movie.save(update_fields=['is_featured'])
        return Response(MovieSerializer(movie, context={'request': request}).data)


class WatchHistoryView(generics.ListAPIView):
    serializer_class = WatchHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WatchHistory.objects.filter(user=self.request.user).order_by('-watched_at')


class MovieStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_bytes = 0
        media_root = str(settings.MEDIA_ROOT)
        for dirpath, _, filenames in os.walk(media_root):
            for f in filenames:
                try:
                    total_bytes += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass

        return Response({
            'total_movies': Movie.objects.count(),
            'this_month': Movie.objects.filter(created_at__gte=start_of_month).count(),
            'storage_bytes': total_bytes,
        })


class SavedMovieView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved = SavedMovie.objects.filter(user=request.user).order_by('-saved_at')
        serializer = SavedMovieSerializer(saved, many=True)
        return Response(serializer.data)

    def post(self, request):
        movie_id = request.data.get('movie_id')
        try:
            movie = Movie.objects.get(id=movie_id)
        except Movie.DoesNotExist:
            return Response({'error': 'Movie not found.'}, status=status.HTTP_404_NOT_FOUND)
        saved, created = SavedMovie.objects.get_or_create(user=request.user, movie=movie)
        if not created:
            return Response({'message': 'Already saved.'})
        return Response({'message': 'Movie saved successfully.'}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        movie_id = request.data.get('movie_id')
        SavedMovie.objects.filter(user=request.user, movie_id=movie_id).delete()
        return Response({'message': 'Removed from saved.'})


class UnsaveMovieView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, movie_id):
        deleted, _ = SavedMovie.objects.filter(user=request.user, movie_id=movie_id).delete()
        if deleted:
            return Response({'message': 'Removed from saved.'})
        return Response({'error': 'Movie not in saved list.'}, status=status.HTTP_404_NOT_FOUND)


def _has_active_premium(user):
    """Return True if the user has an active Premium subscription."""
    return UserSubscription.objects.filter(
        user=user,
        plan__name='PREMIUM',
        status='ACTIVE',
        end_date__gt=timezone.now(),
    ).exists()


class DownloadCheckView(APIView):
    """
    GET  /api/movies/<pk>/download/ — check if user can download.
    Returns:
      200 { "status": "allowed", "download_url": "...", "reason": "premium"|"already_paid" }
      402 { "status": "payment_required", "amount": "200.00", "movie_id": <id> }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        movie = get_object_or_404(Movie, pk=pk)

        # Premium subscribers can download anything
        if _has_active_premium(request.user):
            return Response({
                'status': 'allowed',
                'reason': 'premium',
                'download_url': request.build_absolute_uri(movie.movie_file.url) if movie.movie_file else '',
            })

        # Basic user who already paid for this specific movie
        download = MovieDownload.objects.filter(user=request.user, movie=movie).first()
        if download:
            return Response({
                'status': 'allowed',
                'reason': 'already_paid',
                'download_url': request.build_absolute_uri(movie.movie_file.url) if movie.movie_file else '',
            })

        # Must pay
        try:
            basic_plan = SubscriptionPlan.objects.get(name='BASIC')
            amount = str(basic_plan.price)
        except SubscriptionPlan.DoesNotExist:
            amount = '200.00'

        return Response(
            {
                'status': 'payment_required',
                'amount': amount,
                'movie_id': movie.id,
                'movie_title': movie.title,
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )


class ConfirmDownloadView(APIView):
    """
    POST /api/movies/<pk>/confirm-download/
    Body: { "payment_reference": "optional_ref" }

    Placeholder endpoint — marks a movie as paid for the requesting user.
    Replace body logic with real gateway webhook verification later.
    Returns the same 'allowed' response as DownloadCheckView.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        movie = get_object_or_404(Movie, pk=pk)

        # Premium users get free access — record the download so it shows in MyDownloadsView
        if _has_active_premium(request.user):
            MovieDownload.objects.get_or_create(
                user=request.user,
                movie=movie,
                defaults={'amount_paid': 0, 'payment_reference': 'PREMIUM'},
            )
            return Response({
                'status': 'allowed',
                'reason': 'premium',
                'download_url': request.build_absolute_uri(movie.movie_file.url) if movie.movie_file else '',
            })

        try:
            basic_plan = SubscriptionPlan.objects.get(name='BASIC')
            amount = basic_plan.price
        except SubscriptionPlan.DoesNotExist:
            amount = '200.00'

        download, created = MovieDownload.objects.get_or_create(
            user=request.user,
            movie=movie,
            defaults={
                'amount_paid': amount,
                'payment_reference': request.data.get('payment_reference', ''),
            },
        )

        return Response({
            'status': 'allowed',
            'reason': 'paid' if created else 'already_paid',
            'download_url': request.build_absolute_uri(movie.movie_file.url) if movie.movie_file else '',
            'amount_paid': str(download.amount_paid),
        }, status=status.HTTP_200_OK)


class MyDownloadsView(generics.ListAPIView):
    """GET /api/movies/my-downloads/ — list all movies a user has paid to download."""
    serializer_class = MovieDownloadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MovieDownload.objects.filter(user=self.request.user).order_by('-paid_at')


class UpdateWatchProgressView(APIView):
    """
    PATCH /api/movies/<pk>/watch-progress/
    Body: { "watch_duration": <seconds_watched> }

    Called periodically by the Flutter player to record how far the user got.
    Creates WatchHistory AND UserMovieAccess (10-day window) if they don't exist yet.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        movie = get_object_or_404(Movie, pk=pk)
        try:
            duration = int(request.data.get('watch_duration', 0))
        except (TypeError, ValueError):
            duration = 0

        WatchHistory.objects.update_or_create(
            user=request.user,
            movie=movie,
            defaults={'watch_duration': duration},
        )

        # Ensure the 10-day access window exists.
        # UserMovieAccess is only created in MovieDetailView.retrieve() but Flutter
        # never calls that endpoint directly, so we must create it here on first play.
        UserMovieAccess.objects.get_or_create(
            user=request.user,
            movie=movie,
            defaults={'expires_at': timezone.now() + timedelta(days=10)},
        )

        return Response({'status': 'ok', 'watch_duration': duration})
