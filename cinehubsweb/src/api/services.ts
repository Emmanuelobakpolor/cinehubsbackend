// One module per Flutter service, same endpoints and payloads.
import { api, asList, storage, ApiError } from './client';
import {
  toMovie,
  toWatchHistory,
  toDownload,
  toReview,
  toProfile,
  type Movie,
  type Category,
  type SavedItem,
  type AppNotification,
} from './types';
import { buildMediaUrl } from './client';

// ── Auth (AuthService) ─────────────────────────────────────────────

export const AuthService = {
  async register(p: { fullName: string; email: string; password: string; phoneNumber?: string }) {
    const { data } = await api('/users/register/', {
      method: 'POST',
      auth: false,
      body: {
        full_name: p.fullName,
        email: p.email,
        password: p.password,
        ...(p.phoneNumber ? { phone_number: p.phoneNumber } : {}),
      },
    });
    storage.saveTokens(data.access_token, data.refresh_token);
    return data;
  },
  async login(email: string, password: string) {
    const { data } = await api('/users/login/', {
      method: 'POST',
      auth: false,
      body: { email, password },
    });
    storage.saveTokens(data.access_token, data.refresh_token);
    return data;
  },
  async logout() {
    try {
      await api('/users/logout/', {
        method: 'POST',
        body: { refresh_token: storage.getRefreshToken() },
      });
    } catch {
      // Always clear local tokens even if the API call fails
    } finally {
      storage.clearTokens();
    }
  },
  verifyEmail: (otp: string) => api('/users/verify-email/', { method: 'POST', body: { otp } }),
  resendEmailOtp: () => api('/users/send-email-otp/', { method: 'POST' }),
  forgotPassword: (email: string) =>
    api('/users/forgot-password/', { method: 'POST', auth: false, body: { email } }),
  resetPassword: (email: string, otp: string, newPassword: string) =>
    api('/users/reset-password/', {
      method: 'POST',
      auth: false,
      body: { email, otp, new_password: newPassword },
    }),
};

// ── Movies (MovieService) ──────────────────────────────────────────

export const MovieService = {
  async fetchMovies(opts: { categoryId?: number; search?: string; pageSize?: number } = {}) {
    const q = new URLSearchParams({ page_size: String(opts.pageSize ?? 20) });
    if (opts.categoryId != null) q.set('categories', String(opts.categoryId));
    if (opts.search) q.set('search', opts.search);
    const { data } = await api(`/movies/?${q}`);
    return asList(data).map(toMovie);
  },
  async fetchMovie(id: number): Promise<Movie> {
    const { data } = await api(`/movies/${id}/`);
    return toMovie(data);
  },
  async fetchTrending() {
    const { data } = await api('/movies/trending/');
    return asList(data).map(toMovie);
  },
  /** Admin-featured movie, or null if none is set. */
  async fetchFeatured(): Promise<Movie | null> {
    const { status, data } = await api('/movies/featured/', { allowStatus: [404] });
    return status === 404 || !data ? null : toMovie(data);
  },
  async fetchCategories(): Promise<Category[]> {
    const { data } = await api('/movies/categories/?page_size=100');
    return asList<any>(data).map((c) => ({ id: c.id, name: String(c.name) }));
  },
  async fetchSaved(): Promise<SavedItem[]> {
    const { data } = await api('/movies/saved/');
    return asList<any>(data).map((e) => ({
      movieId: e.movie,
      title: String(e.movie_title ?? ''),
      thumbnailUrl: buildMediaUrl(e.movie_thumbnail),
    }));
  },
  /** Returns true if newly saved, false if already saved. */
  async saveMovie(movieId: number) {
    const { status } = await api('/movies/saved/', { method: 'POST', body: { movie_id: movieId } });
    return status === 201;
  },
  unsaveMovie: (movieId: number) => api(`/movies/saved/${movieId}/`, { method: 'DELETE' }),
  /** Fails silently — a missed progress update is not critical. */
  async updateWatchProgress(movieId: number, seconds: number) {
    try {
      await api(`/movies/${movieId}/watch-progress/`, {
        method: 'PATCH',
        body: { watch_duration: seconds },
      });
    } catch {
      /* silent */
    }
  },
  async fetchWatchHistory() {
    const { data } = await api('/movies/watch-history/');
    return asList(data).map(toWatchHistory);
  },
  async fetchMyDownloads() {
    const { data } = await api('/movies/my-downloads/');
    return asList(data).map(toDownload);
  },
  /** allowed=true for PREMIUM users or BASIC users who already paid for this movie. */
  async checkAccess(movieId: number) {
    const { status, data } = await api(`/movies/${movieId}/download/`, { allowStatus: [402] });
    if (status === 402) {
      return { allowed: false, amount: String(data?.amount ?? '200.00'), downloadUrl: '' };
    }
    return { allowed: true, amount: '0', downloadUrl: buildMediaUrl(data?.download_url) };
  },
  /** Mark movie as paid (BASIC per-movie flow). Returns the download URL. */
  async confirmMoviePayment(movieId: number, txRef = '') {
    const { data } = await api(`/movies/${movieId}/confirm-download/`, {
      method: 'POST',
      body: { payment_reference: txRef },
    });
    return buildMediaUrl(data?.download_url);
  },
};

