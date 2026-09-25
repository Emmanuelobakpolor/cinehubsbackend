import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { storage } from '../api/client';

export default function Splash() {
  const navigate = useNavigate();
  useEffect(() => {
    const t = setTimeout(
      () => navigate(storage.hasTokens() ? '/home' : '/welcome', { replace: true }),
      1800,
    );
    return () => clearTimeout(t);
  }, [navigate]);

  return (
    <div className="splash">
      <div className="glow" />
      <img src="/icon.png" alt="" />
      <div className="word">CINEHUBS</div>
      <div className="tag">Nollywood &amp; Beyond, On Demand</div>
      <div className="foot">Stream · Discover · Experience</div>
    </div>
  );
}
