import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

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

const PAGES = [
  {
    title: 'Naija Stories, Front and Centre',
    subtitle:
      'Nollywood blockbusters, indie gems and diaspora favourites — curated for the culture, not buried under everything else.',
  },
  {
    title: 'Watch Now, Pay Your Way',
    subtitle:
      'Subscribe monthly or unlock a single title at a time — pay in Naira, no foreign card required.',
  },
  {
    title: 'Download. Data-Friendly. Yours Offline.',
    subtitle:
      'Save a movie once, watch it anywhere — built for real-world networks, not just fibre.',
  },
];

export default function Onboarding() {
  const [page, setPage] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setPage((p) => (p + 1) % PAGES.length), 4000);
    return () => clearInterval(t);
  }, [page]);

  const posters = [0, 1, 2].map((i) => ONBOARDING_POSTERS[(page * 3 + i) % ONBOARDING_POSTERS.length]);
  const { title, subtitle } = PAGES[page];

  return (
    <div className="onboarding">
      <div className="flex" style={{ gap: 10, marginBottom: 16 }}>
        <img src="/icon.png" alt="" width={36} height={36} style={{ objectFit: 'contain' }} />
        <strong className="gold" style={{ letterSpacing: 3 }}>CINEHUBS</strong>
      </div>
      <div className="slide">
        <div key={page} style={{ animation: 'rise 0.5s ease-out' }}>
          <h1>{title}</h1>
          <p className="sub">{subtitle}</p>
          <div className="dots">
            {PAGES.map((_, i) => (
              <button key={i} className={i === page ? 'on' : ''} onClick={() => setPage(i)} aria-label={`Slide ${i + 1}`} />
            ))}
          </div>
        </div>
        <div className="fan">
          <img className="left" src={posters[0]} alt="" />
          <img className="right" src={posters[2]} alt="" />
          <img className="front" src={posters[1]} alt="" />
        </div>
      </div>
      <div className="ctas">
        <Link to="/signup" className="btn btn-primary block">
          Sign up and Get Started
        </Link>
        <Link to="/signin" className="btn btn-outline block">
          I already have an account
        </Link>
      </div>
    </div>
  );
}
