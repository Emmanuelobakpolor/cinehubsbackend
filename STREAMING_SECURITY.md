# Protected movie playback

How Cinehubs protects full movies, how to deploy and roll it out, and what it does **not** protect against.

## 1. Before this change (weaknesses found)

| # | Weakness | Impact |
|---|----------|--------|
| 1 | `MovieSerializer` used `fields='__all__'`, so `movie_file` (the permanent public Cloudinary MP4 URL) went to **every** signed-in user from `/api/movies/`, `/api/movies/<id>/`, trending and featured. | Anyone with an account could download any movie without paying. |
| 2 | Movies were stored as public Cloudinary `upload` assets. | A leaked URL works forever, for anyone. |
| 3 | The web player used `<video src="…mp4">`, and the web **Download** button saved the raw MP4. | Trivial ripping. `nodownload` / right-click blocking are cosmetic. |
| 4 | Premium users get `MovieDownload` rows with `amount_paid=0`; `/download/` treated *any* row as "already paid". | Access never expired after Premium lapsed. |
| 5 | `/confirm-download/` never checked whether a `tx_ref` had already been used. | One ₦ Basic payment could unlock unlimited movies. |
| 6 | `/media/` is served without auth (`config/streaming.py`). | Only matters with local storage (dev). |
| 7 | Root `.gitignore` `Lib/` matched `cinehubsweb/src/lib/` on Windows. | `src/lib/*` was never committed. Fixed by anchoring to `/Lib/`. |

Items 1, 3, 4, 5 and 7 are fixed. Item 2 is fixed per movie once `protect_movie_sources --apply` is run (see rollout).

## 2. Architecture

```
 Browser / app                 Django (Railway)                       CDN (Cloudinary)
 ─────────────                 ────────────────                       ────────────────
 POST /api/movies/<id>/playback ─▶ JWT + verified email
                                   entitlement: Premium active OR paid Basic purchase
                                   10-day viewing window not expired
                                   create PlaybackSession (random token, SHA-256 stored,
                                     2 h TTL, max 3 live per user; oldest revoked)
                               ◀── {mode, manifest_url, drm, expires_at, end_url}

 GET /api/stream/<token>/master.m3u8 ─▶ token valid?  ──▶ variant list (relative URIs)
 GET /api/stream/<token>/<n>.m3u8    ─▶ token valid?  ──▶ segment URLs + key URI
 GET /api/stream/<token>/key         ─▶ token valid AND entitlement re-checked ──▶ 16-byte AES key
 GET  hls/<random>/720_00001.ts  ────────────────────────────────────────▶ encrypted segment
 POST /api/stream/<token>/end        ─▶ revoke (player close / tab close)
```

The playback endpoint picks one of three modes:

| Mode | When | Protection |
|------|------|------------|
| `drm` | `DRM_PROVIDER=mux` is configured and the movie has `MovieStream.drm_playback_id` | Widevine / PlayReady / FairPlay through Mux. Keys never reach JavaScript. |
| `hls` | The movie has a READY `MovieStream` | **Free tier.** AES-128 encrypted HLS ladder (1080/720/480, never upscaled). Segments on the CDN are useless without the key, and the key is only served to a live, entitled session. |
| `progressive` | Not yet packaged, `PLAYBACK_ALLOW_PROGRESSIVE=True`, source still public | Legacy MP4 URL, entitled users only. Migration period only. |

Why AES-128 HLS for now: it was the only free option. Every commercial multi-DRM costs money: Mux is $100/mo + $0.003/licence, Bunny MediaCage Enterprise is $99/mo + about $0.005/licence, and DoveRunner/PallyCon is quote-based. AES-128 HLS works in every browser and in iOS/Android native players with no licence fees. The Mux adapter is already built, so real DRM can be switched on later through configuration alone.

### Code map

