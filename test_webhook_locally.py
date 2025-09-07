#!/usr/bin/env python3
"""
Test webhook locally to verify Slack notifications work
"""
import requests
import json

def test_webhook():
    """Test the webhook endpoint directly"""
    
    # Mock Stripe payment_intent.succeeded event
    mock_event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_local_123456",
                "amount": 2999,  # $29.99 in cents
                "receipt_email": "test@example.com",
                "metadata": {
                    "item_count": "1",
                    "item_0_product_id": "1",
                    "item_0_quantity": "1"
                }
            }
        }
    }
    
    print("🧪 TESTING WEBHOOK LOCALLY")
    print("=" * 50)
    print("Sending mock payment_intent.succeeded event to local webhook...")
    
    try:
        response = requests.post(
            'http://127.0.0.1:2100/webhooks/stripe',
            json=mock_event,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook processed successfully!")
            print("🔔 Check your Slack channel for the notification")
        else:
            print("❌ Webhook failed")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Flask app")
        print("Make sure your Flask app is running on port 2100")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_webhook()