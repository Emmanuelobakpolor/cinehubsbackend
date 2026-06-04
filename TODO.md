# Payment Usage Audit TODO

- [x] Step 1: Audit subscription payment entry points and service usage
- [x] Step 2: Harden payment completion flow (avoid premature verification, handle success/failure redirects)
- [ ] Step 3: Run critical-path validation for payment flow and compile

---

# WebView Build Fix TODO

- [x] Step 1: Replace deprecated/mismatched `InAppWebViewOptions` usage in `payment_completion_screen.dart`
- [x] Step 2: Wrap options with `InAppWebViewGroupOptions(crossPlatform: ...)`
- [x] Step 3: Verify no other `initialOptions` mismatches remain in Flutter codebase

---

# Payment Flow Hardening TODO

- [x] Step 1: Harden payment configuration defaults in `config/settings.py`
  - [x] Set `PAYMENT_TEST_MODE` default to `False`
  - [x] Add `PAYMENT_REDIRECT_URL` environment-based setting with production default
- [x] Step 2: Replace hardcoded redirect URL usage in `payments/views.py` with `settings.PAYMENT_REDIRECT_URL`
- [x] Step 3: Add Flutterwave webhook endpoint scaffold (`payments/views.py`, `payments/urls.py`)
- [x] Step 4: Add webhook signature validation and trusted payment finalization path
- [x] Step 5: Add idempotent finalization checks for duplicate callbacks/verifications
- [x] Step 6: Add payment invariant checks (amount/currency/tx_ref/customer consistency)
- [x] Step 7: Add curl-based critical-path test script and run tests
- [x] Step 8: Summarize deployment env variables and go-live checklist

---

## ✅ All Steps Completed

All payment security hardening tasks are now complete. See:
- `DEPLOYMENT_CHECKLIST.md` - Full deployment guide
- `test_payment_flow.sh` - Test script for verifying the flow