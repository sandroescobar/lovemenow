# Slack Order Notifications Setup Guide

## ✅ Status
Slack integration is fully implemented and ready to use. Just need to add your webhook URL to the `.env` file.

## 📋 What's Already Configured

### Message Format
Your Slack notifications will show:
```
🛍️ *NEW ORDER - LMN20250924205618*

👤 *Customer:* Alessandro Escobar
📧 *Email:* alessandro.escobarFIU@gmail.com
📱 *Phone:* 9542790079
📦 *Items:*
• Earthly Body — Massage Oil, Unscented (2 oz)
  - Wholesale ID: 53845
  - UPC: 879959004601
  - Quantity: 1

🚚 *Fulfillment:* 🏪 Store Pickup
💰 *Total:* $6.99

⏰ *Order Time:* 04:56 PM on 09/24/2025 EST

🏪 LoveMeNow Miami | Order #LMN20250924205618
```

### Automatic Triggers
Slack notifications are sent automatically when:
- ✅ Customer completes a Stripe payment (both card and Apple Pay)
- ✅ Works for both **Store Pickup** orders
- ✅ Works for both **Delivery** orders
- ✅ Includes Uber tracking link when driver is assigned

## 🔧 Setup Instructions

### Step 1: Add Webhook URL to `.env`
Edit your `.env` file and add this line:
```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/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
```

### Step 2: Verify Configuration (Local Testing)
Run the test script:
```bash
python test_slack_order_notification.py
```

Expected output:
```
============================================================
🧪 SLACK ORDER NOTIFICATION TEST
============================================================

🔍 SLACK WEBHOOK STATUS:
   Webhook URL configured: ✅ YES
   Webhook URL (masked): https://hooks.slack.com/services/T09DXP...EC0OT75

📝 Creating test order for notification...

🛍️ ORDER DETAILS:
   Order #: LMN20250924205618
   Customer: Alessandro Escobar
   Email: alessandro.escobarFIU@gmail.com
   Phone: 9542790079
   Items: 1
   Total: $6.99
   Fulfillment: 🏪 Store Pickup

📤 Sending Slack notification...
   ✅ Slack notification sent successfully!

   Check your Slack workspace for the message.
```

### Step 3: Deploy to Production (Render)
1. Push your code changes:
```bash
git add .env.example SLACK_WEBHOOK_SETUP.md test_slack_order_notification.py
git commit -m "Add Slack webhook URL to environment"
git push
```

2. The app will automatically load the webhook URL from the environment variables

3. Check Render logs for: `Slack notification sent successfully`

## 🧪 Test In Production

After deploying:
1. Complete a test purchase on your production site
2. Check your Slack channel for the notification
3. Verify all details appear correctly

## 📊 Message Details

### For Pickup Orders
```
🚚 *Fulfillment:* 🏪 Store Pickup
```

### For Delivery Orders
```
🚚 *Fulfillment:* 🚗 Delivery
📍 *Delivery Address:* [Full Address]
🚚 *Track Driver:* [Uber Tracking Link]
```

## 🔍 Troubleshooting

### Issue: No Slack notifications appearing

**Check 1: Webhook URL in environment**
```python
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('SLACK_WEBHOOK_URL'))"
```

**Check 2: Application logs**
On Render, check "Logs" tab for:
- `Slack notification sent successfully` (success)
- `Failed to send Slack notification` (error)
- `Webhook URL not configured` (missing env var)

**Check 3: Test webhook directly**
```bash
curl -X POST https://hooks.slack.com/services/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 \
  -H 'Content-type: application/json' \
  -d '{"text":"Test message"}'
```

### Issue: Old messages from September

**Root Cause:** Webhook URL was missing or incorrect

**Solution:** The new setup will start sending notifications immediately once:
1. ✅ Webhook URL is added to `.env`
2. ✅ App is restarted/redeployed

All future orders will appear in Slack automatically.

## 📝 Files Involved

- **`services/slack_notifications.py`** - Sends Slack messages
- **`routes/webhooks.py`** - Triggers Slack on payment completion
- **`routes/email_utils.py`** - Also sends email confirmations
- **`config.py`** - Loads `SLACK_WEBHOOK_URL` from environment
- **`test_slack_order_notification.py`** - Test script you can run locally

## ✨ Features

✅ **Multi-channel capable:** Can add more webhooks for different channels (orders, deliveries, etc.)

✅ **Rich formatting:** Uses Slack's Block Kit for professional appearance

✅ **Automatic enrichment:**
- Converts UTC timestamps to Eastern Time (EST)
- Includes product UPC and Wholesale ID
- Shows Uber tracking links for deliveries

✅ **Error resilient:** Failed Slack notifications don't block order processing

✅ **Complete information:**
- Customer contact details
- Product quantities and prices
- Fulfillment method
- Exact order timestamp

## 🚀 Next Steps

1. Add webhook URL to `.env` file
2. Run test script locally: `python test_slack_order_notification.py`
3. Deploy to Render
4. Make a test purchase
5. Verify notification appears in Slack

---

**Status:** Ready to go! Just add the webhook URL and you're all set. ✅