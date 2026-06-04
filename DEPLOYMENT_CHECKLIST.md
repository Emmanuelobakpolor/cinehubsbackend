# Payment Deployment Checklist

## Pre-Production Checklist

### 1. Environment Variables

Set these in your production environment (Railway, Heroku, etc.):

```bash
# ── PAYMENTS (REQUIRED) ───────────────────────────────────────
# Must be False in production
PAYMENT_TEST_MODE=False

# Get from Flutterwave Dashboard → Settings → API Keys
FLW_PUBLIC_KEY=FLWPUB-xxxxxxxxxxxxx
FLW_SECRET_KEY=FLWSECK-xxxxxxxxxxxxx
FLW_ENCRYPTION_KEY=xxxxxxxxxxxxx

# URL where Flutterwave will redirect after payment
# This should be your frontend's payment completion page
PAYMENT_REDIRECT_URL=https://your-frontend.com/payment-complete
```

### 2. Flutterwave Dashboard Configuration

1. **Enable Live Mode**
   - Go to Flutterwave Dashboard
   - Toggle from Test Mode to Live Mode

2. **Configure Webhook URL**
   - Go to Settings → Webhooks
   - Add: `https://your-backend-api.com/api/payments/webhook/flutterwave/`
   - Generate and save your webhook hash key

3. **Get API Keys**
   - Go to Settings → API Keys
   - Copy Public Key, Secret Key, and Encryption Key

### 3. Backend URL Configuration

Update your Flutterwave redirect URL to point to your frontend:

```python
# In your Django settings or environment
PAYMENT_REDIRECT_URL=https://your-frontend.com/payment-complete
```

Your frontend should:
1. Read the `tx_ref` from the URL query params
2. Call your backend `/api/payments/verify/` endpoint
3. Show success/failure message to user

### 4. Test in Production

Run the test script against your production URL:

```bash
chmod +x test_payment_flow.sh
./test_payment_flow.sh https://your-production-backend.up.railway.app "your_access_token" 1
```

### 5. Security Checklist

- [ ] `PAYMENT_TEST_MODE=False` in production
- [ ] Valid Flutterwave keys configured
- [ ] Webhook URL configured in Flutterwave dashboard
- [ ] Webhook hash key generated and saved
- [ ] Redirect URL points to your frontend
- [ ] Test payment flow works end-to-end
- [ ] Check payment logs for any errors

---

## Environment Variables Summary

| Variable | Description | Required |
|----------|-------------|----------|
| `PAYMENT_TEST_MODE` | `False` for production | ✅ |
| `FLW_PUBLIC_KEY` | Flutterwave public key | ✅ |
| `FLW_SECRET_KEY` | Flutterwave secret key | ✅ |
| `FLW_ENCRYPTION_KEY` | Flutterwave encryption key | ✅ |
| `PAYMENT_REDIRECT_URL` | Where to redirect after payment | ✅ |

---

## Common Issues

### Issue: "Payment validation failed: Amount mismatch"
**Cause:** Plan price in database doesn't match Flutterwave response
**Fix:** Ensure plan price in database matches what you're charging

### Issue: "Invalid signature" on webhook
**Cause:** Webhook signature verification failing
**Fix:** 
1. Ensure `FLW_SECRET_KEY` is correctly configured
2. Check Flutterwave dashboard has correct webhook URL
3. Verify webhook hash key is generated

### Issue: Webhook not reaching backend
**Cause:** Network/firewall issues or wrong URL
**Fix:**
1. Verify webhook URL in Flutterwave dashboard
2. Check Railway logs for incoming requests
3. Ensure backend is reachable (not blocking webhooks)

### Issue: Subscription not activating
**Cause:** Verification failing or webhook not received
**Fix:**
1. Check payment status in Django admin
2. Check application logs for errors
3. Manually verify payment status in Flutterwave dashboard