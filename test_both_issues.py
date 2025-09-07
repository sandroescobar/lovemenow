#!/usr/bin/env python3
"""
Test both issues: Cart quantity validation and Slack notifications
"""
import requests
import json
import time

def test_cart_issue():
    """Test the cart quantity validation issue"""
    print("🛒 TESTING CART QUANTITY VALIDATION")
    print("=" * 50)
    
    base_url = 'http://127.0.0.1:2100'
    
    # Test with product ID 1 (has quantity_on_hand = 1)
    product_id = 1
    
    print(f"Testing with Product ID: {product_id}")
    print("Expected: First add succeeds, second add fails with proper error")
    print()
    
    # Clear any existing cart first
    try:
        requests.post(f'{base_url}/api/cart/clear', 
                     headers={'Content-Type': 'application/json'})
        print("🧹 Cleared existing cart")
    except:
        pass
    
    # Test 1: Add 1 item (should succeed)
    print("🧪 TEST 1: Adding 1 item (should succeed)")
    try:
        response1 = requests.post(f'{base_url}/api/cart/add', 
                                 json={'product_id': product_id, 'quantity': 1},
                                 headers={'Content-Type': 'application/json'})
        
        print(f"   Status: {response1.status_code}")
        if response1.status_code == 200:
            data = response1.json()
            print(f"   ✅ SUCCESS: {data.get('message', 'Added to cart')}")
        else:
            print(f"   ❌ FAILED: {response1.text}")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    print()
    
    # Test 2: Try to add another item (should fail)
    print("🧪 TEST 2: Adding another item (should fail with proper error)")
    try:
        response2 = requests.post(f'{base_url}/api/cart/add', 
                                 json={'product_id': product_id, 'quantity': 1},
                                 headers={'Content-Type': 'application/json'})
        
        print(f"   Status: {response2.status_code}")
        if response2.status_code == 400:
            data = response2.json()
            print(f"   ✅ SUCCESS: Properly rejected with error: {data.get('error')}")
            if 'max_additional' in data:
                print(f"   ✅ SUCCESS: max_additional field present: {data['max_additional']}")
            else:
                print(f"   ⚠️  WARNING: max_additional field missing")
            return True
        else:
            print(f"   ❌ FAILED: Should have returned 400, got {response2.status_code}")
            print(f"   Response: {response2.text}")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_slack_webhook():
    """Test the Slack webhook functionality"""
    print("\n🔔 TESTING SLACK WEBHOOK")
    print("=" * 50)
    
    base_url = 'http://127.0.0.1:2100'
    
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
    
    print("Sending mock payment_intent.succeeded event...")
    
    try:
        response = requests.post(
            f'{base_url}/webhooks/stripe',
            json=mock_event,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Webhook processed successfully!")
            print("🔔 Check your Slack channel for the notification")
            print("   If no notification appears, the issue is:")
            print("   1. SLACK_WEBHOOK_URL not configured in .env")
            print("   2. Slack webhook URL is incorrect")
            print("   3. Network connectivity issue")
            return True
        else:
            print(f"❌ Webhook failed: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Flask app")
        print("Make sure your Flask app is running on port 2100")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🧪 TESTING BOTH ISSUES")
    print("=" * 60)
    print("Make sure your Flask app is running on port 2100")
    print("=" * 60)
    
    # Test cart issue
    cart_success = test_cart_issue()
    
    # Test webhook issue
    webhook_success = test_slack_webhook()
    
    print("\n" + "=" * 60)
    print("🎯 SUMMARY:")
    print(f"Cart Validation: {'✅ WORKING' if cart_success else '❌ BROKEN'}")
    print(f"Slack Webhooks: {'✅ WORKING' if webhook_success else '❌ BROKEN'}")
    
    if not cart_success:
        print("\n🔧 CART FIX NEEDED:")
        print("- Check browser console for JavaScript errors")
        print("- Verify backend validation is working")
        print("- Check if frontend is properly calling API")
    
    if not webhook_success:
        print("\n🔧 SLACK FIX NEEDED:")
        print("- Add SLACK_WEBHOOK_URL to your .env file")
        print("- Use ngrok or Stripe CLI to forward webhooks")
        print("- Check Slack webhook URL is correct")

if __name__ == "__main__":
    main()