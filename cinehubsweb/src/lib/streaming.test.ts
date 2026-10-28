import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { attachStream, classifyShakaError, endSession, PlaybackError, type PlaybackSession } from './streaming';

// A stand-in for Shaka Player that records what the module asks of it.
const shakaState = vi.hoisted(() => ({
  supported: true,
  players: [] as any[],
  loadError: null as unknown,
}));

vi.mock('shaka-player/dist/shaka-player.hls', () => {
  class Player {
    configured: any[] = [];
    listeners: Record<string, (e: any) => void> = {};
    requestFilters: unknown[] = [];
    responseFilters: unknown[] = [];
    attach = vi.fn(async () => {});
    load = vi.fn(async () => {
      if (shakaState.loadError) throw shakaState.loadError;
    });
    destroy = vi.fn(async () => {});
    constructor() {
      shakaState.players.push(this);
    }
    static isBrowserSupported = () => shakaState.supported;
    configure(config: unknown, value?: unknown) {
      this.configured.push(value === undefined ? config : { [config as string]: value });
      return true;
    }
    addEventListener(type: string, fn: (e: any) => void) {
      this.listeners[type] = fn;
    }
    getNetworkingEngine() {
      return {
        registerRequestFilter: (f: unknown) => this.requestFilters.push(f),
        registerResponseFilter: (f: unknown) => this.responseFilters.push(f),
      };
    }
  }
  const shaka = {
    Player,
    polyfill: { installAll: vi.fn(), PatchedMediaKeysApple: { install: vi.fn() } },
    drm: {
      FairPlay: {
        muxFairPlayRequest: 'muxRequest',
        commonFairPlayResponse: 'commonResponse',
        muxInitDataTransform: 'muxInitData',
      },
    },
  };
  return { default: shaka };
});

const hls: PlaybackSession = {
  mode: 'hls',
  manifestUrl: '/api/stream/tok/master.m3u8',
  drm: null,
  expiresAt: '',
  endUrl: '/api/stream/tok/end',
};

const drmSession: PlaybackSession = {
  ...hls,
  mode: 'drm',
  manifestUrl: 'https://stream.mux.com/pid.m3u8?token=v',
  drm: {
    provider: 'mux',
    widevine: 'https://license.mux.com/license/widevine/pid?token=d',
    playready: 'https://license.mux.com/license/playready/pid?token=d',
    fairplay: 'https://license.mux.com/license/fairplay/pid?token=d',
    fairplayCertificate: 'https://license.mux.com/appcert/fairplay/pid?token=d',
  },
};

const lastPlayer = () => shakaState.players[shakaState.players.length - 1];

beforeEach(() => {
  shakaState.supported = true;
  shakaState.players = [];
  shakaState.loadError = null;
});
afterEach(() => vi.restoreAllMocks());

describe('classifyShakaError', () => {
  it('treats 401/403 responses as an expired session', () => {
    expect(classifyShakaError({ category: 1, code: 1001, data: ['url', 403] }).kind).toBe('auth');
    // License failures wrap the HTTP error.
    const wrapped = { category: 6, code: 6007, data: [{ category: 1, code: 1001, data: ['url', 401] }] };
    expect(classifyShakaError(wrapped).kind).toBe('auth');
  });

  it('separates unsupported key systems, DRM, network and media errors', () => {
    expect(classifyShakaError({ category: 6, code: 6001 }).kind).toBe('unsupported');
    expect(classifyShakaError({ category: 6, code: 6007, data: [] }).kind).toBe('drm');
    expect(classifyShakaError({ category: 1, code: 1002 }).kind).toBe('network');
    expect(classifyShakaError({ category: 3, code: 3016 }).kind).toBe('media');
    expect(classifyShakaError(new Error('boom')).kind).toBe('media');
  });
});

