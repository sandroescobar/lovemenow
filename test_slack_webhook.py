#!/usr/bin/env python3
"""
Test script to simulate a Stripe webhook and test Slack notifications
"""
import requests
import json
import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from dotenv import load_dotenv
from services.slack_notifications import send_order_notification

# Load environment variables
load_dotenv()

def test_slack_notification_directly():
    """Test Slack notification directly without webhook"""
    print("🧪 Testing Slack notification directly...")
    
    # Create Flask app context
    try:
        from app import create_app
        app = create_app('development')
        
        with app.app_context():
            # Create a mock order object
            from datetime import datetime
            class MockOrder:
                def __init__(self):
                    self.order_number = "TEST-12345678"
                    self.total_amount = 29.99
                    self.delivery_type = "pickup"
                    self.email = "test@example.com"
                    self.payment_status = "paid"
                    self.full_name = "Test Customer"
                    self.shipping_address = "123 Test St"
                    self.shipping_suite = "Apt 1"
                    self.shipping_city = "Miami"
                    self.shipping_state = "FL"
                    self.shipping_zip = "33132"
                    self.created_at = datetime.now()
            
            # Create mock cart items
            class MockProduct:
                def __init__(self, id, name, price):
                    self.id = id
                    self.name = name
                    self.price = price
            
            mock_cart_items = [
                {
                    'product': MockProduct(1, "Test Product 1", 19.99),
                    'quantity': 1
                },
                {
                    'product': MockProduct(2, "Test Product 2", 9.99),
                    'quantity': 1
                }
            ]
            
            # Test the Slack notification
            success = send_order_notification(MockOrder(), mock_cart_items)
            if success:
                print("✅ Slack notification sent successfully!")
                print("Check your #lovemenowmiami_orders channel")
            else:
                print("❌ Slack notification failed")
            return success
            
    except Exception as e:
        print(f"❌ Error testing Slack notification: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def test_webhook_endpoint_locally():
    """Test the webhook endpoint with a mock payment intent"""
    webhook_url = "http://127.0.0.1:2900/webhooks/stripe"
    
    # Create a mock payment_intent.succeeded event
    mock_event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_123456789",
                "amount": 2999,  # $29.99 in cents
                "receipt_email": "test@example.com",
                "metadata": {
                    "item_count": "2",
                    "item_0_product_id": "1",
                    "item_0_quantity": "1",
                    "item_1_product_id": "2", 
                    "item_1_quantity": "1"
                }
            }
        }
    }
    
    try:
        print(f"🧪 Testing webhook endpoint: {webhook_url}")
        response = requests.post(
            webhook_url,
            json=mock_event,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook endpoint processed successfully!")
            print("Check your #lovemenowmiami_orders channel")
            return True
        else:
            print(f"❌ Webhook endpoint returned error: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to webhook endpoint")
        print("Make sure your Flask app is running on http://127.0.0.1:2900")
        return False
    except Exception as e:
        print(f"❌ Error testing webhook: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 TESTING SLACK NOTIFICATIONS")
    print("=" * 60)
    
    print("\n1. Testing Slack notification directly (bypassing webhook)...")
    direct_success = test_slack_notification_directly()
    
    print("\n" + "=" * 60)
    print("\n2. Testing webhook endpoint with mock payment intent...")
    webhook_success = test_webhook_endpoint_locally()
    
    print("\n" + "=" * 60)
    print("📊 RESULTS:")
    print(f"Direct Slack test: {'✅ PASSED' if direct_success else '❌ FAILED'}")
    print(f"Webhook test: {'✅ PASSED' if webhook_success else '❌ FAILED'}")
    
    if direct_success and webhook_success:
        print("\n🎉 All tests passed! Slack notifications should work.")
    elif direct_success:
        print("\n⚠️  Slack works but webhook has issues. Check Flask app is running.")
    else:
        print("\n❌ Slack notification has issues. Check configuration.")