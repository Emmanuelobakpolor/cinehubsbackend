import { useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthService, PaymentService, UserService } from '../api/services';
import type { UserProfile } from '../api/types';
import { useApp, useLoad } from '../lib/app';
import { Icon } from '../components/Icon';
import { BackBar, ErrorState, LoadingScreen, PasswordInput, Sheet, Spinner } from '../components/ui';

function Avatar({ profile, size = 88 }: { profile: UserProfile | null; size?: number }) {
  const initial = (profile?.fullName || profile?.email || '?')[0].toUpperCase();
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size / 2.6 }}>
      {profile?.profilePictureUrl ? <img src={profile.profilePictureUrl} alt="" /> : initial}
    </span>
  );
}

function MenuItem({ icon, title, sub, onClick, to, danger }: { icon: string; title: string; sub?: string; onClick?: () => void; to?: string; danger?: boolean }) {
  const inner = (
    <>
      <span className="ic" style={danger ? { color: 'var(--error)' } : undefined}><Icon name={icon} /></span>
      <span className="tx" style={danger ? { color: 'var(--error)' } : undefined}>
        {title}
        {sub && <small>{sub}</small>}
      </span>
      {!danger && <Icon name="chevronRight" className="muted" />}
    </>
  );
  return to ? <Link to={to} className="menu-item">{inner}</Link> : <button className="menu-item" onClick={onClick}>{inner}</button>;
}

export function ThemeToggle() {
  const { theme, setTheme } = useApp();
  return (
    <div className="seg" role="group" aria-label="Theme">
      <button className={theme === 'light' ? 'on' : ''} onClick={() => setTheme('light')}><Icon name="sun" size={18} /> Light</button>
      <button className={theme === 'dark' ? 'on' : ''} onClick={() => setTheme('dark')}><Icon name="moon" size={18} /> Dark</button>
    </div>
  );
}

// ── Profile ────────────────────────────────────────────────────────

export function Profile() {
  const navigate = useNavigate();
  const [profile, loading, error, reload] = useLoad(() => UserService.getProfile());
  const [sub] = useLoad(() => PaymentService.activeSubscription());
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  async function logout() {
    setLoggingOut(true);
    await AuthService.logout();
    navigate('/signin', { replace: true });
  }

  if (loading && !profile) return <LoadingScreen />;
  if (error && !profile) return <div className="page container"><ErrorState message={error} onRetry={reload} /></div>;
  const p = profile!;

  return (
    <div className="page container">
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <div className="page-head flex between">
          <h1>Profile</h1>
          <button className="icon-btn" onClick={reload} aria-label="Refresh"><Icon name="refresh" /></button>
        </div>

        <div className="panel flex" style={{ gap: 16 }}>
          <Avatar profile={p} />
          <div className="grow" style={{ minWidth: 0 }}>
            <h2>{p.fullName || 'Loading...'}</h2>
            <p className="muted small" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.email}</p>
            <div className="flex wrap mt8" style={{ gap: 6 }}>
              <span className={`chip ${p.isEmailVerified ? 'green' : 'red'}`}>{p.isEmailVerified ? 'Verified' : 'Unverified'}</span>
              <span className="chip gold">{sub ? `${sub.planName} plan` : 'BASIC · pay per movie'}</span>
            </div>
          </div>
          <Link to="/profile/edit" className="btn btn-outline sm"><Icon name="edit" size={18} /> Edit</Link>
        </div>

        {!p.isEmailVerified && (
          <button
            className="alert mt16"
            style={{ width: '100%', textAlign: 'left' }}
            onClick={async () => {
              await AuthService.resendEmailOtp().catch(() => {});
              navigate(`/verify?mode=signup&email=${encodeURIComponent(p.email)}`);
            }}
          >
            Your email isn&apos;t verified yet. <strong>Verify now →</strong>
          </button>
        )}

        <div className="stats mt16">
          <div className="stat"><b>{p.watchedCount}</b><span>Watched</span></div>
          <div className="stat"><b>{p.savedCount}</b><span>Saved</span></div>
          <div className="stat"><b>{p.reviewsCount}</b><span>Reviews</span></div>
        </div>

        {p.bio && (
          <>
            <div className="section-label">Bio</div>
            <p className="panel small">{p.bio}</p>
          </>
        )}

        <div className="section-label">Appearance</div>
        <ThemeToggle />

        <div className="section-label">Account</div>
        <div className="menu">
          <MenuItem icon="crown" title="Subscription" sub={sub ? `Active until ${new Date(sub.endDate).toLocaleDateString()}` : 'Upgrade to PREMIUM'} to="/subscription" />
          <MenuItem icon="settings" title="Settings" to="/settings" />
          <MenuItem icon="support" title="Customer Support" to="/support" />
          <MenuItem icon="logout" title="Log Out" onClick={() => setConfirmLogout(true)} danger />
        </div>
      </div>

      {confirmLogout && (
        <Sheet onClose={() => setConfirmLogout(false)}>
          <h2>Log Out</h2>
          <p className="muted mt8">Are you sure you want to log out?</p>
          <div className="flex mt24" style={{ gap: 10 }}>
            <button className="btn btn-ghost grow" onClick={() => setConfirmLogout(false)}>Cancel</button>
            <button className="btn btn-danger grow" onClick={logout} disabled={loggingOut}>{loggingOut ? <Spinner /> : 'Log Out'}</button>
          </div>
        </Sheet>
      )}
    </div>
  );
}

