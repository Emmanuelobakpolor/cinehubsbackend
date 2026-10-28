import { Link } from 'react-router-dom';
import { MovieService } from '../api/services';
import { daysLeftFrom, formatNaira, useLoad } from '../lib/app';
import { Icon } from '../components/Icon';
import { Empty, ErrorState, LoadingScreen, Poster } from '../components/ui';

function Head({ title, sub, onRefresh }: { title: string; sub: string; onRefresh?: () => void }) {
  return (
    <div className="page-head flex between">
      <div>
        <h1>{title}</h1>
        <p>{sub}</p>
      </div>
      {onRefresh && (
        <button className="icon-btn" onClick={onRefresh} aria-label="Refresh">
          <Icon name="refresh" />
        </button>
      )}
    </div>
  );
}

// ── Saved ──────────────────────────────────────────────────────────

export function Saved() {
  const [items, loading, error, reload, setItems] = useLoad(() => MovieService.fetchSaved());

  async function remove(movieId: number) {
    setItems((items ?? []).filter((i) => i.movieId !== movieId));
    try {
      await MovieService.unsaveMovie(movieId);
    } catch {
      reload();
    }
  }

  if (loading && !items) return <LoadingScreen />;
  const list = items ?? [];
  return (
    <div className="page container">
      <Head title="Movies Saved" sub={`${list.length} movie${list.length === 1 ? '' : 's'} saved in your queue`} />
      {error && !items ? (
        <ErrorState message={error} onRetry={reload} />
      ) : list.length === 0 ? (
        <Empty icon="bookmarkOutline" title="No saved movies yet." text="Tap “Save Movie” on any title to keep it here." />
      ) : (
        <div className="grid">
          {list.map((s) => (
            <div key={s.movieId} className="card">
              <Link to={`/movie/${s.movieId}`} className="thumb" style={{ display: 'block' }}>
                <Poster src={s.thumbnailUrl} alt={s.title} />
              </Link>
              <div className="flex between">
                <Link to={`/movie/${s.movieId}`} className="t grow">{s.title}</Link>
                <button className="icon-btn gold" onClick={() => remove(s.movieId)} aria-label={`Remove ${s.title} from saved`} title="Remove">
                  <Icon name="bookmark" size={20} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Watch history ──────────────────────────────────────────────────

/** Progress estimate: watch_duration / 7200 s (≈ 2-hour movie), as in the app. */
const progressOf = (seconds: number) => Math.min(1, Math.max(0, seconds / 7200));

export function History() {
  const [items, loading, error, reload] = useLoad(() => MovieService.fetchWatchHistory());

  if (loading && !items) return <LoadingScreen />;
  return (
    <div className="page container">
      <Head title="Your Watch History" sub="Titles auto-expire 10 days after first play" onRefresh={reload} />
      {error && !items ? (
        <ErrorState message="Failed to load watch history" onRetry={reload} />
      ) : !items?.length ? (
        <Empty icon="history" title="No watch history yet" />
      ) : (
        <div className="narrow" style={{ maxWidth: 820, margin: 0 }}>
          {items.map((h) => {
            const days = daysLeftFrom(h.expiresAt ? new Date(h.expiresAt) : null);
            return (
              <div key={h.id} className="list-item">
                <Link to={`/movie/${h.movieId}`} className="lthumb">
                  <Poster src={h.movieThumbnailUrl} alt={h.movieTitle} />
                </Link>
                <div className="body">
                  <Link to={`/movie/${h.movieId}`} className="t" style={{ display: 'block' }}>{h.movieTitle}</Link>
                  <div className="flex mt8" style={{ gap: 8 }}>
                    <span className={`chip ${days > 0 ? 'gold' : 'red'}`}>{days > 0 ? `${days}d left` : 'Expired'}</span>
                    {h.watchedAt && <span className="muted xs">{new Date(h.watchedAt).toLocaleDateString()}</span>}
                  </div>
                  <div className="progress"><div style={{ width: `${progressOf(h.watchDuration) * 100}%` }} /></div>
                </div>
                {days > 0 && (
                  <Link to={`/watch/${h.movieId}`} className="icon-btn" style={{ background: 'var(--primary)', color: '#fff' }} aria-label={`Continue ${h.movieTitle}`}>
                    <Icon name="play" />
                  </Link>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Downloads (paid titles) ────────────────────────────────────────

export function Downloads() {
  const [items, loading, error, reload] = useLoad(() => MovieService.fetchMyDownloads());

  if (loading && !items) return <LoadingScreen />;
  return (
    <div className="page container">
      <Head title="Your Download History" sub="Movies you've unlocked to watch on Cinehubs. Each purchase is valid for 10 days." onRefresh={reload} />
      {error && !items ? (
        <ErrorState message="Failed to load downloads" onRetry={reload} />
      ) : !items?.length ? (
        <Empty icon="downloadDone" title="No downloads yet" text="Unlock a movie to watch it here." />
      ) : (
        <div style={{ maxWidth: 820 }}>
          {items.map((d) => {
            const paid = new Date(d.paidAt);
            const days = daysLeftFrom(isNaN(paid.getTime()) ? null : new Date(paid.getTime() + 10 * 86_400_000));
            const expired = days <= 0;
            return (
              <div key={d.id} className="list-item">
                <Link to={`/movie/${d.movieId}`} className="lthumb">
                  <Poster src={d.movieThumbnailUrl} alt={d.movieTitle} />
                </Link>
                <div className="body">
                  <Link to={`/movie/${d.movieId}`} className="t" style={{ display: 'block' }}>{d.movieTitle}</Link>
                  <div className="flex wrap mt8" style={{ gap: 8 }}>
                    <span className={`chip ${expired ? 'red' : 'green'}`}>{expired ? 'Expired' : `${days}d left · Ready to watch`}</span>
                    <span className="muted xs">₦{formatNaira(d.amountPaid)}</span>
                  </div>
                </div>
                {!expired && (
                  <Link to={`/watch/${d.movieId}`} className="icon-btn" style={{ background: 'var(--primary)', color: '#fff' }} aria-label={`Play ${d.movieTitle}`}>
                    <Icon name="play" />
                  </Link>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
