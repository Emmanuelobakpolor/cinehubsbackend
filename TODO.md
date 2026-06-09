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

---

# CineHubs Admin Dashboard Responsive Redesign TODO

- [x] Step 1: Refactor layout shell for fluid, ultra-wide-safe container behavior
- [x] Step 2: Redesign Topbar responsiveness across mobile/tablet/laptop/desktop
- [x] Step 3: Refine desktop Sidebar and mobile drawer ergonomics/responsive widths
- [x] Step 4: Rework dashboard stats, movie list/table, and pricing panel for all breakpoints
- [x] Step 5: Run frontend build/type check and verify no regressions

---

# Admin Mobile Fit & No-Zoom UX TODO

- [x] Step 1: Add global overflow-safe/mobile-fit guards in layout shell
- [x] Step 2: Tighten Topbar small-screen spacing and overflow handling
- [x] Step 3: Patch dashboard sections that can trigger horizontal overflow
- [x] Step 4: Patch movies page header/list for narrow-screen wrapping
- [x] Step 5: Run admin frontend build/typecheck

---

# Admin Dedicated Mobile Views TODO

- [ ] Step 1: Implement explicit mobile-view section for dashboard page
- [ ] Step 2: Implement explicit mobile-view section for movies page
- [ ] Step 3: Implement explicit mobile-view section for upload-movie page
- [ ] Step 4: Implement explicit mobile-view section for categories page
- [ ] Step 5: Implement explicit mobile-view section for subscribers page
- [ ] Step 6: Implement explicit mobile-view section for broadcast page
- [ ] Step 7: Optimize AddMovieModal for smaller devices
- [ ] Step 8: Run cinehubsadmin build/typecheck and confirm