// ── Payments (PaymentService) ──────────────────────────────────────

export const PLAN_BASIC = 1;
export const PLAN_PREMIUM = 2;

/** What to do once Flutterwave sends the browser back to /payment/callback. */
export interface PendingPayment {
  txRef: string;
  planId: number;
  planName: string;
  movieId?: number;
  movieTitle?: string;
}

const PENDING_KEY = 'pending_payment';

export const PaymentService = {
  /**
   * Starts checkout for [planId] and leaves the page for Flutterwave.
   * In backend test mode there is no real checkout, so we verify straight away.
   */
  async startCheckout(pending: Omit<PendingPayment, 'txRef'>) {
    const redirectUrl = `${window.location.origin}/payment/callback`;
    const { data } = await api('/payments/initiate/', {
      method: 'POST',
      body: { plan_id: pending.planId, redirect_url: redirectUrl },
    });
    const txRef: string = data.tx_ref;
    const link: string = data.payment_link;
    storage.set(PENDING_KEY, JSON.stringify({ ...pending, txRef }));
    if (link.includes('/api/payments/mock-pay/')) {
      window.location.assign(`/payment/callback?status=successful&tx_ref=${txRef}&transaction_id=TEST-MOCK`);
    } else {
      window.location.assign(link);
    }
  },
  getPending(): PendingPayment | null {
    try {
      return JSON.parse(storage.get(PENDING_KEY) || 'null');
    } catch {
      return null;
    }
  },
  clearPending: () => storage.remove(PENDING_KEY),
  verifyPayment: (txRef: string, transactionId?: string) =>
    api('/payments/verify/', {
      method: 'POST',
      body: { tx_ref: txRef, ...(transactionId ? { transaction_id: transactionId } : {}) },
    }),
  /** The user's currently active subscription, if any. */
  async activeSubscription(): Promise<{ planName: string; endDate: string } | null> {
    try {
      const { data } = await api('/subscriptions/my-subscription/');
      const active = asList<any>(data).find(
        (s) => s.status === 'ACTIVE' && new Date(s.end_date) > new Date(),
      );
      return active ? { planName: String(active.plan_name), endDate: String(active.end_date) } : null;
    } catch (e) {
      if (e instanceof ApiError) return null;
      throw e;
    }
  },
};

// ── Reviews (ReviewService) ────────────────────────────────────────

export const ReviewService = {
  async fetchReviews(movieId: number) {
    const { data } = await api(`/reviews/movie/${movieId}/`);
    return asList(data).map(toReview);
  },
  async submitReview(movieId: number, rating: number, comment?: string) {
    const { data } = await api(`/reviews/movie/${movieId}/`, {
      method: 'POST',
      body: { rating, ...(comment && comment.trim() ? { comment: comment.trim() } : {}) },
    });
    return toReview(data);
  },
};

// ── User (UserService) ─────────────────────────────────────────────

export const UserService = {
  async getProfile() {
    const { data } = await api('/users/profile/');
    return toProfile(data);
  },
  async updateProfile(p: { fullName?: string; phoneNumber?: string; bio?: string }) {
    const body: Record<string, string> = {};
    if (p.fullName != null) body.full_name = p.fullName;
    if (p.phoneNumber != null) body.phone_number = p.phoneNumber;
    if (p.bio != null) body.bio = p.bio;
    const { data } = await api('/users/profile/', { method: 'PATCH', body });
    return toProfile(data);
  },
  async uploadProfilePicture(file: File) {
    const form = new FormData();
    form.append('profile_picture', file);
    const { data } = await api('/users/profile/picture/', { method: 'PATCH', body: form });
    return toProfile(data);
  },
  changePassword: (oldPassword: string, newPassword: string) =>
    api('/users/change-password/', {
      method: 'POST',
      body: { old_password: oldPassword, new_password: newPassword },
    }),
};

// ── Notifications (NotificationService) — read state kept locally ──

const READ_KEY = 'read_notification_ids';

function getReadIds(): Set<number> {
  try {
    return new Set(JSON.parse(storage.get(READ_KEY) || '[]'));
  } catch {
    return new Set();
  }
}

export const NotificationService = {
  markAsRead(id: number) {
    const ids = getReadIds();
    ids.add(id);
    storage.set(READ_KEY, JSON.stringify([...ids]));
  },
  markAllAsRead(list: number[]) {
    const ids = getReadIds();
    list.forEach((i) => ids.add(i));
    storage.set(READ_KEY, JSON.stringify([...ids]));
  },
  async fetchMyNotifications(): Promise<AppNotification[]> {
    const { data } = await api('/notifications/my/');
    const read = getReadIds();
    return asList<any>(data).map((e) => ({
      id: e.id,
      title: String(e.title ?? ''),
      message: String(e.message ?? ''),
      notificationType: e.notification_type ?? 'BROADCAST',
      targetAudience: e.target_audience ?? 'ALL',
      createdAt: new Date(e.created_at ?? Date.now()),
      isRead: read.has(e.id),
    }));
  },
  async fetchUnreadCount() {
    try {
      return (await this.fetchMyNotifications()).filter((n) => !n.isRead).length;
    } catch {
      return 0;
    }
  },
};
