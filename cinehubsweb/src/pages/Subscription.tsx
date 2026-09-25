import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PaymentService, PLAN_PREMIUM } from '../api/services';
import { useApp, useLoad } from '../lib/app';
import { Icon } from '../components/Icon';
import { BackBar, Sheet, Spinner } from '../components/ui';

const PLANS = [
  {
    key: 'basic',
    title: 'BASIC',
    price: '₦200',
    period: '/ movie',
    blurb: 'Pay only for what you watch.',
    features: ['1080p High Definition', '1 concurrent stream', 'Ad-free playback', 'Watch on any device'],
    button: 'Get Started',
  },
  {
    key: 'premium',
    title: 'PREMIUM',
    price: '₦5,500',
    period: '/mo',
    blurb: 'Full access to all movies for a complete 30 days.',
    features: ['4K Ultra HD + HDR', '4 concurrent streams', 'Spatial audio surround', 'Full movie access for 1 month'],
    button: 'Subscribe Premium',
  },
];

export default function Subscription() {
  const navigate = useNavigate();
  const { toast } = useApp();
  const [active] = useLoad(() => PaymentService.activeSubscription());
  const [basicInfo, setBasicInfo] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [paying, setPaying] = useState(false);

  async function payPremium() {
    setPaying(true);
    try {
      await PaymentService.startCheckout({ planId: PLAN_PREMIUM, planName: 'PREMIUM' });
    } catch (e) {
      setPaying(false);
      toast(`Could not initiate payment: ${(e as Error).message}`, 'red', 5000);
    }
  }

  return (
    <div className="page container">
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <BackBar
          title="Subscription"
          right={
            <button className="link-btn small" onClick={() => navigate('/home')}>
              Skip for now
            </button>
          }
        />
        <h2>Choose your seat</h2>
        <p className="muted small mb16">Subscribe &amp; cancel anytime when necessary</p>

        {active && (
          <div className="alert" style={{ background: 'color-mix(in srgb, var(--success) 12%, transparent)', color: 'var(--success)' }}>
            Your {active.planName} plan is active until {new Date(active.endDate).toLocaleDateString()}.
          </div>
        )}

        <div className="plans">
          {PLANS.map((p) => (
            <div key={p.key} className={`plan-card ${p.key === 'premium' ? 'featured' : ''}`}>
              <div className="flex between">
                <strong style={{ letterSpacing: 2 }}>{p.title}</strong>
                {p.key === 'premium' && <span className="chip gold"><Icon name="crown" size={14} /> Best value</span>}
              </div>
              <div className="price">
                {p.price}
                <span> {p.period}</span>
              </div>
              <p className="muted small">{p.blurb}</p>
              <ul>
                {p.features.map((f) => (
                  <li key={f}>
                    <Icon name="check" size={18} /> {f}
                  </li>
                ))}
              </ul>
              <button
                className={`btn block ${p.key === 'premium' ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => (p.key === 'premium' ? setConfirm(true) : setBasicInfo(true))}
              >
                {p.button}
              </button>
            </div>
          ))}
        </div>
      </div>

      {basicInfo && (
        <Sheet onClose={() => setBasicInfo(false)}>
          <strong className="gold" style={{ letterSpacing: 2 }}>BASIC Plan</strong>
          <h2 className="mt8">No upfront subscription needed.</h2>
          <p className="muted small mt8">
            With the Basic plan you pay ₦200 per movie. Simply browse, find a movie you want, tap Play or Download — you&apos;ll be charged per movie at that point.
          </p>
          <button className="btn btn-primary block mt24" onClick={() => navigate('/browse')}>
            Browse Movies
          </button>
        </Sheet>
      )}

      {confirm && (
        <Sheet onClose={() => !paying && setConfirm(false)}>
          <h2>Subscribe to PREMIUM</h2>
          <p className="muted small">Unlimited access for 30 days</p>
          <div className="panel mt16 flex between">
            <div>
              <strong>PREMIUM — 30 Days</strong>
              <p className="muted small">₦5,500 / month</p>
            </div>
            <Icon name="crown" size={28} className="gold" />
          </div>
          <p className="muted xs mt16">You&apos;ll be taken to Flutterwave to pay securely in Naira, then brought back here.</p>
          <button className="btn btn-primary block mt16" onClick={payPremium} disabled={paying}>
            {paying ? <Spinner /> : 'Confirm Subscription — ₦5,500'}
          </button>
        </Sheet>
      )}
    </div>
  );
}
