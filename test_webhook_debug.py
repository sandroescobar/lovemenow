#!/usr/bin/env python3
"""
Debug script to test webhook functionality
"""
import requests
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def test_webhook_endpoint():
    """Test if webhook endpoint is accessible"""
    webhook_url = "http://127.0.0.1:2100/webhooks/stripe"
    
    # Create a mock payment_intent.succeeded event
    mock_event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_123456789",
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
    
    try:
        print(f"Testing webhook endpoint: {webhook_url}")
        response = requests.post(
            webhook_url,
            json=mock_event,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook endpoint is accessible and responding")
            return True
        else:
            print(f"❌ Webhook endpoint returned error: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to webhook endpoint - is the Flask app running?")
        return False
    except Exception as e:
        print(f"❌ Error testing webhook: {str(e)}")
        return False

if __name__ == "__main__":
    test_webhook_endpoint()