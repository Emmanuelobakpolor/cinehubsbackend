import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { AuthService } from '../api/services';
import { BackBar, PasswordInput, ResultDialog, Spinner } from '../components/ui';
import { Icon } from '../components/Icon';
import { ONBOARDING_POSTERS } from './Onboarding';

/** Form on the right, poster wall on the left (desktop only). */
function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth-shell">
      <aside className="auth-art" aria-hidden="true">
        <div className="posters">
          {[...ONBOARDING_POSTERS, ...ONBOARDING_POSTERS.slice(0, 6)].map((p, i) => (
            <img key={i} src={p} alt="" />
          ))}
        </div>
        <div className="copy">
          <h2>Nollywood &amp; Beyond, On Demand</h2>
          <p style={{ opacity: 0.75 }}>Stream · Discover · Experience</p>
        </div>
      </aside>
      <main className="auth-main">
        <div className="inner">
          <BackBar title={title} />
          {children}
        </div>
      </main>
    </div>
  );
}

function SubmitButton({ loading, children }: { loading: boolean; children: ReactNode }) {
  return (
    <button type="submit" className="btn btn-primary block mt8" disabled={loading}>
      {loading ? <Spinner /> : children}
    </button>
  );
}

// ── Sign in ────────────────────────────────────────────────────────

