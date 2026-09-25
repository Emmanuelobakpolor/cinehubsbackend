import { NotificationService } from '../api/services';
import type { AppNotification } from '../api/types';
import { useLoad } from '../lib/app';
import { Icon } from '../components/Icon';
import { BackBar, Empty, ErrorState, LoadingScreen } from '../components/ui';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function timeAgo(dt: Date) {
  const mins = Math.floor((Date.now() - dt.getTime()) / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${dt.getDate()} ${MONTHS[dt.getMonth()]} ${dt.getFullYear()}`;
}

const audienceLabel = (a: string) => (a === 'PREMIUM' ? 'Premium' : a === 'BASIC' ? 'Basic' : 'All users');

function group(list: AppNotification[]) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today.getTime() - 86_400_000);
  const groups: Record<string, AppNotification[]> = { Today: [], Yesterday: [], Earlier: [] };
  for (const n of list) {
    if (n.createdAt >= today) groups.Today.push(n);
    else if (n.createdAt >= yesterday) groups.Yesterday.push(n);
    else groups.Earlier.push(n);
  }
  return Object.entries(groups).filter(([, v]) => v.length);
}

export default function Notifications() {
  const [list, loading, error, reload, setList] = useLoad(() => NotificationService.fetchMyNotifications());

  function markAll() {
    if (!list) return;
    NotificationService.markAllAsRead(list.map((n) => n.id));
    setList(list.map((n) => ({ ...n, isRead: true })));
  }

  function open(n: AppNotification) {
    NotificationService.markAsRead(n.id);
    setList((list ?? []).map((x) => (x.id === n.id ? { ...x, isRead: true } : x)));
  }

  if (loading && !list) return <LoadingScreen />;
  const hasUnread = list?.some((n) => !n.isRead);

  return (
    <div className="page container">
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <BackBar
          title="Notifications"
          right={hasUnread ? <button className="link-btn small" onClick={markAll}>Mark all read</button> : undefined}
        />
        {error && !list ? (
          <ErrorState message="Could not load notifications." onRetry={reload} />
        ) : !list?.length ? (
          <Empty icon="bell" title="No notifications yet" text="When the admin sends a broadcast, it will appear here." />
        ) : (
          group(list).map(([label, items]) => (
            <section key={label} className="mb16">
              <div className="section-label">{label}</div>
              {items.map((n) => (
                <button key={n.id} className={`notif ${n.isRead ? '' : 'unread'}`} onClick={() => open(n)}>
                  <span className="ic"><Icon name="bell" /></span>
                  <span className="grow">
                    <strong style={{ display: 'block' }}>{n.title}</strong>
                    <span className="small" style={{ display: 'block', color: 'var(--text-2)' }}>{n.message}</span>
                    <span className="flex mt8" style={{ gap: 8 }}>
                      <span className="chip">{audienceLabel(n.targetAudience)}</span>
                      <span className="muted xs">{timeAgo(n.createdAt)}</span>
                    </span>
                  </span>
                  {!n.isRead && <span className="dot" />}
                </button>
              ))}
            </section>
          ))
        )}
      </div>
    </div>
  );
}
