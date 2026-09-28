import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { storage } from '../api/client';

const POSTER_BASE = 'https://image.tmdb.org/t/p/w342';
export const ONBOARDING_POSTERS = [
  '3nO3VboeVLVOwIHMkTRIwTrrKQP', // King of Boys
  '9aMG2ftIFqFAN69FdjovKJY0hsd', // A Tribe Called Judah
  'xb30hkUpBm23stnVgDJGYGsC0R0', // Aníkúlápó
  'qJpP0QJZE1Lcxswchana8opO9uW', // The Wedding Party
  'kn28W24slBLyGr8ZIZnxNE5YZrY', // The Black Book
  'nGwFsB6EXUCr21wzPgtP5juZPSv', // Gangs of Lagos
  '1pfvgpvHl5W9pV5P4dcnqhzMeUk', // Battle on Buka Street
  'yAFYuGRA9D1phwDvEfzVZKAJYkF', // Omo Ghetto: The Saga
  'uPZtE5DSo9VIX2N3NPtmTayhgP8', // Jagun Jagun
  'k8medyObgY0XTt2dL7BqjxXkqmw', // Citation
  'rzPxqPcmhjvRU8WtIqwbW95EPQ4', // Chief Daddy
  'zNoyzNcMa2d8i0cynPKI7KM9Zh0', // Ìjọ̀gbọ̀n
].map((p) => `${POSTER_BASE}/${p}.jpg`);

const TRENDING_TITLES = [
  'King of Boys', 'A Tribe Called Judah', 'Aníkúlápó', 'The Wedding Party', 'The Black Book',
  'Gangs of Lagos', 'Battle on Buka Street', 'Omo Ghetto: The Saga', 'Jagun Jagun', 'Citation',
];

const PAGES = [
  {
    icon: 'movie',
    title: 'Naija Stories, Front and Centre',
    subtitle:
      'Nollywood blockbusters, indie gems and diaspora favourites — curated for the culture, not buried under everything else.',
  },
  {
    icon: 'crown',
    title: 'Watch Now, Pay Your Way',
    subtitle:
      'Subscribe monthly or unlock a single title at a time — pay in Naira, no foreign card required.',
  },
  {
    icon: 'download',
    title: 'Download. Data-Friendly. Yours Offline.',
    subtitle:
      'Save a movie once, watch it anywhere — built for real-world networks, not just fibre.',
  },
];

const FAQ = [
  ['What is Cinehubs?', 'Cinehubs is a streaming home for Nollywood and African stories — blockbusters, indie gems and diaspora favourites, on your phone or in your browser.'],
  ['How much does Cinehubs cost?', 'Pay ₦200 to unlock a single movie for 10 days, or go Premium for ₦5,500 and watch everything for 30 days. No foreign card required.'],
  ['Where can I watch?', 'Right here on the web, and in the Cinehubs app for Android and iOS. One account works everywhere.'],
  ['Can I download movies?', 'Yes. Any movie you have access to can be downloaded, so you can watch without burning data.'],
  ['How do I pay?', 'Payments are processed securely by Flutterwave in Naira — card, bank transfer or USSD.'],
];

const HEADLINE = 'Nollywood movies, series and more';
const INTRO_KEY = 'intro_seen';

/** Adds `.in` to `.reveal` elements as they scroll into view. */
function useScrollReveal() {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const els = root.current?.querySelectorAll('.reveal') ?? [];
    if (!('IntersectionObserver' in window)) {
      els.forEach((el) => el.classList.add('in'));
      return;
    }
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        }),
      { threshold: 0.15 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return root;
}

function Intro({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2300);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <div className="nf-intro" onClick={onDone} role="presentation">
      <div className="nf-intro-rays" />
      <img src="/icon.png" alt="Cinehubs" className="nf-intro-logo" />
      <div className="nf-intro-word">CINEHUBS</div>
    </div>
  );
}

/** A row of posters that scrolls forever; duplicated so the loop is seamless. */
function PosterRow({ offset, reverse, speed }: { offset: number; reverse?: boolean; speed: number }) {
  const row = ONBOARDING_POSTERS.map((_, i) => ONBOARDING_POSTERS[(i + offset) % ONBOARDING_POSTERS.length]);
  return (
    <div className="nf-row">
      <div className={`nf-track ${reverse ? 'rev' : ''}`} style={{ animationDuration: `${speed}s` }}>
        {[...row, ...row].map((src, i) => (
          <img key={i} src={src} alt="" loading={i < 8 ? 'eager' : 'lazy'} />
        ))}
      </div>
    </div>
  );
}

