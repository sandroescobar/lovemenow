# PaymentIntent Duplicate Charge Fix

## Problem Summary

**The Issue**: Multiple PaymentIntents were being created during checkout, and when a payment completed on one of them, Stripe could charge multiple PIs simultaneously. This resulted in:

1. ✅ One order created (succeeded)
2. ❌ Another order also created (duplicate charge)
3. 🚫 Uber delivery failed on one order due to address/quote mismatch
4. 💸 Customer charged twice, but only got one delivery

**Root Cause**: Two separate checkout endpoints both creating PaymentIntents without properly cancelling old ones:
- `/create-checkout-session` in `main.py` - ✅ Had cancellation logic
- `/api/create-checkout-session` in `api.py` - ❌ **DID NOT cancel old ones** (RACE CONDITION)

When a customer modified their delivery address or the form changed, new PIs could be created while old ones were still settling, creating a race condition.

---

## Solution Implemented

### 1. **Synced Both Endpoints** ✅

**`routes/api.py` - `/create-checkout-session` (Line 399-407)**
```python
# 🔒 CRITICAL FIX: Cancel stale PaymentIntent if one exists in session
try:
    old_pi = session.get("active_pi_id")
    if old_pi:
        stripe.PaymentIntent.cancel(old_pi)
        current_app.logger.info(f"Cancelled stale PI: {old_pi}")
except Exception as e:
    current_app.logger.warning(f"Failed to cancel old PI: {str(e)}")
```

Now BOTH endpoints:
- Cancel any old PaymentIntent from the session
- Create a fresh PaymentIntent
- Store it in `session["active_pi_id"]` for next time

**Result**: Only ONE active PaymentIntent per checkout session at any time.

---

### 2. **Added Duplicate Order Prevention** ✅

**`routes/api.py` - `/create-order` (Line 451-466)**
```python
# 🔒 CRITICAL FIX: Check if an order was ALREADY created from this PaymentIntent
existing_order = Order.query.filter_by(stripe_session_id=pi_id).first()
if existing_order:
    # Return success but DON'T create another order
    return jsonify({
        'success': True,
        'order_number': existing_order.order_number,
        'message': 'Order already exists for this payment',
    }), 200
```

