import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { MovieService } from '../api/services';
import type { Movie } from '../api/types';
import { useLoad } from '../lib/app';
import { Icon } from '../components/Icon';
import { ErrorState, LoadingScreen, MovieCard } from '../components/ui';

async function loadCatalogue() {
  const [categories, movies] = await Promise.all([
    MovieService.fetchCategories(),
    MovieService.fetchMovies({ pageSize: 100 }),
  ]);
  return { categories, movies };
}

/** Same matching as the app's BrowseScreen: title, cast, director or genre. */
function matches(m: Movie, q: string) {
  return (
    m.title.toLowerCase().includes(q) ||
    m.cast.toLowerCase().includes(q) ||
    m.director.toLowerCase().includes(q) ||
    m.categoryNames.some((c) => c.toLowerCase().includes(q))
  );
}

export default function Browse() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get('q') ?? '');
  const [genre, setGenre] = useState<string | null>(null);
  const [data, loading, error, reload] = useLoad(loadCatalogue);

  useEffect(() => {
    setParams(query ? { q: query } : {}, { replace: true });
  }, [query, setParams]);

  const q = query.trim().toLowerCase();

  // Searching: flat results. "All": one row per category. A genre: that genre only.
  const view = useMemo(() => {
    if (!data) return { kind: 'grid' as const, movies: [] as Movie[] };
    const pool = genre ? data.movies.filter((m) => m.categoryNames.includes(genre)) : data.movies;
    if (q) return { kind: 'grid' as const, movies: pool.filter((m) => matches(m, q)) };
    if (genre) return { kind: 'grid' as const, movies: pool };
    const rows = data.categories
      .map((c) => [c.name, data.movies.filter((m) => m.categoryNames.includes(c.name))] as const)
      .filter(([, movies]) => movies.length > 0);
    return { kind: 'rows' as const, rows };
  }, [data, q, genre]);

  if (loading && !data) return <LoadingScreen />;
  if (error && !data) return <div className="page container"><ErrorState message={error} onRetry={reload} /></div>;

  return (
    <div className="page container">
      <div className="page-head">
        <h1>Browse</h1>
        <p>Explore the full catalogue by genre.</p>
      </div>
      <div className="search-bar">
        <Icon name="search" className="muted" />
        <input
          autoFocus
          placeholder="Search titles, directors, casts...."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search movies"
        />
        {query && (
          <button className="icon-btn" onClick={() => setQuery('')} aria-label="Clear search">
            <Icon name="close" size={18} />
          </button>
        )}
      </div>
      <div className="genre-scroll">
        <button className={`pill ${genre === null ? 'on' : ''}`} onClick={() => setGenre(null)}>
          All
        </button>
        {data!.categories.map((c) => (
          <button key={c.id} className={`pill ${genre === c.name ? 'on' : ''}`} onClick={() => setGenre(c.name)}>
            {c.name}
          </button>
        ))}
      </div>

      {view.kind === 'rows' ? (
        view.rows.length === 0 ? (
          <p className="empty">No movies found.</p>
        ) : (
          view.rows.map(([name, movies]) => (
            <section key={name} className="row-section" style={{ marginTop: 12 }}>
              <div className="row-head">
                <h2>{name}</h2>
                <span className="muted small">{movies.length} title{movies.length === 1 ? '' : 's'}</span>
              </div>
              <div className="row-scroll">
                {movies.map((m) => <MovieCard key={m.id} movie={m} />)}
              </div>
            </section>
          ))
        )
      ) : (
        <>
          <div className="row-head">
            <h2>{q ? `Results for “${query.trim()}”` : genre ?? 'Movies & TV'}</h2>
            <span className="muted small">{view.movies.length} title{view.movies.length === 1 ? '' : 's'}</span>
          </div>
          {view.movies.length === 0 ? (
            <p className="empty">No movies found.</p>
          ) : (
            <div className="grid">
              {view.movies.map((m) => <MovieCard key={m.id} movie={m} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
