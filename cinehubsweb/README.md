# Cinehubs Web

The customer website for Cinehubs. Same backend, flows and API calls as the Flutter app in `../cinehubs`.

## Run locally

```bash
npm install
npm run dev        # http://localhost:5173
```

The dev server proxies `/api` to the Django backend (`VITE_BACKEND_URL`, see `.env.example`), so no CORS setup is needed locally.

## Deploy (Vercel)

`vercel.json` already proxies `/api/*` to the Railway backend and routes all other paths to the SPA.

1. Import this folder as a Vercel project (framework: Vite).
2. On the **backend** (Railway), set `WEB_APP_ORIGINS` to your site's origin, e.g.
   `WEB_APP_ORIGINS=https://cinehubs.vercel.app,http://localhost:5173`.
   This is required for payments: Flutterwave only redirects back to allowlisted origins.

## How payments work on the web

1. `POST /api/payments/initiate/` with `plan_id` and `redirect_url=<site>/payment/callback`.
2. The browser goes to Flutterwave checkout.
3. Flutterwave redirects to `/payment/callback?status=…&tx_ref=…&transaction_id=…`.
4. The callback page calls `/payments/verify/`, and for a single movie (BASIC) also calls
   `/movies/<id>/confirm-download/`, the same steps as the app's `PaymentCompletionScreen`.

If the backend has `PAYMENT_TEST_MODE=True`, checkout is skipped and verification runs immediately.

## Differences from the mobile app

- **Downloads**: files are saved through the browser (Cloudinary `fl_attachment`), not into an in-app offline store.
- **Notifications**: polled every 60s instead of pushed via FCM.
- **Sessions**: expired access tokens are refreshed automatically via `/api/token/refresh/`.
