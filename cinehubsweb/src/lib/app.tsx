import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { storage } from '../api/client';

type Theme = 'light' | 'dark';
type ToastKind = 'default' | 'gold' | 'red';
interface Toast {
  id: number;
  text: string;
  kind: ToastKind;
}

interface AppCtx {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toast: (text: string, kind?: ToastKind, ms?: number) => void;
}

const Ctx = createContext<AppCtx>(null!);
export const useApp = () => useContext(Ctx);

export function AppProvider({ children }: { children: ReactNode }) {
  // The app defaults to light mode; remember the viewer's choice.
  const [theme, setThemeState] = useState<Theme>(() =>
    storage.get('theme') === 'dark' ? 'dark' : 'light',
  );
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const setTheme = useCallback((t: Theme) => {
    storage.set('theme', t);
    setThemeState(t);
  }, []);

  const toast = useCallback((text: string, kind: ToastKind = 'default', ms = 3000) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), ms);
  }, []);

  return (
    <Ctx.Provider value={{ theme, setTheme, toast }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind === 'default' ? '' : t.kind}`}>
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

/** Small data-loading hook: returns [data, loading, error, reload]. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e?.message || 'Something went wrong'))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return [data, loading, error, () => setTick((t) => t + 1), setData] as const;
}

export function daysLeftFrom(expiresAt: Date | null): number {
  if (!expiresAt || isNaN(expiresAt.getTime())) return 0;
  const days = Math.floor((expiresAt.getTime() - Date.now()) / 86_400_000);
  return Math.max(0, Math.min(10, days));
}

export function formatNaira(amount: string | number) {
  const n = Number(amount);
  return isNaN(n) ? String(amount) : n.toLocaleString('en-NG', { maximumFractionDigits: 2 });
}
