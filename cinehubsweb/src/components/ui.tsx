import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Icon } from './Icon';
import type { Movie } from '../api/types';

export function Spinner({ large }: { large?: boolean }) {
  return <span className={`spinner ${large ? 'lg' : ''}`} aria-label="Loading" />;
}

export function LoadingScreen() {
  return (
    <div className="loading-screen">
      <Spinner large />
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="empty">
      <Icon name="wifiOff" size={48} />
      <p>{message}</p>
      {onRetry && (
        <button className="link-btn mt16" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ icon, title, text }: { icon: string; title: string; text?: string }) {
  return (
    <div className="empty">
      <Icon name={icon} size={48} />
      <h3 style={{ color: 'var(--text)' }}>{title}</h3>
      {text && <p className="small mt8">{text}</p>}
    </div>
  );
}

export function BackBar({ title, right }: { title: string; right?: ReactNode }) {
  const navigate = useNavigate();
  return (
    <div className="auth-bar">
      <button className="icon-btn" onClick={() => navigate(-1)} aria-label="Back">
        <Icon name="back" />
      </button>
      <h1 className="grow">{title}</h1>
      {right}
    </div>
  );
}

export function PasswordInput(props: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  id?: string;
  autoComplete?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="input-wrap">
      <input
        id={props.id}
        className="input"
        type={show ? 'text' : 'password'}
        value={props.value}
        placeholder={props.placeholder}
        autoComplete={props.autoComplete}
        onChange={(e) => props.onChange(e.target.value)}
      />
      <button type="button" className="icon-btn eye" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}>
        <Icon name={show ? 'eyeOff' : 'eye'} size={20} />
      </button>
    </div>
  );
}

/** Bottom sheet on phones, centred dialog on larger screens. */
export function Sheet({ onClose, children, dismissable = true }: { onClose: () => void; children: ReactNode; dismissable?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && dismissable && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose, dismissable]);
  return (
    <div className="backdrop" onClick={() => dismissable && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="grab" />
        {children}
      </div>
    </div>
  );
}

export function ResultDialog(props: {
  ok?: boolean;
  title: string;
  text: string;
  action: string;
  onAction: () => void;
  secondary?: { label: string; onClick: () => void };
}) {
  return (
    <Sheet onClose={props.onAction} dismissable={false}>
      <div className="dialog">
        <div className={`ok-circle ${props.ok === false ? 'bad' : ''}`}>
          <Icon name={props.ok === false ? 'close' : 'check'} size={36} />
        </div>
        <h2>{props.title}</h2>
        <p>{props.text}</p>
        <button className="btn btn-primary block" onClick={props.onAction}>
          {props.action}
        </button>
        {props.secondary && (
          <button className="btn btn-ghost block mt8" onClick={props.secondary.onClick}>
            {props.secondary.label}
          </button>
        )}
      </div>
    </Sheet>
  );
}

export function Poster({ src, alt }: { src: string; alt: string }) {
  const [broken, setBroken] = useState(false);
  if (!src || broken) {
    return (
      <div className="placeholder">
        <Icon name="movie" size={32} />
      </div>
    );
  }
  return <img src={src} alt={alt} loading="lazy" onError={() => setBroken(true)} />;
}

export function MovieCard({ movie }: { movie: Movie }) {
  const meta = [movie.releaseYear, movie.runtime].filter(Boolean).join(' · ');
  return (
    <Link to={`/movie/${movie.id}`} className="card" state={{ movie }}>
      <div className="thumb">
        <Poster src={movie.thumbnailUrl} alt={movie.title} />
        <span className="play-dot">
          <Icon name="play" size={18} />
        </span>
      </div>
      <div className="t">{movie.title}</div>
      {meta && <div className="m">{meta}</div>}
    </Link>
  );
}

export function Stars({ value, size = 14 }: { value: number; size?: number }) {
  return (
    <span className="stars" aria-label={`${value} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} style={{ opacity: i <= value ? 1 : 0.25, display: 'inline-flex' }}>
          <Icon name="star" size={size} />
        </span>
      ))}
    </span>
  );
}
