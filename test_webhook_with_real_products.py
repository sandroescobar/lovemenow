#!/usr/bin/env python3
"""
Test webhook with real products from the database
"""
import requests
import json
import time

def test_webhook_with_real_products():
    """Test the webhook with actual products from the database"""
    
    print("🚀 TESTING WEBHOOK WITH REAL PRODUCTS")
    print("=" * 60)
    print("This test uses actual products from your database")
    print("=" * 60)
    
    # Create a realistic payment intent webhook payload using real product IDs
    webhook_payload = {
        "id": "evt_test_webhook",
        "object": "event",
        "api_version": "2020-08-27",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "pi_test_real_products_123",
                "object": "payment_intent",
                "amount": 4498,  # $44.98 (21.99 + 22.99)
                "amount_capturable": 0,
                "amount_received": 4498,
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
                    "url": "/v1/charges?payment_intent=pi_test_real_products_123"
                },
                "client_secret": "pi_test_real_products_123_secret_test",
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
                    "item_0_product_id": "1",  # Rianne S — Ana's Trilogy III Kit ($21.99)
                    "item_0_quantity": "1",
                    "item_1_product_id": "3",  # Darque — Fetish Mask, Black (O/S) ($22.99)
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
                "processing": None,
                "receipt_email": "customer@example.com",
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
            "id": "req_test_webhook",
            "idempotency_key": None
        },
        "type": "payment_intent.succeeded"
    }
    
    print("🧪 Simulating webhook call...")
    print(f"Webhook URL: http://127.0.0.1:2100/webhooks/stripe")
    print(f"Event type: payment_intent.succeeded")
    print(f"Payment Intent ID: pi_test_real_products_123")
    print(f"Products:")
    print(f"  • ID 1: Rianne S — Ana's Trilogy III Kit ($21.99)")
    print(f"  • ID 3: Darque — Fetish Mask, Black (O/S) ($22.99)")
    print(f"Total: $44.98")
    print()
    
    try:
        response = requests.post(
            'http://127.0.0.1:2100/webhooks/stripe',
            json=webhook_payload,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Stripe/1.0 (+https://stripe.com/docs/webhooks)'
            },
            timeout=10
        )
        
        print("📊 Response:")
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        print()
        
        if response.status_code == 200:
            print("✅ Webhook processed successfully!")
            print("🔔 Check your Slack channel for the notification")
            print()
            print("=" * 60)
            print("🎉 SUCCESS! The webhook should have sent a Slack notification")
            print("📝 Look for a message about order PI-DUCTS123 with:")
            print("   • Rianne S — Ana's Trilogy III Kit ($21.99)")
            print("   • Darque — Fetish Mask, Black (O/S) ($22.99)")
            print("   • Total: $44.98")
        else:
            print(f"❌ Webhook failed with status {response.status_code}")
            print()
            print("=" * 60)
            print("❌ FAILED! There's an issue with the webhook processing.")
            print("🔧 Check your Flask app logs for errors.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to webhook endpoint - is the Flask app running?")
    except Exception as e:
        print(f"❌ Error testing webhook: {str(e)}")

if __name__ == "__main__":
    test_webhook_with_real_products()