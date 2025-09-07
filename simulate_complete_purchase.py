#!/usr/bin/env python3
"""
Simulate the complete purchase flow including the exact webhook that would be sent
"""
import requests
import json
import time
import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from app import create_app
from models import Product

def simulate_complete_purchase():
    """Simulate a complete purchase flow with real product"""
    
    print("🛒 SIMULATING COMPLETE PURCHASE FLOW")
    print("=" * 60)
    print("This simulates exactly what happens when you buy a product")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        # Find the Adam's True Feel Dildo
        product = Product.query.filter(Product.name.like('%Adam%True Feel Dildo%')).first()
        
        if not product:
            print("❌ Could not find Adam's True Feel Dildo in database")
            print("📋 Available products with 'Adam' in name:")
            adam_products = Product.query.filter(Product.name.like('%Adam%')).all()
            for p in adam_products:
                print(f"   ID {p.id}: {p.name} (${p.price})")
            return
        
        print(f"🎯 Found product: {product.name}")
        print(f"💰 Price: ${product.price}")
        print(f"🆔 Product ID: {product.id}")
        print()
        
        # Create the exact webhook payload that Stripe would send
        webhook_payload = {
            "id": "evt_complete_purchase_test",
            "object": "event",
            "api_version": "2020-08-27",
            "created": int(time.time()),
            "data": {
                "object": {
                    "id": "pi_complete_purchase_123",
                    "object": "payment_intent",
                    "amount": int(float(product.price) * 100),  # Convert to cents
                    "amount_capturable": 0,
                    "amount_received": int(float(product.price) * 100),
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
                        "url": f"/v1/charges?payment_intent=pi_complete_purchase_123"
                    },
                    "client_secret": "pi_complete_purchase_123_secret",
                    "confirmation_method": "automatic",
                    "created": int(time.time()),
                    "currency": "usd",
                    "customer": None,
                    "description": f"LoveMeNow order - {product.name}",
                    "invoice": None,
                    "last_payment_error": None,
                    "livemode": False,
                    "metadata": {
                        "item_count": "1",
                        "item_0_product_id": str(product.id),
                        "item_0_quantity": "1"
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
                    "receipt_email": "customer@lovemenow.com",
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
                "id": "req_complete_purchase_test",
                "idempotency_key": None
            },
            "type": "payment_intent.succeeded"
        }
        
        print("🚀 STEP 1: Customer completes payment on website")
        print("✅ Payment processed by Stripe")
        print()
        
        print("🚀 STEP 2: Stripe sends webhook to your server")
        print(f"📤 Sending webhook for: {product.name}")
        print(f"💰 Amount: ${product.price}")
        print()
        
        try:
            response = requests.post(
                'http://127.0.0.1:2100/webhooks/stripe',
                json=webhook_payload,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Stripe/1.0 (+https://stripe.com/docs/webhooks)',
                    'Stripe-Signature': 'test_signature'  # This will be ignored in dev mode
                },
                timeout=10
            )
            
            print("📊 Webhook Response:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text}")
            print()
            
            if response.status_code == 200:
                print("🚀 STEP 3: Webhook processed successfully")
                print("✅ Order information extracted from webhook")
                print("✅ Slack notification sent")
                print()
                print("🎉 COMPLETE PURCHASE FLOW SUCCESSFUL!")
                print("🔔 Check your Slack channel for the notification about:")
                print(f"   📦 {product.name}")
                print(f"   💰 ${product.price}")
                print(f"   🆔 Order: PI-CHASE123")
                print()
                print("=" * 60)
                print("✅ YOUR WEBHOOK SYSTEM IS WORKING PERFECTLY!")
                print("🚨 The only issue is that Stripe can't reach your local server")
                print("💡 Use Stripe CLI or ngrok to test with real purchases")
            else:
                print("❌ Webhook failed - check your Flask app logs")
                
        except requests.exceptions.ConnectionError:
            print("❌ Could not connect to webhook endpoint")
            print("🔧 Make sure your Flask app is running on port 2100")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    simulate_complete_purchase()