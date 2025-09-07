#!/usr/bin/env python3
"""
Test script to simulate order notifications
"""
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from routes import db
from models import Product, Order, OrderItem, User
from services.slack_notifications import send_order_notification

def create_test_order():
    """Create a test order to test Slack notifications"""
    with app.app_context():
        try:
            # Get a sample product
            product = Product.query.first()
            if not product:
                print("❌ No products found in database. Please add some products first.")
                return None
            
            print(f"Using product: {product.name} (ID: {product.id}, UPC: {getattr(product, 'upc', 'N/A')})")
            
            # Create a test order
            order = Order(
                order_number=f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                email="test@example.com",
                full_name="John Doe",
                phone="+1-305-555-0123",
                shipping_address="123 Test Street",
                shipping_suite="Apt 4B",
                shipping_city="Miami",
                shipping_state="FL",
                shipping_zip="33132",
                shipping_country="US",
                delivery_type="pickup",  # Test pickup first
                subtotal=Decimal('29.99'),
                shipping_amount=Decimal('0.00'),
                total_amount=Decimal('29.99'),
                payment_method="card",
                payment_status="paid",
                status="processing"
            )
            
            db.session.add(order)
            db.session.flush()  # Get the order ID
            
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                price=product.price,
                quantity=2,
                total=product.price * 2
            )
            
            db.session.add(order_item)
            db.session.commit()
            
            print(f"✅ Created test order: {order.order_number}")
            return order, [{'product_id': product.id, 'quantity': 2}]
            
        except Exception as e:
            print(f"❌ Error creating test order: {str(e)}")
            db.session.rollback()
            return None

def test_pickup_notification():
    """Test pickup order notification"""
    print("\n=== Testing PICKUP Order Notification ===")
    
    order_data = create_test_order()
    if not order_data:
        return False
    
    order, cart_items = order_data
    
    # Send notification (within app context)
    with app.app_context():
        # Re-fetch the product to avoid session issues
        fresh_product = Product.query.get(cart_items[0]['product_id'])
        fresh_cart_items = [{'product': fresh_product, 'quantity': cart_items[0]['quantity']}]
        success = send_order_notification(order, fresh_cart_items)
    
    if success:
        print("✅ Pickup notification sent successfully!")
        print("Check your Slack channel for the pickup order notification.")
    else:
        print("❌ Failed to send pickup notification")
    
    # Clean up test order
    with app.app_context():
        db.session.delete(order)
        db.session.commit()
    
    return success

def test_delivery_notification():
    """Test delivery order notification"""
    print("\n=== Testing DELIVERY Order Notification ===")
    
    with app.app_context():
        try:
            # Get a sample product
            product = Product.query.first()
            if not product:
                print("❌ No products found in database.")
                return False
            
            # Create a delivery test order
            order = Order(
                order_number=f"TEST-DELIVERY-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                email="delivery@example.com",
                full_name="Jane Smith",
                phone="+1-305-555-0456",
                shipping_address="456 Delivery Avenue",
                shipping_suite="Unit 2A",
                shipping_city="Miami Beach",
                shipping_state="FL",
                shipping_zip="33139",
                shipping_country="US",
                delivery_type="delivery",  # Test delivery
                subtotal=Decimal('45.99'),
                shipping_amount=Decimal('5.99'),
                total_amount=Decimal('51.98'),
                payment_method="card",
                payment_status="paid",
                status="processing"
            )
            
            db.session.add(order)
            db.session.flush()
            
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                price=product.price,
                quantity=3,
                total=product.price * 3
            )
            
            db.session.add(order_item)
            db.session.commit()
            
            print(f"✅ Created test delivery order: {order.order_number}")
            
            # Send notification
            cart_items = [{'product': product, 'quantity': 3}]
            success = send_order_notification(order, cart_items)
            
            if success:
                print("✅ Delivery notification sent successfully!")
                print("Check your Slack channel for the delivery order notification.")
            else:
                print("❌ Failed to send delivery notification")
            
            # Clean up test order
            db.session.delete(order)
            db.session.commit()
            
            return success
            
        except Exception as e:
            print(f"❌ Error testing delivery notification: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("🧪 Testing Slack Order Notifications")
    print("=" * 50)
    
    # Test pickup notification
    pickup_success = test_pickup_notification()
    
    # Test delivery notification  
    delivery_success = test_delivery_notification()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"Pickup Notification: {'✅ PASS' if pickup_success else '❌ FAIL'}")
    print(f"Delivery Notification: {'✅ PASS' if delivery_success else '❌ FAIL'}")
    
    if pickup_success and delivery_success:
        print("\n🎉 All tests passed! Your Slack notifications are working correctly.")
        print("💡 Now when customers complete real orders, you'll get notified in Slack!")
    else:
        print("\n⚠️  Some tests failed. Check the error messages above.")