describe('attachStream', () => {
  it('plays a progressive file directly and clears it on cleanup', async () => {
    const video = document.createElement('video');
    const cleanup = await attachStream(video, { ...hls, mode: 'progressive', manifestUrl: 'https://cdn/movie.mp4' }, { onError: vi.fn() });
    expect(video.getAttribute('src')).toBe('https://cdn/movie.mp4');
    expect(shakaState.players).toHaveLength(0);
    cleanup();
    expect(video.hasAttribute('src')).toBe(false);
  });

  it('loads HLS through Shaka at the resume point and destroys it on cleanup', async () => {
    const video = document.createElement('video');
    const cleanup = await attachStream(video, hls, { startAt: 42, onError: vi.fn() });
    const player = lastPlayer();
    expect(player.attach).toHaveBeenCalledWith(video);
    expect(player.load).toHaveBeenCalledWith('/api/stream/tok/master.m3u8', 42);
    expect(video.hasAttribute('src')).toBe(false);
    cleanup();
    expect(player.destroy).toHaveBeenCalled();
  });

  it('reports playback errors after startup', async () => {
    const onError = vi.fn();
    await attachStream(document.createElement('video'), hls, { onError });
    lastPlayer().listeners.error({ detail: { category: 1, code: 1001, data: ['u', 403] } });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: 'auth' }));
  });

  it('destroys the player and throws a classified error when loading fails', async () => {
    shakaState.loadError = { category: 6, code: 6001 };
    const err = await attachStream(document.createElement('video'), hls, { onError: vi.fn() }).catch((e) => e);
    expect(err).toBeInstanceOf(PlaybackError);
    expect(err.kind).toBe('unsupported');
    expect(lastPlayer().destroy).toHaveBeenCalled();
  });

  it('configures DRM license servers from the session', async () => {
    await attachStream(document.createElement('video'), drmSession, { onError: vi.fn() });
    const drm = lastPlayer().configured.find((c: any) => c.drm)?.drm;
    expect(drm.servers['com.widevine.alpha']).toBe(drmSession.drm!.widevine);
    expect(drm.servers['com.microsoft.playready']).toBe(drmSession.drm!.playready);
    expect(drm.servers['com.apple.fps.1_0']).toBe(drmSession.drm!.fairplay);
    expect(drm.advanced['com.apple.fps.1_0'].serverCertificateUri).toBe(drmSession.drm!.fairplayCertificate);
  });

  it('uses the Mux FairPlay adapters on Apple browsers', async () => {
    vi.spyOn(navigator, 'vendor', 'get').mockReturnValue('Apple Computer, Inc.');
    await attachStream(document.createElement('video'), drmSession, { onError: vi.fn() });
    const player = lastPlayer();
    expect(player.requestFilters).toEqual(['muxRequest']);
    expect(player.responseFilters).toEqual(['commonResponse']);
    expect(player.configured).toContainEqual({ 'drm.initDataTransform': 'muxInitData' });
  });

  it('falls back to native HLS when MediaSource is unavailable', async () => {
    shakaState.supported = false;
    const video = document.createElement('video');
    vi.spyOn(video, 'canPlayType').mockReturnValue('maybe');
    await attachStream(video, hls, { onError: vi.fn() });
    expect(video.getAttribute('src')).toBe('/api/stream/tok/master.m3u8');
  });

  it('refuses when neither MediaSource nor native HLS is available', async () => {
    shakaState.supported = false;
    const video = document.createElement('video');
    vi.spyOn(video, 'canPlayType').mockReturnValue('');
    await expect(attachStream(video, hls, { onError: vi.fn() })).rejects.toMatchObject({ kind: 'unsupported' });
    // DRM can't fall back to native HLS without FairPlay set up.
    vi.spyOn(video, 'canPlayType').mockReturnValue('maybe');
    await expect(attachStream(video, drmSession, { onError: vi.fn() })).rejects.toMatchObject({ kind: 'unsupported' });
  });
});

describe('endSession', () => {
  it('tells the backend the session is over, surviving page unload', () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
    endSession(hls);
    expect(fetchMock).toHaveBeenCalledWith('/api/stream/tok/end', { method: 'POST', keepalive: true });
  });
});
