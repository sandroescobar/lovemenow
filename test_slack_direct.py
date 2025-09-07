#!/usr/bin/env python3
"""
Test Slack notification directly
"""
import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from app import create_app
from models import Product
from services.slack_notifications import send_order_notification

def test_slack_notification():
    """Test sending a Slack notification directly"""
    app = create_app()
    
    with app.app_context():
        print("🔔 TESTING SLACK NOTIFICATION DIRECTLY")
        print("=" * 50)
        
        # Get real products from database
        product1 = Product.query.get(1)  # Ana's Trilogy III Kit
        product3 = Product.query.get(3)  # Fetish Mask
        
        if not product1 or not product3:
            print("❌ Could not find test products in database")
            return
        
        print(f"✅ Found products:")
        print(f"   • {product1.name} (${product1.price})")
        print(f"   • {product3.name} (${product3.price})")
        print()
        
        # Create mock order
        from datetime import datetime
        mock_order = type('Order', (), {
            'order_number': 'TEST-DIRECT-SLACK',
            'total_amount': float(product1.price) + float(product3.price),
            'delivery_type': 'pickup',
            'email': 'test@example.com',
            'payment_status': 'paid',
            'full_name': 'Test Customer',
            'phone': '+1-555-123-4567',
            'created_at': datetime.now()  # Only needed for Slack formatting
        })()
        
        # Create cart items
        cart_items = [
            {'product': product1, 'quantity': 1},
            {'product': product3, 'quantity': 1}
        ]
        
        print("📤 Sending Slack notification...")
        try:
            success = send_order_notification(mock_order, cart_items)
            if success:
                print("✅ Slack notification sent successfully!")
                print("🔔 Check your Slack channel for the notification")
            else:
                print("❌ Slack notification failed")
        except Exception as e:
            print(f"❌ Error sending Slack notification: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_slack_notification()