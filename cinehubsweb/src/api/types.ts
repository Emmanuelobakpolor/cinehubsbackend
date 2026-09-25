import { buildMediaUrl } from './client';

export interface Movie {
  id: number;
  title: string;
  synopsis: string;
  thumbnailUrl: string;
  movieFileUrl: string;
  categoryNames: string[];
  cast: string;
  releaseYear: string;
  runtime: string;
  rating: string;
  director: string;
  viewsCount: number;
  isTrending: boolean;
  isFeatured: boolean;
  createdAt: string;
  trailerUrl: string;
  thrillerClipUrl: string;
}

const str = (v: unknown) => (v == null ? '' : String(v));

export function toMovie(j: any): Movie {
  return {
    id: j.id,
    title: str(j.title),
    synopsis: str(j.synopsis),
    thumbnailUrl: buildMediaUrl(j.thumbnail),
    movieFileUrl: buildMediaUrl(j.movie_file),
    categoryNames: Array.isArray(j.category_names) ? j.category_names.map(String) : [],
    cast: str(j.cast),
    releaseYear: str(j.release_year),
    runtime: str(j.runtime),
    rating: str(j.rating),
    director: str(j.director),
    viewsCount: j.views_count ?? 0,
    isTrending: !!j.is_trending,
    isFeatured: !!j.is_featured,
    createdAt: str(j.created_at),
    trailerUrl: buildMediaUrl(j.trailer_url),
    thrillerClipUrl: buildMediaUrl(j.thriller_clip),
  };
}

export interface Category {
  id: number;
  name: string;
}

export interface WatchHistoryItem {
  id: number;
  movieId: number;
  movieTitle: string;
  movieThumbnailUrl: string;
  watchedAt: string;
  watchDuration: number;
  expiresAt: string | null;
}

export function toWatchHistory(j: any): WatchHistoryItem {
  return {
    id: j.id,
    movieId: j.movie,
    movieTitle: str(j.movie_title),
    movieThumbnailUrl: buildMediaUrl(j.movie_thumbnail),
    watchedAt: str(j.watched_at),
    watchDuration: j.watch_duration ?? 0,
    expiresAt: j.expires_at == null ? null : String(j.expires_at),
  };
}

export interface DownloadItem {
  id: number;
  movieId: number;
  movieTitle: string;
  movieThumbnailUrl: string;
  movieFileUrl: string;
  amountPaid: string;
  paidAt: string;
}

export function toDownload(j: any): DownloadItem {
  return {
    id: j.id,
    movieId: j.movie,
    movieTitle: str(j.movie_title),
    movieThumbnailUrl: buildMediaUrl(j.movie_thumbnail),
    movieFileUrl: buildMediaUrl(j.movie_file),
    amountPaid: str(j.amount_paid) || '0',
    paidAt: str(j.paid_at),
  };
}

export interface SavedItem {
  movieId: number;
  title: string;
  thumbnailUrl: string;
}

export interface Review {
  id: number;
  userId: number;
  username: string;
  movieId: number;
  rating: number;
  comment: string;
  createdAt: string;
}

export function toReview(j: any): Review {
  return {
    id: j.id,
    userId: j.user ?? 0,
    username: str(j.username),
    movieId: j.movie ?? 0,
    rating: j.rating ?? 0,
    comment: str(j.comment),
    createdAt: str(j.created_at),
  };
}

export interface UserProfile {
  id: number;
  fullName: string;
  email: string;
  phoneNumber: string | null;
  bio: string | null;
  profilePictureUrl: string | null;
  isEmailVerified: boolean;
  watchedCount: number;
  savedCount: number;
  reviewsCount: number;
}

export function toProfile(j: any): UserProfile {
  return {
    id: j.id,
    fullName: str(j.full_name),
    email: str(j.email),
    phoneNumber: j.phone_number ?? null,
    bio: j.bio ?? null,
    profilePictureUrl: j.profile_picture ? buildMediaUrl(j.profile_picture) : null,
    isEmailVerified: !!j.is_email_verified,
    watchedCount: j.watched_count ?? 0,
    savedCount: j.saved_count ?? 0,
    reviewsCount: j.reviews_count ?? 0,
  };
}

export interface AppNotification {
  id: number;
  title: string;
  message: string;
  notificationType: string;
  targetAudience: string;
  createdAt: Date;
  isRead: boolean;
}