function Ctas() {
  return (
    <div className="nf-ctas">
      <Link to="/signup" className="btn btn-primary nf-cta">
        Sign up and Get Started <Icon name="chevronRight" />
      </Link>
      <Link to="/signin" className="btn nf-ghost">
        I already have an account
      </Link>
    </div>
  );
}

export default function Onboarding() {
  const [intro, setIntro] = useState(() => storage.get(INTRO_KEY) !== '1');
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const root = useScrollReveal();

  const finishIntro = () => {
    storage.set(INTRO_KEY, '1');
    setIntro(false);
  };

  return (
    <div className="nf" ref={root}>
      {intro && <Intro onDone={finishIntro} />}

      <header className="nf-top">
        <Link to="/welcome" className="nf-brand">
          <img src="/icon.png" alt="" />
          <span>
            CINEHUBS
            <small>Home of Movies</small>
          </span>
        </Link>
        <Link to="/signin" className="btn btn-primary sm">Sign In</Link>
      </header>

      <section className={`nf-hero ${intro ? '' : 'go'}`}>
        <div className="nf-wall" aria-hidden="true">
          <div className="nf-wall-inner">
            <PosterRow offset={0} speed={70} />
            <PosterRow offset={4} speed={85} reverse />
            <PosterRow offset={8} speed={65} />
            <PosterRow offset={2} speed={90} reverse />
          </div>
        </div>
        <div className="nf-shade" />

        <div className="nf-hero-copy">
          <h1>
            {HEADLINE.split(' ').map((w, i) => (
              <span key={i} className="nf-word" style={{ animationDelay: `${0.25 + i * 0.09}s` }}>
                {w}&nbsp;
              </span>
            ))}
          </h1>
          <p className="nf-lead nf-fade" style={{ animationDelay: '0.9s' }}>
            From ₦200 a movie. Or go Premium for ₦5,500 a month.
          </p>
          <p className="nf-small nf-fade" style={{ animationDelay: '1.05s' }}>
            Ready to watch? Create your account or sign in.
          </p>
          <div className="nf-fade" style={{ animationDelay: '1.2s' }}>
            <Ctas />
          </div>
        </div>
        <div className="nf-arc" aria-hidden="true" />
      </section>

      <main className="nf-body">
        <section className="nf-section reveal">
          <h2>Trending Now</h2>
          <div className="nf-trending">
            {ONBOARDING_POSTERS.slice(0, 10).map((src, i) => (
              <Link to="/signup" key={src} className="nf-rank" style={{ transitionDelay: `${i * 60}ms` }} aria-label={`${i + 1}. ${TRENDING_TITLES[i]}`}>
                <span className="nf-num">{i + 1}</span>
                <img src={src} alt={TRENDING_TITLES[i]} loading="lazy" />
              </Link>
            ))}
          </div>
        </section>

        <section className="nf-section reveal">
          <h2>More Reasons to Join</h2>
          <div className="nf-reasons">
            {PAGES.map((p, i) => (
              <div key={p.title} className="nf-reason" style={{ transitionDelay: `${i * 120}ms` }}>
                <h3>{p.title}</h3>
                <p>{p.subtitle}</p>
                <span className="nf-reason-ic"><Icon name={p.icon} size={44} /></span>
              </div>
            ))}
          </div>
        </section>

        <section className="nf-section reveal">
          <h2>Frequently Asked Questions</h2>
          <div className="nf-faq">
            {FAQ.map(([q, a], i) => (
              <div key={q} className={`nf-faq-item ${openFaq === i ? 'open' : ''}`}>
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)} aria-expanded={openFaq === i}>
                  {q}
                  <span className="nf-plus" aria-hidden="true" />
                </button>
                <div className="nf-faq-a"><p>{a}</p></div>
              </div>
            ))}
          </div>
        </section>

        <section className="nf-section nf-final reveal">
          <p className="nf-small">Ready to watch? Create your account or sign in.</p>
          <Ctas />
        </section>

        <footer className="nf-foot">
          <a href="mailto:Cinehubscustomercare@gmail.com">Help</a>
          <Link to="/terms">Terms of Service</Link>
          <Link to="/privacy">Privacy Policy</Link>
          <span>© {new Date().getFullYear()} Cinehubs</span>
        </footer>
      </main>
    </div>
  );
}
