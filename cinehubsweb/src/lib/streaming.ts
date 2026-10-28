// Attaches an authorized playback session to a <video> element.
//
// Full movies never play from a permanent file URL. The backend returns a
// short-lived session (see MovieService.startPlayback):
//   - "hls":         AES-128 encrypted HLS; the key URL only works for this session.
//   - "drm":         Widevine / PlayReady / FairPlay via the configured DRM provider.
//   - "progressive": legacy MP4, only for movies not yet packaged for streaming.
// Shaka Player is loaded on demand so it doesn't weigh down the rest of the app.

// The HLS-only build: everything we play is HLS, and it is ~25% smaller.
import type shakaNamespace from 'shaka-player/dist/shaka-player.hls';

type Shaka = typeof shakaNamespace;

export type PlaybackMode = 'hls' | 'drm' | 'progressive';

export interface DrmServers {
  provider: string;
  widevine: string;
  playready: string;
  fairplay: string;
  fairplayCertificate: string;
}

export interface PlaybackSession {
  mode: PlaybackMode;
  manifestUrl: string;
  drm: DrmServers | null;
  expiresAt: string;
  endUrl: string;
}

/** What went wrong, so the player can pick the right message or recovery. */
export type PlaybackErrorKind = 'auth' | 'unsupported' | 'drm' | 'network' | 'media';

export class PlaybackError extends Error {
  kind: PlaybackErrorKind;
  constructor(kind: PlaybackErrorKind, message: string) {
    super(message);
    this.kind = kind;
  }
}

const MESSAGES: Record<PlaybackErrorKind, string> = {
  auth: 'Your playback session expired. Please try again.',
  unsupported:
    'This browser cannot play protected video. Please use an up-to-date Chrome, Edge, Firefox or Safari.',
  drm: 'This device could not get a playback license for this movie.',
  network: 'Could not load video. Check your connection and try again.',
  media: 'Could not play this video.',
};

export function playbackError(kind: PlaybackErrorKind) {
  return new PlaybackError(kind, MESSAGES[kind]);
}

// shaka.util.Error categories / codes used below.
const NETWORK = 1;
const DRM = 6;
const BAD_HTTP_STATUS = 1001;
const KEY_SYSTEM_UNAVAILABLE = 6001;
const LICENSE_REQUEST_FAILED = 6007;

/** Map a Shaka error to a PlaybackError. Expired or revoked sessions answer 401/403. */
export function classifyShakaError(e: unknown): PlaybackError {
  const err = e as { category?: number; code?: number; data?: unknown[] };
  const httpStatus = (code: number | undefined, data: unknown[] | undefined): number => {
    if (code === BAD_HTTP_STATUS) return Number(data?.[1]);
    // A failed license request wraps the underlying network error.
    if (code === LICENSE_REQUEST_FAILED) {
      const inner = data?.[0] as { code?: number; data?: unknown[] } | undefined;
      return inner ? httpStatus(inner.code, inner.data) : NaN;
    }
    return NaN;
  };
  const status = httpStatus(err?.code, err?.data);
  if (status === 401 || status === 403) return playbackError('auth');
  if (err?.code === KEY_SYSTEM_UNAVAILABLE) return playbackError('unsupported');
  if (err?.category === DRM) return playbackError('drm');
  if (err?.category === NETWORK) return playbackError('network');
  return playbackError('media');
}

let shakaPromise: Promise<Shaka> | null = null;
function loadShaka(): Promise<Shaka> {
  shakaPromise ??= import('shaka-player/dist/shaka-player.hls').then((m) => {
    const shaka = (m.default ?? m) as Shaka;
    shaka.polyfill.installAll();
    return shaka;
  });
  return shakaPromise;
}

const isAppleWebKit = () => /apple/i.test(navigator.vendor);

function configureDrm(shaka: Shaka, player: shakaNamespace.Player, drm: DrmServers) {
  // License URLs carry a short-lived token minted by our backend after its
  // entitlement check; no provider credentials ever reach the browser.
  player.configure({
    drm: {
      servers: {
        'com.widevine.alpha': drm.widevine,
        'com.microsoft.playready': drm.playready,
        'com.apple.fps.1_0': drm.fairplay,
      },
      advanced: {
        'com.apple.fps.1_0': { serverCertificateUri: drm.fairplayCertificate },
      },
    },
  });
  if (drm.provider === 'mux' && isAppleWebKit()) {
    // Mux's documented FairPlay integration for Shaka (legacy Apple media keys).
    shaka.polyfill.PatchedMediaKeysApple.install();
    const net = player.getNetworkingEngine();
    net?.registerRequestFilter(shaka.drm.FairPlay.muxFairPlayRequest);
    net?.registerResponseFilter(shaka.drm.FairPlay.commonFairPlayResponse);
    player.configure('drm.initDataTransform', shaka.drm.FairPlay.muxInitDataTransform);
  }
}

/**
 * Start [session] on [video] at [startAt] seconds. Resolves with a cleanup
 * function that tears the player down; errors after startup go to [onError].
 */
export async function attachStream(
  video: HTMLVideoElement,
  session: PlaybackSession,
  { startAt = 0, onError }: { startAt?: number; onError: (e: PlaybackError) => void },
): Promise<() => void> {
  if (session.mode === 'progressive') {
    video.src = session.manifestUrl;
    if (startAt) video.currentTime = startAt;
    return () => {
      video.removeAttribute('src');
      video.load();
    };
  }

  const shaka = await loadShaka();
  if (!shaka.Player.isBrowserSupported()) {
    // Older iOS has no MediaSource; its native HLS player handles AES-128 itself.
    if (session.mode === 'hls' && video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = session.manifestUrl;
      if (startAt) video.currentTime = startAt;
      return () => {
        video.removeAttribute('src');
        video.load();
      };
    }
    throw playbackError('unsupported');
  }

  const player = new shaka.Player();
  const destroy = () => {
    player.destroy().catch(() => {});
  };
  try {
    await player.attach(video);
    player.configure({
      streaming: {
        // Safari's own HLS stack is the most reliable for AES-128 and FairPlay.
        preferNativeHls: isAppleWebKit(),
        retryParameters: { maxAttempts: 3 },
      },
    });
    if (session.mode === 'drm' && session.drm) configureDrm(shaka, player, session.drm);
    player.addEventListener('error', (ev) => onError(classifyShakaError((ev as unknown as { detail: unknown }).detail)));
    await player.load(session.manifestUrl, startAt || null);
  } catch (e) {
    destroy();
    throw e instanceof PlaybackError ? e : classifyShakaError(e);
  }
  return destroy;
}

/** Tell the backend this session is over so it stops counting toward the stream limit. */
export function endSession(session: PlaybackSession) {
  if (!session.endUrl) return;
  fetch(session.endUrl, { method: 'POST', keepalive: true }).catch(() => {});
}
