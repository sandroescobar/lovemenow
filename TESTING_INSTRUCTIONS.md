# 🧪 TESTING INSTRUCTIONS FOR BOTH FIXES

## Prerequisites
1. Make sure your Flask app is running on port 2100
2. Open browser developer console (F12) to see JavaScript logs

## Test 1: Cart Quantity Validation Fix

### Automated Test:
```bash
python3 test_both_issues.py
```

### Manual Test:
1. Go to any product with limited stock (e.g., product ID 1)
2. Open browser console (F12)
3. Add 1 item to cart from product detail page
4. Try to add another item
5. **Expected Result**: 
   - Should show error message
   - Console should show: "📥 Cart API response: {error: '...', max_additional: 0}"
   - Quantity input should be adjusted

### Debug Steps if Not Working:
1. Check console for JavaScript errors
2. Look for these console messages:
   - "🛒 addToCart called with: ..."
   - "📤 Sending to cart API: ..."
   - "📥 Cart API response: ..."
3. If API response shows success when it should fail, backend issue
4. If no API call is made, frontend issue

## Test 2: Slack Notifications Fix

### Step 1: Configure Slack Webhook
Add to your `.env` file:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

### Step 2: Enable Webhook Forwarding
Choose ONE option:

#### Option A: Stripe CLI (Recommended)
```bash
# In a separate terminal:
./setup_stripe_cli_webhooks.sh
```

#### Option B: ngrok
```bash
# In a separate terminal:
python3 setup_local_webhooks.py
```

#### Option C: Manual Test (No Forwarding Needed)
```bash
python3 test_webhook_locally.py
```

### Step 3: Test Real Purchase
1. Make sure webhook forwarding is running
2. Add items to cart on your local site
3. Go through checkout and pay
4. **Expected Result**: Slack notification should appear immediately

## Troubleshooting

### Cart Issue Still Happening?
- Check if JavaScript changes were applied
- Look for console errors
- Verify backend validation is working with: `python3 test_both_issues.py`

### Slack Notifications Not Working?
1. **Check .env file**: Make sure SLACK_WEBHOOK_URL is set
2. **Test webhook directly**: Run `python3 test_webhook_locally.py`
3. **Check webhook forwarding**: Make sure Stripe CLI or ngrok is running
4. **Verify Stripe webhook**: Check Stripe Dashboard webhook logs

## Expected Console Output (Cart Test)

When testing cart on product detail page, you should see:
```
🛒 addToCart called with: {productId: 1, productName: "...", price: 29.99, variantId: null}
🔍 Found button: <button class="btn-add-cart" ...>
📦 quantityOnHand from button: 1
🔢 Attempting to add 1 items. Stock available: 1
🚀 Calling addToCartWithQuantity - backend will validate stock limits
📤 Sending to cart API: {product_id: 1, quantity: 1}
📥 Cart API response: {error: "This item is already at maximum quantity in your cart", max_additional: 0}
```

## Success Criteria

### ✅ Cart Fix Working:
- First add succeeds
- Second add fails with proper error message
- Quantity input adjusts automatically
- Console shows proper API responses

### ✅ Slack Fix Working:
- Webhook test returns 200 status
- Slack notification appears in channel
- Real purchases trigger notifications

## Quick Fix Commands

If issues persist:

```bash
# Restart Flask app
# Ctrl+C to stop, then:
python main.py

# Clear browser cache and reload page
# Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

# Test webhook directly
python3 test_webhook_locally.py

# Test cart API directly
python3 test_both_issues.py
```