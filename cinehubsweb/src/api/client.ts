// Thin fetch wrapper shared by every service. Mirrors the Flutter app's Dio
// setup: Bearer token from storage, DRF-style error parsing, 15s timeout.

export const BACKEND_URL: string =
  import.meta.env.VITE_BACKEND_URL || 'https://cinehubsbackend-production.up.railway.app';
export const API_BASE: string = import.meta.env.VITE_API_BASE || '/api';

const ACCESS_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function safeSet(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) — session will just not persist */
  }
}
function safeRemove(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

export const storage = {
  get: safeGet,
  set: safeSet,
  remove: safeRemove,
  getAccessToken: () => safeGet(ACCESS_KEY),
  getRefreshToken: () => safeGet(REFRESH_KEY),
  hasTokens: () => !!safeGet(ACCESS_KEY),
  saveTokens(access: string, refresh: string) {
    safeSet(ACCESS_KEY, access);
    safeSet(REFRESH_KEY, refresh);
  },
  clearTokens() {
    safeRemove(ACCESS_KEY);
    safeRemove(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

/** Same rules as the app's _parseError: detail/error/non_field_errors, then first field error. */
export function parseError(data: unknown, status: number): string {
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const d = data as Record<string, unknown>;
    for (const key of ['detail', 'error', 'non_field_errors']) {
      const v = d[key];
      if (v != null) return Array.isArray(v) ? String(v[0]) : String(v);
    }
    for (const v of Object.values(d)) {
      if (Array.isArray(v) && v.length) return String(v[0]);
      if (typeof v === 'string') return v;
    }
  }
  if (status === 0) return 'Cannot reach server. Check your connection.';
  if (status === 408) return 'Connection timed out. Please try again.';
  return 'Something went wrong. Please try again.';
}

/** Called when the session can't be refreshed; App wires this to a redirect. */
let onSessionExpired: () => void = () => {};
export function setSessionExpiredHandler(fn: () => void) {
  onSessionExpired = fn;
}

let refreshing: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refresh = storage.getRefreshToken();
  if (!refresh) return false;
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      storage.saveTokens(data.access, data.refresh ?? refresh);
      return true;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

type Options = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  /** Treat these non-2xx statuses as a normal response instead of throwing. */
  allowStatus?: number[];
};

export async function api<T = any>(
  path: string,
  { method = 'GET', body, auth = true, allowStatus = [] }: Options = {},
  retried = false,
): Promise<{ status: number; data: T }> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const isForm = body instanceof FormData;
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  const token = storage.getAccessToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), isForm ? 120_000 : 15_000);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (e) {
    const timedOut = (e as Error).name === 'AbortError';
    throw new ApiError(parseError(null, timedOut ? 408 : 0), timedOut ? 408 : 0, null);
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401 && auth && !retried) {
    if (await refreshAccessToken()) return api<T>(path, { method, body, auth, allowStatus }, true);
    storage.clearTokens();
    onSessionExpired();
  }

  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok && !allowStatus.includes(res.status)) {
    throw new ApiError(parseError(data, res.status), res.status, data);
  }
  return { status: res.status, data };
}

/** Lists come back either as an array or DRF-paginated {results: [...]}. */
export function asList<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object' && Array.isArray((data as any).results)) {
    return (data as any).results as T[];
  }
  return [];
}

export function buildMediaUrl(path: unknown): string {
  if (path == null || String(path) === '') return '';
  const s = String(path);
  return s.startsWith('http') ? s : `${BACKEND_URL}${s}`;
}