// ── Edit profile ───────────────────────────────────────────────────

export function EditProfile() {
  const { toast } = useApp();
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [profile, loading, error, reload, setProfile] = useLoad(async () => {
    const p = await UserService.getProfile();
    setForm({ fullName: p.fullName, phone: p.phoneNumber ?? '', bio: p.bio ?? '' });
    return p;
  });
  const [form, setForm] = useState({ fullName: '', phone: '', bio: '' });
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function pickPhoto(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    try {
      setProfile(await UserService.uploadProfilePicture(file));
      toast('Profile photo updated', 'gold');
    } catch (e) {
      toast((e as Error).message, 'red');
    } finally {
      setUploading(false);
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!form.fullName.trim()) return setSaveError('Full name cannot be empty.');
    setSaving(true);
    setSaveError(null);
    try {
      setProfile(await UserService.updateProfile({ fullName: form.fullName.trim(), phoneNumber: form.phone.trim(), bio: form.bio.trim() }));
      toast('Profile updated', 'gold');
      navigate('/profile');
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading && !profile) return <LoadingScreen />;
  if (error && !profile) return <div className="page container"><ErrorState message={error} onRetry={reload} /></div>;

  return (
    <div className="page container">
      <div className="narrow">
        <BackBar title="Edit Profile" />
        <div className="center mb16">
          <button onClick={() => fileRef.current?.click()} style={{ position: 'relative', display: 'inline-block' }} aria-label="Change profile photo" disabled={uploading}>
            <Avatar profile={profile} size={104} />
            <span className="icon-btn" style={{ position: 'absolute', right: -4, bottom: -4, background: 'var(--primary)', color: '#fff', width: 36, height: 36 }}>
              {uploading ? <Spinner /> : <Icon name="camera" size={18} />}
            </span>
          </button>
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => pickPhoto(e.target.files?.[0])} />
        </div>
        <form onSubmit={save} noValidate>
          {saveError && <div className="alert">{saveError}</div>}
          <div className="field">
            <label>Email Address</label>
            <input className="input readonly" value={profile?.email ?? ''} readOnly />
            <p className="muted xs mt8">Email cannot be changed</p>
          </div>
          <div className="field">
            <label htmlFor="fn">Full Name</label>
            <input id="fn" className="input" placeholder="Enter your full name" value={form.fullName} onChange={(e) => setForm({ ...form, fullName: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="ph">Phone Number</label>
            <input id="ph" className="input" type="tel" placeholder="e.g. +2348012345678" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="bio">Bio</label>
            <textarea id="bio" className="input" placeholder="Tell us a bit about yourself…" value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
          </div>
          <button type="submit" className="btn btn-primary block" disabled={saving}>{saving ? <Spinner /> : 'Save Changes'}</button>
        </form>
      </div>
    </div>
  );
}

// ── Settings ───────────────────────────────────────────────────────

export function Settings() {
  const [pwOpen, setPwOpen] = useState(false);
  return (
    <div className="page container">
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <BackBar title="Settings" />
        <div className="section-label">ACCOUNT</div>
        <div className="menu">
          <MenuItem icon="person" title="Personal Information" sub="Name, email, profile photo" to="/profile/edit" />
          <MenuItem icon="shield" title="Password & Security" sub="Change password" onClick={() => setPwOpen(true)} />
        </div>
        <div className="section-label">APPEARANCE</div>
        <ThemeToggle />
        <div className="section-label">SUPPORT &amp; LEGAL</div>
        <div className="menu">
          <MenuItem icon="support" title="Customer Support" sub="Get help, report an issue" to="/support" />
          <MenuItem icon="doc" title="Terms of Service" to="/terms" />
          <MenuItem icon="shield" title="Privacy Policy" to="/privacy" />
        </div>
        <p className="muted xs center mt24">Cinehubs Web • {new Date().getFullYear()}</p>
      </div>
      {pwOpen && <ChangePasswordSheet onClose={() => setPwOpen(false)} />}
    </div>
  );
}

function ChangePasswordSheet({ onClose }: { onClose: () => void }) {
  const { toast } = useApp();
  const [f, setF] = useState({ old: '', next: '', confirm: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!f.old || !f.next) return setError('Please fill in all fields.');
    if (f.next !== f.confirm) return setError('New passwords do not match.');
    if (f.next.length < 6) return setError('New password must be at least 6 characters.');
    setBusy(true);
    setError(null);
    try {
      await UserService.changePassword(f.old, f.next);
      toast('Password updated successfully', 'gold');
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet onClose={onClose}>
      <h2 className="mb16">Change Password</h2>
      <form onSubmit={submit} noValidate>
        {error && <div className="alert">{error}</div>}
        <div className="field"><label>Current Password</label><PasswordInput autoComplete="current-password" placeholder="Current password" value={f.old} onChange={(v) => setF({ ...f, old: v })} /></div>
        <div className="field"><label>New Password</label><PasswordInput autoComplete="new-password" placeholder="New password" value={f.next} onChange={(v) => setF({ ...f, next: v })} /></div>
        <div className="field"><label>Confirm New Password</label><PasswordInput autoComplete="new-password" placeholder="Repeat new password" value={f.confirm} onChange={(v) => setF({ ...f, confirm: v })} /></div>
        <div className="flex" style={{ gap: 10 }}>
          <button type="button" className="btn btn-ghost grow" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary grow" disabled={busy}>{busy ? <Spinner /> : 'Update'}</button>
        </div>
      </form>
    </Sheet>
  );
}