| File | Role |
|------|------|
| `movies/playback.py` | Entitlement (`is_entitled`, `access_expired`), session create/lookup, playlist rendering, Cloudinary URL parsing |
| `movies/views.py` | `PlaybackSessionView`, `Stream{Master,Variant,Key,End}View`. Download views now use the shared entitlement helpers and never return protected URLs. |
| `movies/packaging.py` | ffmpeg ladder → AES-128 → upload segments; `protect_source()` moves the original to Cloudinary `authenticated` delivery |
| `movies/drm.py` | Mux adapter: RS256 JWTs (`aud: v` manifest, `aud: d` licences) and licence/certificate URLs |
| `movies/models.py` | `MovieStream` (key, variants, status, `drm_playback_id`), `PlaybackSession` |
| `movies/management/commands/` | `package_movies`, `protect_movie_sources` |
| `cinehubsweb/src/lib/streaming.ts` | Shaka Player (HLS build, lazy-loaded), DRM config, Mux FairPlay adapters, native-HLS fallback, error classification |
| `cinehubsweb/src/pages/Player.tsx` | Uses playback sessions. On expiry it fetches one fresh session automatically and resumes; it ends the session on leave/tab close. Watermark, capture guard, speed, fullscreen, wake lock and progress are unchanged. |

## 3. API changes

* **New** `POST /api/movies/<id>/playback/`: 200 session, 402 payment required (same body as `/download/`), 403 `access_expired`, 503 `stream_not_ready`, 429 throttled.
* **New** `/api/stream/<token>/…`: no JWT. The path token is the credential, because native players can't send headers.
* **Changed** `movie_file` is `''` for non-staff in all movie list/detail responses. Admins still see it.
* **Changed** `download_url` (`/download/`, `/confirm-download/`) and `movie_file` in `/my-downloads/` are `''` once a movie's source is protected. Before that they are unchanged.
* **Changed** A Premium access row (`amount_paid=0`) no longer counts as a purchase after Premium lapses, and a payment reference unlocks only one movie.

### Mobile app (Flutter, `cinehubs/`, not in this repo) — required before protecting sources
The app plays `download_url`, falling back to `movie_file`, and uses `download_url` for in-app offline downloads. It keeps working until a movie's source is protected. Before running `protect_movie_sources --apply`, the app must:
1. Call `POST /api/movies/<id>/playback/` and play `manifest_url`. ExoPlayer and AVPlayer play AES-128 HLS natively; send the user to the paywall on 402.
2. `POST end_url` when the player closes.
3. Offline downloads: either drop them for protected movies, or download the HLS package into app-private storage (the key must also be stored, which weakens protection). The proper fix is DRM persistent licences (Mux `offline` tokens), which need the paid tier.

## 4. Configuration

New dependencies: backend `cryptography` (RS256 signing for Mux). Frontend `shaka-player` (runtime) plus `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/dom` (dev). The worker also needs the system binaries `ffmpeg`/`ffprobe` (`nixpacks.toml`).

Migration: `movies/0009_protected_playback` adds two tables and touches no existing data. It runs automatically through `preDeploy`.

```dotenv
# ── Protected playback (all optional; defaults shown) ──────────────
PLAYBACK_SESSION_TTL_SECONDS=7200     # how long a session can fetch manifest/key
PLAYBACK_MAX_ACTIVE_SESSIONS=3        # simultaneous streams per account
PLAYBACK_ALLOW_PROGRESSIVE=True       # set False once every movie is packaged
PLAYBACK_THROTTLE_RATE=60/hour        # POST /playback/ per user
STREAM_THROTTLE_RATE=600/hour         # manifest/key requests per IP
USE_REDIS_CACHE=False                 # True = throttle counters shared across workers (uses REDIS_URL)

# ── Encrypted HLS packaging (worker) ───────────────────────────────
HLS_STORAGE=cloudinary                # 'local' only for dev
HLS_RENDITIONS=1080:5000,720:2800,480:1200   # height:video_kbps
HLS_SEGMENT_SECONDS=6
HLS_X264_PRESET=veryfast
HLS_AUTO_PACKAGE=False                # True = package automatically on upload/replace

# ── Commercial DRM (paid; leave empty to stay on free AES-128 HLS) ─
DRM_PROVIDER=                         # 'mux'
MUX_SIGNING_KEY_ID=
MUX_SIGNING_PRIVATE_KEY=              # base64 private key returned by Mux; server only
MUX_PLAYBACK_RESTRICTION_ID=          # optional referrer/user-agent restriction
```

