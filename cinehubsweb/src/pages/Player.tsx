import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { MovieService, UserService } from '../api/services';
import { useCaptureGuard } from '../lib/captureGuard';
import { Icon } from '../components/Icon';
import { Spinner } from '../components/ui';
import { attachStream, endSession, playbackError, type PlaybackError, type PlaybackSession } from '../lib/streaming';

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

/** Public trailers play straight from their file; full movies only through an authorized session. */
type Source = { kind: 'file'; url: string } | { kind: 'session'; session: PlaybackSession; startAt: number };

export default function Player() {
  const { id } = useParams();
  const movieId = Number(id);
  const [params] = useSearchParams();
  const isTrailer = params.get('trailer') === '1';
  const navigate = useNavigate();
  const shellRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [title, setTitle] = useState('');
  // error: nothing to retry (no access, no file). loadError: playback failed; Retry is offered.
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Bumped to ask the backend for a fresh playback session.
  const [attempt, setAttempt] = useState(0);
  const resumeAt = useRef(0);
  const autoRetries = useRef(0);
  const [idle, setIdle] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [speedOpen, setSpeedOpen] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [viewer, setViewer] = useState('');
  const [markPos, setMarkPos] = useState({ x: 10, y: 15 });

  // Blank the picture whenever a capture is likely; the viewer taps to resume.
  const pauseVideo = useCallback(() => videoRef.current?.pause(), []);
  const { shielded, unshield } = useCaptureGuard(pauseVideo);
  const resume = () => {
    unshield();
    videoRef.current?.play().catch(() => {});
  };

  // Watermark full movies with who is watching, so leaked recordings can be traced.
  useEffect(() => {
    if (isTrailer) return;
    UserService.getProfile()
      .then((p) => setViewer(p.email || `User #${p.id}`))
      .catch(() => {});
  }, [isTrailer]);

  // Move the watermark every 8s so it can't simply be cropped or blurred out.
  useEffect(() => {
    if (!viewer) return;
    const move = () => setMarkPos({ x: 5 + Math.random() * 60, y: 12 + Math.random() * 70 });
    const t = setInterval(move, 8000);
    return () => clearInterval(t);
  }, [viewer]);

  // Resolve what to play. Full movies need a playback session, which the backend
  // only grants after checking access (premium or paid) on its side.
  useEffect(() => {
    let alive = true;
    (async () => {
      const movie = await MovieService.fetchMovie(movieId);
      if (!alive) return;
      if (isTrailer) {
        setTitle(`${movie.title} — Trailer`);
        const url = movie.thrillerClipUrl || movie.trailerUrl;
        if (url) setSource({ kind: 'file', url });
        else setError('No trailer available for this title.');
        return;
      }
      setTitle(movie.title);
      const res = await MovieService.startPlayback(movieId);
      if (!alive) return;
      if (res.status === 'payment_required') {
        navigate(`/movie/${movieId}`, { replace: true, state: { movie, autoplay: true } });
        return;
      }
      setSource({ kind: 'session', session: res.session, startAt: resumeAt.current });
    })().catch((e) => alive && setError(e.message || 'Could not load video.'));
    return () => {
      alive = false;
    };
  }, [movieId, isTrailer, navigate, attempt]);

  // An expired session or dropped connection gets one automatic fresh session,
  // resuming where the viewer was; after that, show the error with Retry.
  const onStreamError = useCallback((e: PlaybackError) => {
    if ((e.kind === 'auth' || e.kind === 'network') && autoRetries.current < 1) {
      autoRetries.current += 1;
      setAttempt((a) => a + 1);
      return;
    }
    setLoadError(e.message);
  }, []);

  const failed = !!(error || loadError);

  // Start the authorized stream on the <video>, and tear it down (ending the
  // backend session) when the session changes, playback fails or we leave.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || failed || source?.kind !== 'session') return;
    const { session, startAt } = source;
    let disposed = false;
    let teardown: (() => void) | null = null;
    // Closing the tab or a full page load never unmounts React, so end the session here too.
    const onPageHide = () => endSession(session);
    window.addEventListener('pagehide', onPageHide);
    attachStream(video, session, { startAt, onError: onStreamError })
      .then((destroy) => {
        if (disposed) return destroy();
        teardown = destroy;
        video.play().catch(() => {});
      })
      .catch((e) => !disposed && onStreamError(e));
    return () => {
      disposed = true;
      window.removeEventListener('pagehide', onPageHide);
      teardown?.();
      endSession(session);
    };
  }, [source, failed, onStreamError]);

  // Report watch progress every 15s and when leaving, like the app.
  useEffect(() => {
    // Hold the element itself: React clears videoRef before this cleanup runs on leave.
    const v = videoRef.current;
    if (isTrailer || !source || !v) return;
    const send = () => {
      if (v.currentTime > 0) MovieService.updateWatchProgress(movieId, Math.floor(v.currentTime));
    };
    const t = setInterval(send, 15_000);
    window.addEventListener('pagehide', send);
    return () => {
      clearInterval(t);
      window.removeEventListener('pagehide', send);
      send();
    };
  }, [source, isTrailer, movieId]);

  // Keep the screen awake while playing (the app uses wakelock_plus).
  useEffect(() => {
    if (!playing || !('wakeLock' in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    let cancelled = false;
    const acquire = () =>
      navigator.wakeLock
        .request('screen')
        .then((l) => {
          if (cancelled) l.release();
          else lock = l;
        })
        .catch(() => {});
    acquire();
    // The browser drops the lock when the tab is hidden; take it back on return.
    const onVisible = () => document.visibilityState === 'visible' && acquire();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
      lock?.release().catch(() => {});
    };
  }, [playing]);

  // Auto-hide controls after 3s of no activity while playing.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const wake = () => {
      setIdle(false);
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (videoRef.current && !videoRef.current.paused) {
          setIdle(true);
          setSpeedOpen(false);
        }
      }, 3000);
    };
    wake();
    window.addEventListener('mousemove', wake);
    window.addEventListener('touchstart', wake);
    window.addEventListener('keydown', wake);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('mousemove', wake);
      window.removeEventListener('touchstart', wake);
      window.removeEventListener('keydown', wake);
    };
  }, []);

  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const skip = (s: number) => {
    const v = videoRef.current;
    if (v) v.currentTime = Math.max(0, Math.min(v.duration || Infinity, v.currentTime + s));
  };
  const togglePlay = () => {
    const v = videoRef.current;
    if (v) v.paused ? v.play() : v.pause();
  };
  // Fullscreen the whole player so our controls stay visible.
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else shellRef.current?.requestFullscreen().catch(() => {});
  };
  const chooseRate = (r: number) => {
    if (videoRef.current) videoRef.current.playbackRate = r;
    setRate(r);
    setSpeedOpen(false);
  };
  const retry = () => {
    setLoadError(null);
    autoRetries.current = 0;
    if (source?.kind === 'file') {
      videoRef.current?.load();
      videoRef.current?.play().catch(() => {});
    } else {
      setSource(null); // the old session has ended; wait for a fresh one
      setAttempt((a) => a + 1);
    }
  };
  const onVideoError = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    // With MediaSource (a blob: URL) Shaka reports the failure itself.
    if (e.currentTarget.currentSrc.startsWith('blob:')) return;
    if (source?.kind === 'session') onStreamError(playbackError('network'));
    else setLoadError('Could not load video.');
  };

  // Keyboard: ←/→ skip 10s, space play/pause, F fullscreen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') skip(10);
      else if (e.key === 'ArrowLeft') skip(-10);
      else if (e.key === ' ' && document.activeElement !== videoRef.current) {
        e.preventDefault();
        togglePlay();
      } else if (e.key.toLowerCase() === 'f') toggleFullscreen();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div ref={shellRef} className={`player ${idle ? 'idle' : ''}`}>
      <div className="bar">
        <button className="icon-btn" onClick={() => navigate(-1)} aria-label="Back">
          <Icon name="back" />
        </button>
        <strong className="grow" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</strong>
        {source && !failed && (
          <>
            <div style={{ position: 'relative' }}>
              <button className="speed-btn" onClick={() => setSpeedOpen(!speedOpen)} aria-label="Playback speed" aria-expanded={speedOpen}>
                {rate}x
              </button>
              {speedOpen && (
                <div className="speed-menu" role="menu">
                  {SPEEDS.map((s) => (
                    <button key={s} role="menuitemradio" aria-checked={s === rate} className={s === rate ? 'on' : ''} onClick={() => chooseRate(s)}>
                      {s}x
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button className="icon-btn" onClick={toggleFullscreen} aria-label={fullscreen ? 'Exit full screen' : 'Full screen'}>
              <Icon name={fullscreen ? 'fullscreenExit' : 'fullscreen'} />
            </button>
          </>
        )}
      </div>

      {failed ? (
        <div className="center" style={{ color: '#fff', padding: 24 }}>
          <Icon name="info" size={40} />
          <p className="mt8" role="alert">{error ?? loadError}</p>
          <div className="flex mt16" style={{ justifyContent: 'center' }}>
            {loadError && (
              <button className="btn btn-primary" onClick={retry}>
                <Icon name="refresh" size={18} /> Retry
              </button>
            )}
            <button className="btn btn-ghost" style={{ color: '#fff' }} onClick={() => navigate(-1)}>Go back</button>
          </div>
        </div>
      ) : source ? (
        <>
          <video
            ref={videoRef}
            src={source.kind === 'file' ? source.url : undefined}
            autoPlay
            controls
            playsInline
            controlsList="nodownload nofullscreen noremoteplayback"
            disablePictureInPicture
            disableRemotePlayback
            onContextMenu={(e) => e.preventDefault()}
            onPlay={() => setPlaying(true)}
            onPlaying={() => {
              autoRetries.current = 0;
            }}
            onTimeUpdate={(e) => {
              // Where a fresh session resumes from after an expiry or Retry.
              if (e.currentTarget.currentTime > 0) resumeAt.current = e.currentTarget.currentTime;
            }}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onRateChange={(e) => setRate(e.currentTarget.playbackRate)}
            onError={onVideoError}
          />
          {viewer && (
            <div className="watermark" style={{ left: `${markPos.x}%`, top: `${markPos.y}%` }} aria-hidden>
              {viewer}
            </div>
          )}
          {shielded && (
            <button className="capture-shield" onClick={resume}>
              <Icon name="lock" size={36} />
              <span>Playback paused to protect this content</span>
              <small>Click to resume</small>
            </button>
          )}
          <div className="center-controls">
            <button onClick={() => skip(-10)} aria-label="Back 10 seconds"><Icon name="replay10" size={40} /></button>
            <button className="big" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
              <Icon name={playing ? 'pause' : 'play'} size={48} />
            </button>
            <button onClick={() => skip(10)} aria-label="Forward 10 seconds"><Icon name="forward10" size={40} /></button>
          </div>
        </>
      ) : (
        <span style={{ color: 'var(--primary)' }}><Spinner large /></span>
      )}
    </div>
  );
}
