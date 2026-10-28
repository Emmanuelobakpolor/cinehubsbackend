from django.urls import path
from .views import (
    CategoryListCreateView, MovieListCreateView, MovieDetailView,
    TrendingMoviesView, WatchHistoryView, SavedMovieView, UnsaveMovieView, MovieStatsView,
    FeaturedMovieView, SetFeaturedMovieView,
    DownloadCheckView, ConfirmDownloadView, MyDownloadsView,
    UpdateWatchProgressView, CloudinaryUploadSignatureView, CloudinaryPingView,
    PlaybackSessionView, StreamMasterView, StreamVariantView, StreamKeyView, StreamEndView,
)

urlpatterns = [
    path('categories/', CategoryListCreateView.as_view()),
    path('stats/', MovieStatsView.as_view()),
    path('trending/', TrendingMoviesView.as_view()),
    path('featured/', FeaturedMovieView.as_view()),
    path('watch-history/', WatchHistoryView.as_view()),
    path('saved/', SavedMovieView.as_view()),
    path('saved/<int:movie_id>/', UnsaveMovieView.as_view()),
    path('my-downloads/', MyDownloadsView.as_view()),
    path('upload-signature/', CloudinaryUploadSignatureView.as_view()),
    path('cloudinary-ping/', CloudinaryPingView.as_view()),
    path('', MovieListCreateView.as_view()),
    path('<int:pk>/', MovieDetailView.as_view()),
    path('<int:pk>/set-featured/', SetFeaturedMovieView.as_view()),
    path('<int:pk>/download/', DownloadCheckView.as_view()),
    path('<int:pk>/confirm-download/', ConfirmDownloadView.as_view()),
    path('<int:pk>/watch-progress/', UpdateWatchProgressView.as_view()),
    path('<int:pk>/playback/', PlaybackSessionView.as_view()),
]

# Mounted at /api/stream/ — authorized by the playback-session token in the path.
stream_urlpatterns = [
    path('<str:token>/master.m3u8', StreamMasterView.as_view(), name='stream-master'),
    path('<str:token>/<int:index>.m3u8', StreamVariantView.as_view()),
    path('<str:token>/key', StreamKeyView.as_view()),
    path('<str:token>/end', StreamEndView.as_view(), name='stream-end'),
]