**How it works**:
- When `/create-order` is called with a PaymentIntent ID
- Check if an order already exists for that PI
- If yes: return the existing order (don't charge again)
- If no: create the order normally

**Result**: Even if the same PI somehow completes twice, only ONE order is created.

---

### 3. **Added Tracking Fields to Order Model** ✅

**`models.py` - Order model (Line 345-348)**
```python
# Track if this order is a duplicate from same PI or was cancelled
is_duplicate_payment = db.Column(db.Boolean, default=False)
payment_intent_status_at_creation = db.Column(db.String(50), nullable=True)
cancellation_reason = db.Column(db.String(255), nullable=True)
```

**Benefits**:
- **Debug visibility**: You can see which orders were from duplicate PIs
- **Admin filtering**: Filter orders where `is_duplicate_payment=True` to find affected customers
- **Audit trail**: Track PI status at time of order creation
- **Future prevention**: Spot patterns of problematic PIs

---

### 4. **Clear Session After Order** ✅

**`routes/api.py` - After order commit (Line 576)**
```python
# 🔒 Clear the PaymentIntent from session so it can't be reused
session.pop('active_pi_id', None)
```

Once an order is created from a PaymentIntent, it's removed from the session so:
- It can't be accidentally reused
- Next checkout gets a completely fresh session
- Multiple PIs can't compete for the same order

---

## Files Changed

1. **`models.py`** (Lines 345-348)
   - Added 3 new tracking columns to Order model

2. **`routes/api.py`** (Multiple sections)
   - Line 399-407: Added PI cancellation logic to `/create-checkout-session`
   - Line 451-466: Added duplicate order prevention to `/create-order`
   - Line 497-499: Added tracking fields when creating order
   - Line 576: Clear session after order creation

3. **NEW: `migrate_payment_intent_tracking.py`**
   - Migration script to add columns to existing database

4. **NEW: `check_duplicate_orders.py`**
   - Admin utility to identify affected orders and customers

---

## Database Migration

### Run the migration:
```bash
python migrate_payment_intent_tracking.py
```

This adds the 3 new columns to the orders table. **Fully backward compatible** - doesn't touch existing data.

### Verify it worked:
```bash
python check_duplicate_orders.py
```

This shows:
- ✅ Any duplicate orders found (same PI, multiple orders)
- ✅ Orders with failed deliveries despite successful payment
- ✅ Suspicious activity patterns (same customer multiple orders)

---

## Testing Your Local Fix

### Test Case 1: Address Change (Quote-Locking ✅ + PI Fix ✅)
1. Add item to cart
2. Get delivery quote (quote locks)
3. Change address **multiple times** → Quote is reused, single PI stays active
4. Submit payment → **RESULT**: Single order, single charge ✅

### Test Case 2: Rapid Form Changes (NEW FIX)
1. Add item to cart
2. Click "Get Quote" 
3. **Quickly** click "Get Quote" again while first one loading → New PI cancels old PI
4. Complete payment → **RESULT**: Single order ✅

### Test Case 3: Duplicate Order Prevention (NEW FIX)
*(Requires manual testing in Stripe dashboard)*
1. Create order normally → Order creates successfully
2. Manually call `/api/create-order` with same PI ID again
3. **RESULT**: Returns existing order, no new order created ✅

---

## How to Monitor

### Admin Dashboard Check
```python
# See duplicate orders
duplicates = Order.query.filter_by(is_duplicate_payment=True).all()

# See failed Uber deliveries
failed = Order.query.filter_by(status='confirmed', delivery_type='delivery').all()
failed = [o for o in failed if not o.delivery or o.delivery.status != 'completed']

# See PI status tracking
for order in Order.query.all():
    print(f"{order.order_number}: PI Status = {order.payment_intent_status_at_creation}")
```

### Log Monitoring
Look for these log messages:
- ✅ `Cancelled stale PI: pi_xxx` - Old PI was cancelled
- ✅ `Created new PI: pi_xxx` - Fresh PI created
- ⚠️  `Duplicate order attempt detected! PI xxx already created order #LMN...` - Prevention worked
- ✅ `Order created successfully: LMN... (PI: pi_xxx)` - Order created

---

## Backward Compatibility

✅ **Fully backward compatible**:
- Existing orders unaffected
- New columns default to `NULL` or `False`
- Old checkout code still works
- Migration script is optional (but recommended)

---

## What This DOESN'T Fix

**This fix addresses the PaymentIntent duplicate issue specifically.** It doesn't change:
- ✅ Quote-locking (already fixed in previous change)
- ✅ Store hours validation (already implemented)
- Address formatting issues (handled separately)

**Combined with the quote-locking fix**, these two changes eliminate the double-charge race condition.

---

## Summary of Changes

| Issue | Before | After |
|-------|--------|-------|
| Multiple PIs created during checkout | ❌ Race condition | ✅ Only 1 active PI per session |
| PI in api.py cancels old ones | ❌ No | ✅ Yes (synced with main.py) |
| Duplicate orders from same PI | ❌ Creates multiple | ✅ Prevents 2nd order |
| Visibility into duplicates | ❌ Hidden | ✅ Trackable with new fields |
| Session cleanup | ❌ PI reused | ✅ Cleared after order |
| Admin audit trail | ❌ None | ✅ Full tracking |

---

## Next Steps

1. **Run migration**: `python migrate_payment_intent_tracking.py`
2. **Check for existing duplicates**: `python check_duplicate_orders.py`
3. **Test locally** with the test cases above
4. **Deploy to production**
5. **Monitor logs** for cancellation/creation patterns
6. **Review any flagged duplicates** for potential refunds

---

## Questions?

If you see:
- `Duplicate order attempt detected` → Good! Prevention is working
- Multiple orders with same `stripe_session_id` → Contact those customers for refund
- `Payment not completed. Status: canceled` → Customer likely hit back button or had network issue

All of these are now tracked and debuggable thanks to the new fields.