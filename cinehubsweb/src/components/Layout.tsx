import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Icon } from './Icon';
import { NotificationService } from '../api/services';
import type { AppNotification } from '../api/types';

const NAV = [
  { to: '/home', label: 'Home', icon: 'home' },
  { to: '/saved', label: 'Saved', icon: 'bookmark' },
  { to: '/history', label: 'History', icon: 'playCircle' },
  { to: '/downloads', label: 'Downloads', icon: 'download' },
  { to: '/profile', label: 'Profile', icon: 'person' },
];

/**
 * Unread badge + "new notification" banner, polled every 30s like the app's
 * HomeScreen. The first poll only records what exists; later polls banner
 * anything new.
 */
function useNotificationPolling() {
  const [count, setCount] = useState(0);
  const [banner, setBanner] = useState<AppNotification | null>(null);
  const seen = useRef<Set<number> | null>(null);
  const { pathname } = useLocation();

  // Re-polls on navigation too, so the badge clears after reading notifications.
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const list = await NotificationService.fetchMyNotifications();
        if (!alive) return;
        const ids = new Set(list.map((n) => n.id));
        if (seen.current) {
          const fresh = list.filter((n) => !seen.current!.has(n.id));
          if (fresh.length) setBanner(fresh.sort((a, b) => +b.createdAt - +a.createdAt)[0]);
        }
        seen.current = ids;
        setCount(list.filter((n) => !n.isRead).length);
      } catch {
        /* keep the last known count */
      }
    };
    poll();
    const t = setInterval(poll, 30_000);
    // Refresh when the tab regains focus (e.g. after reading on another tab).
    const onFocus = () => document.visibilityState === 'visible' && poll();
    document.addEventListener('visibilitychange', onFocus);
    return () => {
      alive = false;
      clearInterval(t);
      document.removeEventListener('visibilitychange', onFocus);
    };
  }, [pathname]);

  // Auto-dismiss after 6 seconds, as in the app.
  useEffect(() => {
    if (!banner) return;
    const t = setTimeout(() => setBanner(null), 6000);
    return () => clearTimeout(t);
  }, [banner]);

  return { count, banner, dismiss: () => setBanner(null) };
}

function NotificationBanner({ notif, onOpen, onDismiss }: { notif: AppNotification; onOpen: () => void; onDismiss: () => void }) {
  return (
    <div className="notif-banner" role="alert">
      <button className="grow flex" style={{ textAlign: 'left', gap: 12 }} onClick={onOpen}>
        <span className="ic"><Icon name="bell" /></span>
        <span className="grow" style={{ minWidth: 0 }}>
          <strong style={{ display: 'block' }}>{notif.title}</strong>
          <span className="small clamp1">{notif.message}</span>
          <span className="xs gold" style={{ display: 'block' }}>Tap to view</span>
        </span>
      </button>
      <button className="icon-btn" onClick={onDismiss} aria-label="Dismiss notification">
        <Icon name="close" size={18} />
      </button>
    </div>
  );
}

export function BellButton({ count }: { count: number }) {
  return (
    <Link to="/notifications" className="icon-btn" aria-label="Notifications">
      <Icon name="bell" />
      {count > 0 && <span className="badge">{count > 9 ? '9+' : count}</span>}
    </Link>
  );
}

export function Layout() {
  const navigate = useNavigate();
  const { count: unread, banner, dismiss } = useNotificationPolling();
  return (
    <>
      {banner && (
        <NotificationBanner
          notif={banner}
          onDismiss={dismiss}
          onOpen={() => {
            dismiss();
            navigate('/notifications');
          }}
        />
      )}
      <header className="topnav">
        <div className="container">
          <Link to="/home" className="brand">
            <img src="/icon.png" alt="" />
            CINEHUBS
          </Link>
          <nav>
            {NAV.slice(0, 4).map((n) => (
              <NavLink key={n.to} to={n.to}>
                {n.label}
              </NavLink>
            ))}
            <NavLink to="/browse">Browse</NavLink>
          </nav>
          <div className="actions">
            <Link to="/browse" className="icon-btn" aria-label="Search">
              <Icon name="search" />
            </Link>
            <BellButton count={unread} />
            <NavLink to="/profile" className="icon-btn" aria-label="Profile">
              <Icon name="person" />
            </NavLink>
          </div>
        </div>
      </header>
      <Outlet context={{ unread }} />
      <nav className="bottomnav">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to}>
            <Icon name={n.icon} size={24} />
            {n.label}
          </NavLink>
        ))}
      </nav>
    </>
  );
}
