import { useMemo, useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import { MovieService } from '../api/services';
import type { Movie } from '../api/types';
import { useLoad } from '../lib/app';
import { Icon } from '../components/Icon';
import { BellButton } from '../components/Layout';
import { ErrorState, LoadingScreen, MovieCard, Sheet } from '../components/ui';

async function loadHome() {
  let featured = await MovieService.fetchFeatured();
  if (!featured) featured = (await MovieService.fetchTrending())[0] ?? null;
  const categories = await MovieService.fetchCategories();
  // The app fetches these one by one; in parallel is the same data, faster.
  const rows = await Promise.all(
    categories.map(async (c) => [c.name, await MovieService.fetchMovies({ categoryId: c.id })] as const),
  );
  const byCategory = new Map<string, Movie[]>(rows.filter(([, m]) => m.length > 0));
  return { featured, byCategory };
}

const isTv = (name: string) => /tv|series|show|episode/i.test(name);

export default function Home() {
  const navigate = useNavigate();
  const { unread } = useOutletContext<{ unread: number }>();
  const [data, loading, error, reload] = useLoad(loadHome);
  const [tab, setTab] = useState(1); // 0 TV Shows, 1 Movies, 2 Categories
  const [picked, setPicked] = useState<string | null>(null);
  const [catsOpen, setCatsOpen] = useState(false);

  const visible = useMemo(() => {
    const all = data?.byCategory ?? new Map<string, Movie[]>();
    if (tab === 0) {
      const tv = new Map([...all].filter(([n]) => isTv(n)));
      return tv.size ? tv : all;
    }
    if (tab === 2 && picked && all.has(picked)) return new Map([[picked, all.get(picked)!]]);
    return all;
  }, [data, tab, picked]);

  if (loading && !data) return <LoadingScreen />;
  if (error && !data) return <div className="page container"><ErrorState message={error} onRetry={reload} /></div>;

  const featured = data!.featured;
  const genre = featured?.categoryNames[0];
  const tabs = ['TV Shows', 'Movies', tab === 2 && picked ? picked : 'Categories'];

  return (
    <div className="page flush">
      <section className="hero">
        {featured?.thumbnailUrl && <img className="bg" src={featured.thumbnailUrl} alt="" />}
        <div className="top">
          <div className="container">
            <img src="/icon.png" alt="Cinehubs" width={36} height={36} style={{ objectFit: 'contain' }} />
            <div className="flex" style={{ gap: 4 }}>
              <BellButton count={unread} />
              <Link to="/browse" className="icon-btn" aria-label="Search">
                <Icon name="search" />
              </Link>
            </div>
          </div>
        </div>
        <div className="content">
          <div className="container">
            <div className="pill-tabs">
              {tabs.map((label, i) => (
                <button
                  key={i}
                  className={`pill ${tab === i ? 'on' : ''}`}
                  onClick={() => {
                    if (i === 2) setCatsOpen(true);
                    else {
                      setTab(i);
                      setPicked(null);
                    }
                  }}
                >
                  {label}
                  {i === 2 && <Icon name="chevronDown" size={18} />}
                </button>
              ))}
            </div>
            {featured ? (
              <div className="inner">
                <h1>{featured.title}</h1>
                <div className="meta">
                  {[featured.releaseYear, genre, featured.runtime, featured.rating].filter(Boolean).join('  •  ')}
                </div>
                {featured.synopsis && <p className="syn">{featured.synopsis}</p>}
                <div className="btns">
                  <button className="btn btn-primary" onClick={() => navigate(`/movie/${featured.id}`, { state: { movie: featured, autoplay: true } })}>
                    <Icon name="play" /> Play Movie
                  </button>
                  <Link to={`/movie/${featured.id}`} state={{ movie: featured }} className="btn btn-ghost" style={{ background: 'color-mix(in srgb, var(--bg) 60%, transparent)' }}>
                    <Icon name="info" /> More info
                  </Link>
                </div>
              </div>
            ) : (
              <h1>Welcome to Cinehubs</h1>
            )}
          </div>
        </div>
      </section>

      <div className="container">
        {visible.size === 0 && <p className="empty">No movies found in this category.</p>}
        {[...visible].map(([name, movies]) => (
          <section key={name} className="row-section">
            <div className="row-head">
              <h2>{name}</h2>
              <span className="muted small">
                {movies.length} title{movies.length === 1 ? '' : 's'}
              </span>
            </div>
            <div className="row-scroll">
              {movies.map((m) => (
                <MovieCard key={m.id} movie={m} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {catsOpen && (
        <Sheet onClose={() => setCatsOpen(false)}>
          <div className="flex between mb16">
            <div>
              <h2>Browse</h2>
              <p className="muted small">{data!.byCategory.size} genres available</p>
            </div>
            <button className="icon-btn" onClick={() => setCatsOpen(false)} aria-label="Close">
              <Icon name="close" />
            </button>
          </div>
          <div className="menu">
            <button
              className="menu-item"
              onClick={() => {
                setTab(2);
                setPicked(null);
                setCatsOpen(false);
              }}
            >
              <span className="ic"><Icon name="apps" /></span>
              <span className="tx">All Categories</span>
              {tab === 2 && !picked && <Icon name="check" className="gold" />}
            </button>
            {[...data!.byCategory].map(([name, movies]) => (
              <button
                key={name}
                className="menu-item"
                onClick={() => {
                  setTab(2);
                  setPicked(name);
                  setCatsOpen(false);
                }}
              >
                <span className="tx">
                  {name}
                  <small>
                    {movies.length} title{movies.length === 1 ? '' : 's'}
                  </small>
                </span>
                {picked === name ? <Icon name="check" className="gold" /> : <Icon name="chevronRight" />}
              </button>
            ))}
          </div>
        </Sheet>
      )}
    </div>
  );
}