## 5. Deployment and rollout

1. **Deploy backend and worker.** Railway builds with `nixpacks.toml`, which adds ffmpeg. Make sure the `worker` process from the `Procfile` is running as a service, since packaging runs there. Set `USE_REDIS_CACHE=True` so throttling works across gunicorn workers.
2. **Deploy the web app** (`npm ci && npm run build` on Vercel). No new env vars.
3. **Package existing movies:** `python manage.py package_movies --missing --queue` (or synchronously, without `--queue`, in a Railway shell). Check status in Django admin → *Movie streams*; failures show ffmpeg's error. Encoding time depends on the worker's CPU, so time the first movie before queueing the whole library. `HLS_X264_PRESET` trades speed against quality. Segments go to Cloudinary raw storage under `hls/<random>/` and count towards your Cloudinary storage and bandwidth credits.
4. **Turn on auto-packaging** for new uploads: `HLS_AUTO_PACKAGE=True`.
5. **Ship the Flutter update** (section 3).
6. **Lock the originals:** `python manage.py protect_movie_sources` (dry run), then add `--apply`. This moves each packaged movie's MP4 to Cloudinary `authenticated` delivery and purges the CDN copy, so every old `movie_file` URL stops working. It can be undone per movie with Cloudinary's rename API (`to_type='upload'`).
7. Set `PLAYBACK_ALLOW_PROGRESSIVE=False`.

### Turning on real DRM (paid)
1. Mux account → request DRM in *Settings → Digital Rights Management*. Mux emails a DRM configuration ID. Start Apple's FairPlay Streaming application at the same time, because approval takes a while.
2. Create a signing key (`POST /system/v1/signing-keys`) and set `MUX_SIGNING_KEY_ID` / `MUX_SIGNING_PRIVATE_KEY`.
3. For each movie, create a Mux asset from the source with `advanced_playback_policies: [{policy: "drm", drm_configuration_id}]` and `video_quality: "plus"`. Paste the resulting playback ID into admin → *Movie streams* → `drm_playback_id`. (Not automated: it needs the account first.)
4. Set `DRM_PROVIDER=mux`. Movies with a `drm_playback_id` switch to `drm` mode; the rest stay on AES-128 HLS.

## 6. Verified in this change

* Backend: 45 tests (`manage.py test`) cover authorized/unauthorized playback, unverified email, lapsed Premium, expired viewing window, expired/revoked/invalid tokens, deactivated accounts, key re-check after a subscription lapses, the stream cap, throttling, progressive fallback rules, Mux token claims/licence URLs, payment-reference reuse, `movie_file` hiding, packaging (mocked ffmpeg), signals and commands.
* Frontend: 22 tests (`npm test`) cover Shaka init/cleanup, DRM config and Mux FairPlay filters, native-HLS fallback, unsupported browsers, error classification, trailer vs. movie, paywall redirect, session refresh and resume, the retry limit, speed menu, watermark, progress on leave and session end on tab close. `npm run build` passes.
* Real pipeline, run locally with ffmpeg 9.0.2: a 720p clip packaged into 720p+480p. Every segment is AES-128 encrypted (no TS sync byte) and decrypts with the stored key and advertised IV. In headless Chrome through Django and Vite, the player fetched session → master → variant → key → segments, played, switched 480p→720p, and after leaving the copied key URL returned 403.
* **Not** tested: Safari/iOS, Edge, Android devices, Cloudinary uploads with real credentials, real Mux DRM.

