# Upload API / Cloudinary Debug TODO

- [x] Harden Cloudinary upload handling in `movies/views.py` with explicit exception handling and timeout.
- [x] Add structured logging + per-field upload timing in `movies/views.py`.
- [x] Return clean DRF JSON errors (not uncaught exceptions) for upload failures/timeouts.
- [x] Run Django checks to verify no syntax/runtime issues.
- [x] Provide exact Postman steps to avoid 502 upstream timeout and verify Cloudinary success.
