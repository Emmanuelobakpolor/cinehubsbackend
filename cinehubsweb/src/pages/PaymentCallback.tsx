import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { MovieService, PaymentService, type PendingPayment } from '../api/services';
import { ResultDialog, Spinner } from '../components/ui';

type Outcome =
  | { kind: 'working' }
  | { kind: 'success'; pending: PendingPayment | null }
  | { kind: 'failed'; message: string; pending: PendingPayment | null };

/**
 * Flutterwave redirects here with ?status=&tx_ref=&transaction_id=.
 * Same steps as the app's PaymentCompletionScreen: verify, then (for a single
 * movie) confirm the unlock against that tx_ref.
 */
export default function PaymentCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'working' });
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const status = (params.get('status') ?? '').toLowerCase();
    const pending = PaymentService.getPending();
    const txRef = params.get('tx_ref') || pending?.txRef || '';
    const transactionId = params.get('transaction_id') ?? undefined;

    if (!['successful', 'success', 'completed'].includes(status) || !txRef) {
      PaymentService.clearPending();
      setOutcome({ kind: 'failed', message: 'Payment was cancelled or failed. No money was deducted.', pending });
      return;
    }

    (async () => {
      try {
        await PaymentService.verifyPayment(txRef, transactionId);
        if (pending?.movieId) await MovieService.confirmMoviePayment(pending.movieId, txRef);
        PaymentService.clearPending();
        setOutcome({ kind: 'success', pending });
      } catch (e) {
        setOutcome({ kind: 'failed', message: (e as Error).message, pending });
      }
    })();
  }, [params]);

  const pending = outcome.kind === 'working' ? null : outcome.pending;
  const retryTo = pending?.movieId ? `/movie/${pending.movieId}` : '/subscription';

  return (
    <div className="loading-screen" style={{ minHeight: '100vh', flexDirection: 'column', gap: 16 }}>
      <span style={{ color: 'var(--primary)' }}><Spinner large /></span>
      <p className="muted">Confirming your payment…</p>

      {outcome.kind === 'success' &&
        (pending?.movieId ? (
          <ResultDialog
            title="Payment Successful!"
            text={`${pending.movieTitle ?? 'This movie'} is unlocked for 10 days.`}
            action="Start Watching"
            onAction={() => navigate(`/watch/${pending.movieId}`, { replace: true })}
            secondary={{ label: 'Back to movie', onClick: () => navigate(`/movie/${pending.movieId}`, { replace: true }) }}
          />
        ) : (
          <ResultDialog
            title="Subscription Activated!"
            text="Your PREMIUM subscription is now active for 30 days. Enjoy unlimited access!"
            action="Start Watching"
            onAction={() => navigate('/home', { replace: true })}
          />
        ))}

      {outcome.kind === 'failed' && (
        <ResultDialog
          ok={false}
          title="Payment Not Completed"
          text={outcome.message}
          action="Try Again"
          onAction={() => navigate(retryTo, { replace: true })}
          secondary={{ label: 'Go Home', onClick: () => navigate('/home', { replace: true }) }}
        />
      )}
    </div>
  );
}
