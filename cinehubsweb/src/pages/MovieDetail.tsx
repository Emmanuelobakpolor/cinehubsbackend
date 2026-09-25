import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { MovieService, PaymentService, ReviewService, PLAN_BASIC } from '../api/services';
import type { Movie, Review } from '../api/types';
import { formatNaira, useApp, useLoad } from '../lib/app';
import { Icon } from '../components/Icon';
import { ErrorState, LoadingScreen, MovieCard, ResultDialog, Sheet, Spinner, Stars } from '../components/ui';

/** Ask Cloudinary to serve the file as an attachment so the browser saves it. */
export function attachmentUrl(url: string) {
  return url.includes('res.cloudinary.com') && url.includes('/upload/') && !url.includes('fl_attachment')
    ? url.replace('/upload/', '/upload/fl_attachment/')
    : url;
}

export function triggerDownload(url: string) {
  const a = document.createElement('a');
  a.href = attachmentUrl(url);
  a.rel = 'noopener';
  a.target = '_blank';
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default function MovieDetail() {
  const { id } = useParams();
  const movieId = Number(id);
  const location = useLocation();
  const passed = (location.state as { movie?: Movie; autoplay?: boolean } | null) ?? {};
  const [movie, loading, error, reload] = useLoad<Movie>(
    () => (passed.movie?.id === movieId ? Promise.resolve(passed.movie) : MovieService.fetchMovie(movieId)),
    [movieId],
  );

  if (loading && !movie) return <LoadingScreen />;
  if (error || !movie) return <div className="page container"><ErrorState message={error ?? 'Movie not found'} onRetry={reload} /></div>;
  return <Detail key={movie.id} movie={movie} autoplay={!!passed.autoplay} />;
}

function Detail({ movie: m, autoplay }: { movie: Movie; autoplay: boolean }) {
  const navigate = useNavigate();
  const { toast } = useApp();

  const [access, setAccess] = useState<{ allowed: boolean; amount: string } | null>(null);
  const [paywall, setPaywall] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [similar, setSimilar] = useState<Movie[]>([]);
  const [rateOpen, setRateOpen] = useState(false);
  const [rated, setRated] = useState(false);
  const [castOpen, setCastOpen] = useState(false);

  async function checkAccess() {
    try {
      const r = await MovieService.checkAccess(m.id);
      setAccess(r);
      return r;
    } catch {
      const r = { allowed: false, amount: '200.00' };
      setAccess(r);
      return r;
    }
  }

  useEffect(() => {
    checkAccess().then((r) => {
      if (autoplay) r.allowed ? navigate(`/watch/${m.id}`) : setPaywall(true);
    });
    ReviewService.fetchReviews(m.id).then(setReviews).catch(() => {});
    MovieService.fetchSaved()
      .then((list) => setSaved(list.some((s) => s.movieId === m.id)))
      .catch(() => {});
    (async () => {
      const first = m.categoryNames[0];
      if (!first) return;
      const cat = (await MovieService.fetchCategories()).find((c) => c.name === first);
      if (!cat) return;
      const movies = await MovieService.fetchMovies({ categoryId: cat.id });
      setSimilar(movies.filter((x) => x.id !== m.id));
    })().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m.id]);

  async function toggleSave() {
    if (saving) return;
    setSaving(true);
    try {
      if (saved) {
        await MovieService.unsaveMovie(m.id);
        setSaved(false);
      } else {
        await MovieService.saveMovie(m.id);
        setSaved(true);
        toast('Saved — Video added to your saved list', 'gold', 2000);
      }
    } catch {
      /* silent, like the app */
    } finally {
      setSaving(false);
    }
  }

  async function download() {
    if (!access?.allowed) return setPaywall(true);
    setDownloading(true);
    try {
      const url = (await MovieService.confirmMoviePayment(m.id)) || m.movieFileUrl;
      if (!url) throw new Error('No download URL');
      triggerDownload(url);
      toast('Download started — check your browser downloads', 'gold');
    } catch (e) {
      toast(`Download failed: ${(e as Error).message}`, 'red', 6000);
    } finally {
      setDownloading(false);
    }
  }

  const genre = m.categoryNames.join(', ');
  const castList = m.cast.split(',').map((c) => c.trim()).filter(Boolean);

  return (
    <div className="page flush">
      <Trailer movie={m} onBack={() => navigate(-1)} />
      <div className="container">
        <div className="detail-grid">
          <div>
            <h1 style={{ fontSize: 'clamp(26px, 4vw, 40px)' }}>{m.title}</h1>
            <p className="muted small mt8">
              {[m.releaseYear, m.categoryNames[0], m.runtime, m.rating].filter(Boolean).join('  •  ')}
            </p>
            {m.synopsis && <p className="mt16" style={{ maxWidth: 720 }}>{m.synopsis}</p>}

            <div className="detail-actions">
              <button
                className="btn btn-primary span2"
                disabled={!access}
                onClick={() => (access?.allowed ? navigate(`/watch/${m.id}`) : setPaywall(true))}
              >
                {!access ? <Spinner /> : <Icon name={access.allowed ? 'play' : 'lock'} />}
                {!access ? 'Checking...' : 'Play'}
              </button>
              <button className="btn btn-dark" onClick={download} disabled={!access || downloading}>
                {downloading ? <Spinner /> : <Icon name="download" />}
                {downloading ? 'Preparing...' : 'Download Movie'}
              </button>
              <button className="btn btn-ghost" onClick={toggleSave} disabled={saving}>
                <Icon name={saved ? 'bookmark' : 'bookmarkOutline'} className={saved ? 'gold' : ''} />
                {saved ? 'Saved' : 'Save Movie'}
              </button>
            </div>

            <section className="mt24">
              <h2>Movie details</h2>
              <div className="mt8">
                {m.director && (
                  <div className="kv"><span className="k">Director</span><span>{m.director}</span></div>
                )}
                {castList.length > 0 && (
                  <div className="kv">
                    <span className="k">Cast</span>
                    <span>
                      {(castOpen ? castList : castList.slice(0, 3)).join(', ')}
                      {castList.length > 3 && (
                        <button className="link-btn small" style={{ marginLeft: 8 }} onClick={() => setCastOpen(!castOpen)}>
                          {castOpen ? 'View less' : 'View more cast'}
                        </button>
                      )}
                    </span>
                  </div>
                )}
                {genre && <div className="kv"><span className="k">Genre</span><span>{genre}</span></div>}
                {m.rating && <div className="kv"><span className="k">Rating</span><span>{m.rating}</span></div>}
              </div>
            </section>
          </div>

          <aside className="panel" style={{ alignSelf: 'start' }}>
            <div className="flex between">
              <h2 className="flex" style={{ gap: 8 }}>
                {reviews.length ? `Reviews (${reviews.length})` : 'Reviews'}
                <span className="flex small gold" style={{ gap: 2 }}>
                  <Icon name="star" size={16} />
                  <span style={{ color: 'var(--text)' }}>{m.rating || '—'}</span>
                </span>
              </h2>
              <button className="btn btn-outline sm" onClick={() => setRateOpen(true)}>
                <Icon name="star" size={18} /> Rate Movie
              </button>
            </div>
            {reviews.length === 0 ? (
              <p className="muted small mt16">No reviews yet. Be the first to rate this movie.</p>
            ) : (
              <div className="mt8" style={{ maxHeight: 460, overflowY: 'auto' }}>
                {reviews.map((r) => (
                  <div key={r.id} className="review">
                    <div className="flex">
                      <span className="avatar">{(r.username || '?')[0].toUpperCase()}</span>
                      <div className="grow">
                        <strong className="small">{r.username || 'User'}</strong>
                        <div className="flex" style={{ gap: 6 }}>
                          <Stars value={r.rating} size={13} />
                          <span className="muted xs">{r.createdAt ? new Date(r.createdAt).toLocaleDateString() : ''}</span>
                        </div>
                      </div>
                    </div>
                    {r.comment && <p className="small mt8">{r.comment}</p>}
                  </div>
                ))}
              </div>
            )}
          </aside>
        </div>

        {similar.length > 0 && (
          <section className="row-section">
            <div className="row-head">
              <h2>Similar Movie Genre</h2>
            </div>
            <div className="row-scroll">
              {similar.map((s) => (
                <MovieCard key={s.id} movie={s} />
              ))}
            </div>
          </section>
        )}
      </div>

      {paywall && access && (
        <Paywall
          movie={m}
          amount={access.amount}
          onClose={() => setPaywall(false)}
        />
      )}
      {rateOpen && (
        <RatingSheet
          onClose={() => setRateOpen(false)}
          onSubmit={async (rating, comment) => {
            try {
              const review = await ReviewService.submitReview(m.id, rating, comment);
              setReviews((r) => [review, ...r]);
              setRateOpen(false);
              setRated(true);
            } catch (e) {
              setRateOpen(false);
              toast((e as Error).message, 'red');
            }
          }}
        />
      )}
      {rated && (
        <ResultDialog
          title="Rating Submitted"
          text="Thank you for your feedback this helps us improve our services"
          action="Okay, got it"
          onAction={() => setRated(false)}
        />
      )}
    </div>
  );
}

/** Autoplaying muted trailer (thriller clip first), poster as fallback. */
function Trailer({ movie, onBack }: { movie: Movie; onBack: () => void }) {
  const src = movie.thrillerClipUrl || movie.trailerUrl;
  const ref = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
  const [paused, setPaused] = useState(false);
  const [failed, setFailed] = useState(false);
  const navigate = useNavigate();

  function togglePause() {
    const v = ref.current;
    if (!v) return;
    if (v.paused) {
      v.play();
      setPaused(false);
    } else {
      v.pause();
      setPaused(true);
    }
  }

  return (
    <div className="detail-hero">
      <button className="back" onClick={onBack} aria-label="Back">
        <Icon name="back" />
      </button>
      {src && !failed ? (
        <>
          <video
            ref={ref}
            src={src}
            poster={movie.thumbnailUrl || undefined}
            autoPlay
            muted={muted}
            loop
            playsInline
            onClick={togglePause}
            onError={() => setFailed(true)}
          />
          <span className="badge-tr">TRAILER</span>
          <div className="ctrls">
            <button onClick={togglePause} aria-label={paused ? 'Play trailer' : 'Pause trailer'}>
              <Icon name={paused ? 'play' : 'pause'} />
            </button>
            <button onClick={() => setMuted(!muted)} aria-label={muted ? 'Unmute' : 'Mute'}>
              <Icon name={muted ? 'volumeOff' : 'volumeOn'} />
            </button>
            <button onClick={() => navigate(`/watch/${movie.id}?trailer=1`)} aria-label="Watch trailer full screen">
              <Icon name="playCircle" />
            </button>
          </div>
        </>
      ) : movie.thumbnailUrl ? (
        <img src={movie.thumbnailUrl} alt="" />
      ) : null}
    </div>
  );
}

function Paywall({ movie, amount, onClose }: { movie: Movie; amount: string; onClose: () => void }) {
  const navigate = useNavigate();
  const { toast } = useApp();
  const [paying, setPaying] = useState(false);

  async function payPerMovie() {
    setPaying(true);
    try {
      // Leaves the site for Flutterwave; /payment/callback finishes the unlock.
      await PaymentService.startCheckout({
        planId: PLAN_BASIC,
        planName: 'Basic Movie',
        movieId: movie.id,
        movieTitle: movie.title,
      });
    } catch (e) {
      setPaying(false);
      toast(`Could not initiate payment: ${(e as Error).message}`, 'red', 5000);
    }
  }

  return (
    <Sheet onClose={onClose}>
      <div className="flex between">
        <div>
          <h2>Get Access</h2>
          <p className="muted small">{movie.title}</p>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close">
          <Icon name="close" />
        </button>
      </div>
      <button className="plan-card featured mt16" style={{ width: '100%', textAlign: 'left' }} onClick={() => navigate('/subscription')}>
        <div className="flex">
          <span className="ic" style={{ color: 'var(--primary)' }}><Icon name="crown" size={28} /></span>
          <div className="grow">
            <strong>Subscribe to PREMIUM</strong>
            <p className="muted small">₦5,500/mo · Unlimited access to all movies</p>
          </div>
          <Icon name="chevronRight" />
        </div>
      </button>
      <div className="flex mt16 mb16" style={{ gap: 12 }}>
        <hr className="grow" style={{ border: 0, borderTop: '1px solid var(--divider)' }} />
        <span className="muted xs">OR</span>
        <hr className="grow" style={{ border: 0, borderTop: '1px solid var(--divider)' }} />
      </div>
      <button className="btn btn-primary block" onClick={payPerMovie} disabled={paying}>
        {paying ? <Spinner /> : `Pay ₦${formatNaira(amount)} for this movie`}
      </button>
      <p className="muted xs center mt8">One-time payment · Valid for 10 days</p>
    </Sheet>
  );
}

const TAGS = ['Reliable', 'Fast', 'Good Service', 'Nice Story', 'Not Good', 'Poor Service'];

function RatingSheet({ onClose, onSubmit }: { onClose: () => void; onSubmit: (rating: number, comment: string) => Promise<void> }) {
  const [rating, setRating] = useState(4);
  const [tags, setTags] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    const comment = [tags.join(', '), text.trim()].filter(Boolean).join(' — ');
    await onSubmit(rating, comment);
    setBusy(false);
  }

  return (
    <Sheet onClose={onClose}>
      <h2 className="center">Rate Movie</h2>
      <div className="stars big center mt16" style={{ display: 'flex', justifyContent: 'center' }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <button key={i} className={i <= rating ? 'on' : ''} onClick={() => setRating(i)} aria-label={`${i} star${i > 1 ? 's' : ''}`}>
            <Icon name="star" size={36} />
          </button>
        ))}
      </div>
      <div className="tags mt16" style={{ justifyContent: 'center' }}>
        {TAGS.map((t) => (
          <button key={t} className={`tag ${tags.includes(t) ? 'on' : ''}`} onClick={() => setTags((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))}>
            {t}
          </button>
        ))}
      </div>
      <textarea className="input mt16" placeholder="Write Review (Optional)" value={text} onChange={(e) => setText(e.target.value)} />
      <button className="btn btn-primary block mt16" onClick={submit} disabled={busy}>
        {busy ? <Spinner /> : 'Submit'}
      </button>
    </Sheet>
  );
}