## 7. Manual test checklist

For each of: **Chrome (Win/macOS), Edge (Win), Safari (macOS), iOS Safari, Android Chrome**

- [ ] Premium user: movie plays, seeks, changes quality on a slow network (DevTools throttling), speed menu and fullscreen work, watermark moves.
- [ ] Basic user who paid: plays. Basic user who hasn't paid: sent to the paywall.
- [ ] Trailer plays for everyone.
- [ ] Network tab: no `.mp4` URL for full movies; `/key` requests carry the session token; `/api/movies/` shows `movie_file: ""`.
- [ ] Copy the `master.m3u8` URL, close the player and open the URL in a private window: **403**.
- [ ] Open the same movie in 4 tabs: the oldest tab's next key/manifest request fails, and the player either recovers with a fresh session or shows the error.
- [ ] Admin → Playback sessions → revoke during playback, then seek far ahead or reload: new playback requires a new session.
- [ ] Let a session expire (set `PLAYBACK_SESSION_TTL_SECONDS=60`) and reload: the player refreshes and resumes at the same time.
- [ ] Old browser without MediaSource or HLS: shows the "cannot play protected video" message.
- [ ] Resume/progress: watch 1 min, leave, and check that *Continue watching* reflects it.
- [ ] Capture guard: Win+Shift+S / Cmd+Shift+4 / alt-tab blanks the picture, and clicking resumes.
- [ ] (DRM mode only) Screenshot during playback: black frame expected on Safari/iOS and on Edge with hardware PlayReady; usually **not** black on desktop Chrome/Firefox.

## 8. Needs paid credentials or external infrastructure

* Widevine / PlayReady / FairPlay DRM: Mux DRM add-on, plus an Apple FairPlay Streaming deployment package.
* Hardware-backed screen-capture blocking: only comes with DRM, and only on some devices.
* DRM offline licences for in-app downloads.
* Forensic (invisible, per-session) watermarking such as NexGuard or Irdeto TraceMark is an enterprise add-on. Cinehubs only has the visible moving email watermark.
* Cloudinary storage/bandwidth for the HLS ladder: the default 3 renditions total about 9.4 Mbps, about 4.2 GB per hour of film. Plus Railway CPU for encoding.
* Shared throttle counters need Redis (`USE_REDIS_CACHE=True`; `REDIS_URL` already exists).

## 9. Remaining limitations (be honest with stakeholders)

* **AES-128 HLS is not DRM.** The key is delivered to the browser's JavaScript/media stack. A determined user with an active entitlement can capture the key and segments with developer tools or tools like yt-dlp, and decrypt the movie. It stops casual sharing, URL leaks and naive downloaders, and ties every playback to an account, but it does not stop a paying user who wants to rip.
* **Nothing stops screen recording in every case.** DRM can black out captures on Safari/iOS and hardware-DRM setups, but not on most desktop Chrome/Firefox, and not a camera pointed at the screen. The capture guard is a deterrent only, and the visible watermark is what traces leaks.
* Once a player has fetched the key, revoking the session doesn't stop that tab from playing what it has already buffered or can still decrypt. Revocation stops *new* sessions and keys. Key rotation means re-packaging (`package_movies <id>`), which issues a new key and a new segment folder and deletes the old one.
* The session token sits in the URL path, because native HLS players can't send headers. Within its TTL, anyone holding it can fetch the key, but only while the owner's account is still entitled, and only until the owner stops watching or it hits the stream cap.
* Sessions aren't bound to IP or User-Agent, because mobile networks change IPs and AVPlayer uses a different UA from Safari.
* Segment URLs (Cloudinary raw, random folder) are public but encrypted.
* Until `protect_movie_sources --apply` has run, original MP4 URLs that users already received before this change still work.
