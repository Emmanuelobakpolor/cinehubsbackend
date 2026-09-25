import { useEffect, type ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { setSessionExpiredHandler, storage } from './api/client';
import { Layout } from './components/Layout';
import Splash from './pages/Splash';
import Onboarding from './pages/Onboarding';
import { SignIn, SignUp, ForgotPassword, Otp, CreatePassword, AccountReady } from './pages/Auth';
import Home from './pages/Home';
import Browse from './pages/Browse';
import MovieDetail from './pages/MovieDetail';
import Player from './pages/Player';
import { Saved, History, Downloads } from './pages/Library';
import Notifications from './pages/Notifications';
import Subscription from './pages/Subscription';
import PaymentCallback from './pages/PaymentCallback';
import { Profile, EditProfile, Settings } from './pages/Profile';
import { Support, Privacy, Terms } from './pages/Info';

function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!storage.hasTokens()) {
    return <Navigate to="/signin" replace state={{ from: location.pathname + location.search }} />;
  }
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  return storage.hasTokens() ? <Navigate to="/home" replace /> : <>{children}</>;
}

export default function App() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    setSessionExpiredHandler(() => navigate('/signin', { replace: true }));
  }, [navigate]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <Routes>
      <Route path="/" element={<Splash />} />
      <Route path="/welcome" element={<GuestOnly><Onboarding /></GuestOnly>} />
      <Route path="/signin" element={<GuestOnly><SignIn /></GuestOnly>} />
      <Route path="/signup" element={<GuestOnly><SignUp /></GuestOnly>} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/verify" element={<Otp />} />
      <Route path="/reset-password" element={<CreatePassword />} />
      <Route path="/account-ready" element={<RequireAuth><AccountReady /></RequireAuth>} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />

      <Route path="/watch/:id" element={<RequireAuth><Player /></RequireAuth>} />
      <Route path="/payment/callback" element={<RequireAuth><PaymentCallback /></RequireAuth>} />

      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/home" element={<Home />} />
        <Route path="/browse" element={<Browse />} />
        <Route path="/movie/:id" element={<MovieDetail />} />
        <Route path="/saved" element={<Saved />} />
        <Route path="/history" element={<History />} />
        <Route path="/downloads" element={<Downloads />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/subscription" element={<Subscription />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/profile/edit" element={<EditProfile />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/support" element={<Support />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
