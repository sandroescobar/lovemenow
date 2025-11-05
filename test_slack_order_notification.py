#!/usr/bin/env python
"""
Test script to verify Slack order notifications are working correctly
Tests both delivery and pickup orders
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to the path
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from app import create_app
from routes import db
from models import Product, Order, OrderItem
from services.slack_notifications import send_order_notification

# Create app context
app = create_app()

def test_slack_notification():
    """Test Slack notification with a mock order"""
    
    with app.app_context():
        # Check if webhook URL is configured
        webhook_url = app.config.get('SLACK_WEBHOOK_URL')
        print(f"\n🔍 SLACK WEBHOOK STATUS:")
        print(f"   Webhook URL configured: {'✅ YES' if webhook_url else '❌ NO'}")
        if webhook_url:
            print(f"   Webhook URL (masked): {webhook_url[:50]}...{webhook_url[-10:]}")
        else:
            print(f"   ⚠️  Add SLACK_WEBHOOK_URL to your .env file")
            return False
        
        print(f"\n📝 Creating test order for notification...")
        
        # Create a mock order object (without saving to DB)
        mock_order = type('Order', (), {
            'order_number': 'LMN20250924205618',
            'full_name': 'Alessandro Escobar',
            'email': 'alessandro.escobarFIU@gmail.com',
            'phone': '9542790079',
            'shipping_address': '123 Test Street',
            'shipping_suite': 'Suite 100',
            'shipping_city': 'Miami',
            'shipping_state': 'FL',
            'shipping_zip': '33132',
            'total_amount': 6.99,
            'delivery_type': 'pickup',
            'created_at': datetime.utcnow()
        })()
        
        # Create mock product and order items
        mock_product = type('Product', (), {
            'id': 1,
            'name': 'Earthly Body — Massage Oil, Unscented (2 oz)',
            'price': 6.99,
            'upc': '879959004601',
            'wholesale_id': '53845'
        })()
        
        # Create order items list
        order_items = [{
            'product': mock_product,
            'quantity': 1
        }]
        
        print(f"\n🛍️ ORDER DETAILS:")
        print(f"   Order #: {mock_order.order_number}")
        print(f"   Customer: {mock_order.full_name}")
        print(f"   Email: {mock_order.email}")
        print(f"   Phone: {mock_order.phone}")
        print(f"   Items: 1")
        print(f"   Total: ${mock_order.total_amount:.2f}")
        print(f"   Fulfillment: {'🚗 Delivery' if mock_order.delivery_type == 'delivery' else '🏪 Store Pickup'}")
        
        # Send test notification
        print(f"\n📤 Sending Slack notification...")
        try:
            success = send_order_notification(mock_order, order_items)
            
            if success:
                print(f"   ✅ Slack notification sent successfully!")
                print(f"\n   Check your Slack workspace for the message.")
                print(f"   It should include:")
                print(f"     • Order number and customer info")
                print(f"     • Product details (UPC, Wholesale ID)")
                print(f"     • Total amount and fulfillment type")
                print(f"     • Order timestamp in EST")
                return True
            else:
                print(f"   ❌ Failed to send Slack notification")
                print(f"   Check the logs for error details")
                return False
                
        except Exception as e:
            print(f"   ❌ Error sending notification: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

def test_slack_delivery_order():
    """Test Slack notification with a delivery order"""
    
    with app.app_context():
        webhook_url = app.config.get('SLACK_WEBHOOK_URL')
        if not webhook_url:
            print(f"❌ SLACK_WEBHOOK_URL not configured")
            return False
        
        print(f"\n\n📦 TESTING DELIVERY ORDER NOTIFICATION:")
        print(f"{'='*60}")
        
        # Create a mock delivery order
        mock_order = type('Order', (), {
            'order_number': 'LMN20250925123456',
            'full_name': 'Test Customer',
            'email': 'test@example.com',
            'phone': '5551234567',
            'shipping_address': '456 Delivery Ave',
            'shipping_suite': 'Apt 200',
            'shipping_city': 'Miami',
            'shipping_state': 'FL',
            'shipping_zip': '33139',
            'total_amount': 29.99,
            'delivery_type': 'delivery',
            'created_at': datetime.utcnow(),
            'delivery': None  # No Uber tracking yet
        })()
        
        # Create mock products
        order_items = [
            {
                'product': type('Product', (), {
                    'id': 1,
                    'name': 'Product 1',
                    'price': 14.99,
                    'upc': '111111111111',
                    'wholesale_id': '10001'
                })(),
                'quantity': 1
            },
            {
                'product': type('Product', (), {
                    'id': 2,
                    'name': 'Product 2',
                    'price': 15.00,
                    'upc': '222222222222',
                    'wholesale_id': '10002'
                })(),
                'quantity': 1
            }
        ]
        
        print(f"\n🛍️ ORDER DETAILS:")
        print(f"   Order #: {mock_order.order_number}")
        print(f"   Customer: {mock_order.full_name}")
        print(f"   Address: {mock_order.shipping_address}, {mock_order.shipping_city}, {mock_order.shipping_state}")
        print(f"   Items: {len(order_items)}")
        print(f"   Total: ${mock_order.total_amount:.2f}")
        print(f"   Fulfillment: 🚗 Delivery")
        
        # Send test notification
        print(f"\n📤 Sending Slack notification...")
        try:
            success = send_order_notification(mock_order, order_items)
            
            if success:
                print(f"   ✅ Delivery notification sent successfully!")
                return True
            else:
                print(f"   ❌ Failed to send notification")
                return False
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🧪 SLACK ORDER NOTIFICATION TEST")
    print("="*60)
    
    # Test pickup order
    success1 = test_slack_notification()
    
    # Test delivery order
    success2 = test_slack_delivery_order()
    
    print("\n" + "="*60)
    if success1 and success2:
        print("✅ ALL TESTS PASSED - Slack integration is working!")
        print("\nYour orders will now send Slack notifications when:")
        print("  1. Payment is received (Stripe webhook)")
        print("  2. Delivery status updates (Uber webhook)")
    else:
        print("❌ TESTS FAILED - Check your SLACK_WEBHOOK_URL configuration")
    print("="*60 + "\n")