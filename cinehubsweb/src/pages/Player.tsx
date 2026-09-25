import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { MovieService } from '../api/services';
import { Icon } from '../components/Icon';
import { Spinner } from '../components/ui';

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

export default function Player() {
  const { id } = useParams();
  const movieId = Number(id);
  const [params] = useSearchParams();
  const isTrailer = params.get('trailer') === '1';
  const navigate = useNavigate();
  const shellRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [idle, setIdle] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [speedOpen, setSpeedOpen] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  // Resolve the stream URL; full movies require access (premium or paid).
  useEffect(() => {
    let alive = true;
    (async () => {
      const movie = await MovieService.fetchMovie(movieId);
      if (!alive) return;
      if (isTrailer) {
        setTitle(`${movie.title} — Trailer`);
        setSrc(movie.thrillerClipUrl || movie.trailerUrl || null);
        if (!movie.thrillerClipUrl && !movie.trailerUrl) setError('No trailer available for this title.');
        return;
      }
      setTitle(movie.title);
      const access = await MovieService.checkAccess(movieId);
      if (!alive) return;
      if (!access.allowed) {
        navigate(`/movie/${movieId}`, { replace: true, state: { movie, autoplay: true } });
        return;
      }
      const url = access.downloadUrl || movie.movieFileUrl;
      if (!url) setError('This movie file is not available yet.');
      else setSrc(url);
    })().catch((e) => alive && setError(e.message || 'Could not load video.'));
    return () => {
      alive = false;
    };
  }, [movieId, isTrailer, navigate]);

  // Report watch progress every 15s and when leaving, like the app.
  useEffect(() => {
    if (isTrailer || !src) return;
    const send = () => {
      const v = videoRef.current;
      if (v && v.currentTime > 0) MovieService.updateWatchProgress(movieId, Math.floor(v.currentTime));
    };
    const t = setInterval(send, 15_000);
    window.addEventListener('pagehide', send);
    return () => {
      clearInterval(t);
      window.removeEventListener('pagehide', send);
      send();
    };
  }, [src, isTrailer, movieId]);

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
    setLoadError(false);
    videoRef.current?.load();
    videoRef.current?.play().catch(() => {});
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

  const failed = error || loadError;

  return (
    <div ref={shellRef} className={`player ${idle ? 'idle' : ''}`}>
      <div className="bar">
        <button className="icon-btn" onClick={() => navigate(-1)} aria-label="Back">
          <Icon name="back" />
        </button>
        <strong className="grow" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</strong>
        {src && !failed && (
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
          <p className="mt8">{error ?? 'Could not load video.'}</p>
          <div className="flex mt16" style={{ justifyContent: 'center' }}>
            {loadError && (
              <button className="btn btn-primary" onClick={retry}>
                <Icon name="refresh" size={18} /> Retry
              </button>
            )}
            <button className="btn btn-ghost" style={{ color: '#fff' }} onClick={() => navigate(-1)}>Go back</button>
          </div>
        </div>
      ) : src ? (
        <>
          <video
            ref={videoRef}
            src={src}
            autoPlay
            controls
            playsInline
            controlsList="nodownload nofullscreen"
            disablePictureInPicture={false}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onRateChange={(e) => setRate(e.currentTarget.playbackRate)}
            onError={() => setLoadError(true)}
          />
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