export function SignIn() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) return setError('Please enter your email and password.');
    setLoading(true);
    setError(null);
    try {
      await AuthService.login(email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== '/signin' ? from : '/home', { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Sign in">
      <form onSubmit={submit} noValidate>
        {error && <div className="alert">{error}</div>}
        <div className="field">
          <label htmlFor="email">Email Address</label>
          <input id="email" className="input" type="email" autoComplete="email" placeholder="Enter email address" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <PasswordInput id="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={setPassword} />
        </div>
        <div style={{ textAlign: 'right', marginBottom: 20 }}>
          <Link to="/forgot-password" className="link-btn small">
            Forgot Password?
          </Link>
        </div>
        <SubmitButton loading={loading}>Sign In</SubmitButton>
      </form>
      <p className="auth-foot">
        Don&apos;t have an account?{' '}
        <Link to="/signup" replace className="link-btn">
          Sign Up
        </Link>
      </p>
    </AuthShell>
  );
}

// ── Sign up ────────────────────────────────────────────────────────

export function SignUp() {
  const navigate = useNavigate();
  const [f, setF] = useState({ name: '', email: '', phone: '', password: '', confirm: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const name = f.name.trim();
    const email = f.email.trim();
    if (!name || !email || !f.password) return setError('Please fill in all required fields.');
    if (f.password !== f.confirm) return setError('Passwords do not match.');
    if (f.password.length < 6) return setError('Password must be at least 6 characters.');
    setLoading(true);
    setError(null);
    try {
      await AuthService.register({ fullName: name, email, password: f.password, phoneNumber: f.phone.trim() || undefined });
      navigate(`/verify?mode=signup&email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Sign up">
      <form onSubmit={submit} noValidate>
        {error && <div className="alert">{error}</div>}
        <div className="field">
          <label htmlFor="name">Full Name</label>
          <input id="name" className="input" autoComplete="name" placeholder="Enter your full name" value={f.name} onChange={(e) => set('name')(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="email">Email Address</label>
          <input id="email" className="input" type="email" autoComplete="email" placeholder="Enter email address" value={f.email} onChange={(e) => set('email')(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="phone">Phone Number (optional)</label>
          <div className="phone-row">
            <span className="prefix">+234</span>
            <input id="phone" className="input" type="tel" autoComplete="tel-national" placeholder="Phone number" value={f.phone} onChange={(e) => set('phone')(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="pw">Password</label>
          <PasswordInput id="pw" autoComplete="new-password" placeholder="Create a password (min 6 chars)" value={f.password} onChange={set('password')} />
        </div>
        <div className="field">
          <label htmlFor="pw2">Confirm Password</label>
          <PasswordInput id="pw2" autoComplete="new-password" placeholder="Repeat your password" value={f.confirm} onChange={set('confirm')} />
        </div>
        <SubmitButton loading={loading}>Create Account</SubmitButton>
      </form>
      <p className="auth-foot">
        Already have an account?{' '}
        <Link to="/signin" replace className="link-btn">
          Sign In
        </Link>
      </p>
    </AuthShell>
  );
}

// ── Forgot password ────────────────────────────────────────────────

export function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim()) return setError('Please enter your email address.');
    setLoading(true);
    setError(null);
    try {
      await AuthService.forgotPassword(email.trim());
      navigate(`/verify?mode=reset&email=${encodeURIComponent(email.trim())}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Forgot Password">
      <h2>Enter Email Address</h2>
      <p className="muted small mt8 mb16">Enter the email you used to create your account.</p>
      <form onSubmit={submit} noValidate>
        {error && <div className="alert">{error}</div>}
        <div className="field">
          <label htmlFor="email">Email Address</label>
          <input id="email" className="input" type="email" autoComplete="email" placeholder="Enter email address" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <SubmitButton loading={loading}>Proceed</SubmitButton>
      </form>
      <p className="auth-foot">
        <Link to="/signin" className="link-btn">
          Back to Login
        </Link>
      </p>
    </AuthShell>
  );
}

// ── OTP (signup verification or password reset) ────────────────────

export function Otp() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const email = params.get('email') ?? '';
  const isSignup = params.get('mode') !== 'reset';
  const [digits, setDigits] = useState(['', '', '', '', '', '']);
  const [seconds, setSeconds] = useState(60);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (seconds <= 0) return;
    const t = setTimeout(() => setSeconds((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [seconds]);

  function setDigit(i: number, v: string) {
    const clean = v.replace(/\D/g, '');
    if (clean.length > 1) {
      // Pasted the whole code
      const next = clean.slice(0, 6).split('');
      setDigits([...next, ...Array(6 - next.length).fill('')]);
      refs.current[Math.min(next.length, 5)]?.focus();
      return;
    }
    const next = [...digits];
    next[i] = clean;
    setDigits(next);
    if (clean && i < 5) refs.current[i + 1]?.focus();
  }

  async function resend() {
    setError(null);
    try {
      if (isSignup) await AuthService.resendEmailOtp();
      else await AuthService.forgotPassword(email);
      setSeconds(60);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const otp = digits.join('');
    if (otp.length < 6) return setError('Please enter the 6-digit code.');
    if (!isSignup) {
      navigate('/reset-password', { replace: true, state: { email, otp } });
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await AuthService.verifyEmail(otp);
      navigate('/account-ready', { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="OTP Verification">
      <h2>Enter the code</h2>
      <p className="muted small mt8">
        Type in the 6-digit code sent to <strong style={{ color: 'var(--text)' }}>{email}</strong>
      </p>
      <form onSubmit={submit} noValidate>
        <div className="otp-row">
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => {
                refs.current[i] = el;
              }}
              inputMode="numeric"
              autoComplete={i === 0 ? 'one-time-code' : 'off'}
              maxLength={i === 0 ? 6 : 1}
              value={d}
              aria-label={`Digit ${i + 1}`}
              onChange={(e) => setDigit(i, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Backspace' && !digits[i] && i > 0) refs.current[i - 1]?.focus();
              }}
            />
          ))}
        </div>
        {error && <div className="alert">{error}</div>}
        <SubmitButton loading={loading}>Verify</SubmitButton>
      </form>
      <p className="auth-foot">
        {seconds > 0 ? 'Resend code in ' : "Didn't get the code? "}
        {seconds > 0 ? (
          <span className="gold">{seconds}s</span>
        ) : (
          <button className="link-btn" onClick={resend}>
            Resend
          </button>
        )}
      </p>
    </AuthShell>
  );
}

// ── Create new password (after reset OTP) ──────────────────────────

export function CreatePassword() {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { email?: string; otp?: string } | null };
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (!state?.email || !state.otp) {
    return (
      <AuthShell title="Create New Password">
        <p className="muted">This link has expired. Please start the password reset again.</p>
        <Link to="/forgot-password" className="btn btn-primary block mt16">
          Forgot Password
        </Link>
      </AuthShell>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!pw) return setError('Please enter a new password.');
    if (pw.length < 6) return setError('Password must be at least 6 characters.');
    if (pw !== confirm) return setError('Passwords do not match.');
    setLoading(true);
    setError(null);
    try {
      await AuthService.resetPassword(state!.email!, state!.otp!, pw);
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Create New Password">
      <form onSubmit={submit} noValidate>
        {error && <div className="alert">{error}</div>}
        <div className="field">
          <label htmlFor="pw">Create new Password</label>
          <PasswordInput id="pw" autoComplete="new-password" placeholder="Create your unique password" value={pw} onChange={setPw} />
        </div>
        <div className="field">
          <label htmlFor="pw2">Confirm new Password</label>
          <PasswordInput id="pw2" autoComplete="new-password" placeholder="Repeat your password" value={confirm} onChange={setConfirm} />
        </div>
        <SubmitButton loading={loading}>Update Password</SubmitButton>
      </form>
      <p className="auth-foot">
        <Link to="/signin" className="link-btn">
          Back to Login
        </Link>
      </p>
      {done && (
        <ResultDialog
          title="Password Reset Successful"
          text="Your password has been reset successfully. Please log in with your new password."
          action="Login"
          onAction={() => navigate('/signin', { replace: true })}
        />
      )}
    </AuthShell>
  );
}

// ── Account ready (after signup OTP) ───────────────────────────────

export function AccountReady() {
  const navigate = useNavigate();
  return (
    <div className="loading-screen" style={{ minHeight: '100vh', padding: 24 }}>
      <div className="dialog narrow" style={{ maxWidth: 420 }}>
        <div className="ok-circle">
          <Icon name="shield" size={36} />
        </div>
        <h2>Account Setup Successful!</h2>
        <p>Your email has been verified and your account is ready. Welcome to Cinehubs!</p>
        <button className="btn btn-primary block" onClick={() => navigate('/home', { replace: true })}>
          Start Watching
        </button>
      </div>
    </div>
  );
}
