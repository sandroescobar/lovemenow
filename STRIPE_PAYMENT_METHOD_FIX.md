# Stripe Payment Method Fix - Card Only + Apple Pay

## Problem Solved ✅

The Affirm, Amazon Pay, Cash App Pay, and Klarna tabs were appearing because the Stripe PaymentIntent was created with:
```python
automatic_payment_methods={'enabled': True}  # ❌ WRONG
```

This allowed ALL payment methods available in your Stripe Dashboard.

---

## Solution Applied

### 1. **Fixed `/create-checkout-session` in `main.py` (Line 1297-1298)**

Changed from:
```python
automatic_payment_methods={'enabled': True}
```

To:
```python
automatic_payment_methods={'enabled': False},  # ✅ DISABLED
payment_method_types=['card'],                 # ✅ CARD ONLY
```

**What this does:**
- Disables automatic payment method discovery
- Restricts to **CARD ONLY** (Visa, Mastercard, Amex, etc.)
- **Still allows Apple Pay & Google Pay** via the Payment Request Button (card rails)

### 2. **Added Stale PI Cancellation (Lines 1285-1291)**

Prevents reusing old PaymentIntents:
```python
try:
    old_pi = session.get("active_pi_id")
    if old_pi:
        stripe.PaymentIntent.cancel(old_pi)
except Exception:
    pass
```

**Why:** Old PIs might have been created with auto methods ON. This forces a fresh PI each checkout.

### 3. **Bumped Cache Version in `checkout_enhanced.html` (Line 315)**

Changed script tag from:
```html
<script src="{{ url_for('static', filename='js/checkout.js') }}?v=20250929-2" defer></script>
```

To:
```html
<script src="{{ url_for('static', filename='js/checkout.js') }}?v=20250930-fixed-card-only" defer></script>
```

**Why:** Forces browsers to load fresh JS (not cached old version).

### 4. **Added Debug Logging in `checkout.js` (Lines 328-331)**

```javascript
const piId = clientSecret.split('_secret_')[0];
console.log('✅ Fresh PaymentIntent created:', piId);
console.log('📋 Delivery type:', selectedDeliveryType, 'Quote:', deliveryQuote);
```

**Why:** Helps verify the PI is being created correctly.

---

## Testing Checklist ✅

### Step 1: Restart Backend
```bash
# Stop Flask server and restart it
# This ensures the new code is loaded
```

### Step 2: Clear Browser Cache
- Open DevTools (F12)
- Network tab → check "Disable cache"
- Or do a hard refresh: `Cmd+Shift+R` (Mac) / `Ctrl+Shift+R` (Windows)

### Step 3: Verify in Browser Console
1. Go to checkout page
2. Open DevTools Console (F12)
3. Select a delivery method
4. Look for the log message: `✅ Fresh PaymentIntent created: pi_...`
5. Copy that PI ID

### Step 4: Verify in Stripe Dashboard
1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Developers → Events**
3. Search for your PI ID (e.g., `pi_123abc...`)
4. Click it to view details
5. Verify these settings:
   - ✅ `automatic_payment_methods.enabled` = **false**
   - ✅ `payment_method_types` = **["card"]**
   - ✅ `status` = **requires_payment_method** (or **succeeded** if paid)

### Step 5: Test Payment Method Tabs
The payment form should now show:
- ✅ **Card** (Visa, Mastercard, Amex, Discover)
- ✅ **Apple Pay** (if on Safari/HTTPS with domain verified)
- ❌ ~~Affirm~~ (removed)
- ❌ ~~Amazon Pay~~ (removed)
- ❌ ~~Cash App Pay~~ (removed)
- ❌ ~~Klarna~~ (removed)

---

## Apple Pay Setup (Optional)

Apple Pay only appears when ALL conditions are true:

1. **Browser**: Safari (not Chrome, Firefox, etc.)
2. **Protocol**: HTTPS on a real domain (not `127.0.0.1` or `localhost`)
3. **Domain**: Registered in Stripe Dashboard
4. **File**: Must host `/.well-known/apple-developer-merchantid-domain-association`

### Quick Check:
```javascript
// In browser console on Safari:
const result = await paymentRequest.canMakePayment();
console.log('canMakePayment:', result);
```

If `null` → Apple Pay not available on this browser/domain.

---

## Google Pay Setup (Optional)

If you want Google Pay in addition to Apple Pay:

```python
payment_method_types=['card', 'google_pay']
```

But since you specified "card only", you're good.

---

## If Tabs Still Show After Restart

1. **Check Stripe Dashboard**:
   - Verify the PaymentIntent settings (step 4 above)
   - If it shows `automatic_payment_methods: enabled = true`, an old PI is still being reused

2. **Check Caching**:
   - Restart Flask backend
   - Do hard refresh (`Cmd+Shift+R`)
   - Check console logs for the PI ID
   - Verify in Stripe Dashboard that PI was created AFTER your code changes

3. **Session State**:
   - Clear browser cookies/session storage for your domain
   - Start a new checkout

---

## Summary of Changes

| File | Change | Why |
|------|--------|-----|
| `routes/main.py` | `automatic_payment_methods={'enabled': False}` + `payment_method_types=['card']` | Restrict to card only |
| `routes/main.py` | Added PI cancellation logic | Force fresh PIs |
| `templates/checkout_enhanced.html` | Bumped `?v=...` parameter | Force reload JS |
| `static/js/checkout.js` | Added console logging | Debug PI creation |

---

## Questions?

If payment method tabs still appear after testing:
1. Check the PI ID in console logs
2. Look it up in Stripe Dashboard
3. Confirm `payment_method_types: ["card"]` is set
4. If old PI ID appears, clear session and restart backend
