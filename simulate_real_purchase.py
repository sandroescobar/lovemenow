#!/usr/bin/env python3
"""
Simulate a real purchase by calling the webhook endpoint directly
This tests if the webhook processing works when called
"""
import requests
import json
import time

def simulate_purchase_webhook():
    """Simulate what Stripe sends when a real purchase is made"""
    webhook_url = "http://127.0.0.1:2100/webhooks/stripe"
    
    # This is what a real Stripe webhook looks like for payment_intent.succeeded
    real_webhook_payload = {
        "id": "evt_test_webhook",
        "object": "event",
        "api_version": "2020-08-27",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "pi_test_1234567890",
                "object": "payment_intent",
                "amount": 2999,  # $29.99
                "amount_capturable": 0,
                "amount_received": 2999,
                "application": None,
                "application_fee_amount": None,
                "canceled_at": None,
                "cancellation_reason": None,
                "capture_method": "automatic",
                "charges": {
                    "object": "list",
                    "data": [],
                    "has_more": False,
                    "total_count": 0,
                    "url": "/v1/charges?payment_intent=pi_test_1234567890"
                },
                "client_secret": "pi_test_1234567890_secret_test",
                "confirmation_method": "automatic",
                "created": int(time.time()),
                "currency": "usd",
                "customer": None,
                "description": "LoveMeNow order - 2 items",
                "invoice": None,
                "last_payment_error": None,
                "livemode": False,
                "metadata": {
                    "item_count": "2",
                    "item_0_product_id": "1",
                    "item_0_quantity": "1",
                    "item_1_product_id": "2",
                    "item_1_quantity": "1"
                },
                "next_action": None,
                "on_behalf_of": None,
                "payment_method": None,
                "payment_method_options": {
                    "card": {
                        "installments": None,
                        "mandate_options": None,
                        "network": None,
                        "request_three_d_secure": "automatic"
                    }
                },
                "payment_method_types": ["card"],
                "receipt_email": "test@example.com",
                "review": None,
                "setup_future_usage": None,
                "shipping": None,
                "source": None,
                "statement_descriptor": None,
                "statement_descriptor_suffix": None,
                "status": "succeeded",
                "transfer_data": None,
                "transfer_group": None
            }
        },
        "livemode": False,
        "pending_webhooks": 1,
        "request": {
            "id": "req_test_1234567890",
            "idempotency_key": None
        },
        "type": "payment_intent.succeeded"
    }
    
    try:
        print("🧪 Simulating real Stripe webhook call...")
        print(f"Webhook URL: {webhook_url}")
        print(f"Event type: {real_webhook_payload['type']}")
        print(f"Payment Intent ID: {real_webhook_payload['data']['object']['id']}")
        print(f"Amount: ${real_webhook_payload['data']['object']['amount'] / 100}")
        
        response = requests.post(
            webhook_url,
            json=real_webhook_payload,
            headers={
                'Content-Type': 'application/json',
                'Stripe-Signature': 'test_signature'  # This would normally be validated
            },
            timeout=10
        )
        
        print(f"\n📊 Response:")
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Webhook processed successfully!")
            print("🔔 Check your Slack channel for the notification")
            return True
        else:
            print(f"\n❌ Webhook failed with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to webhook endpoint")
        print("💡 Make sure your Flask app is running on http://127.0.0.1:2100")
        print("   Try: python app.py")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 SIMULATING REAL STRIPE PURCHASE WEBHOOK")
    print("=" * 60)
    print("This simulates what happens when someone makes a real purchase")
    print("and Stripe sends a webhook to your server.")
    print("=" * 60)
    
    success = simulate_purchase_webhook()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS! The webhook processing works.")
        print("📝 The issue is that Stripe can't reach your local server.")
        print("💡 Use Stripe CLI or ngrok to forward webhooks for real purchases.")
    else:
        print("❌ FAILED! There's an issue with the webhook processing.")
        print("🔧 Check your Flask app logs for errors.")