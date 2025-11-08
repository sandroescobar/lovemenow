#!/usr/bin/env python
"""
Utility script to identify and report duplicate orders from PaymentIntent race conditions.
This helps you see which orders were created from the same PaymentIntent and which should be refunded.
"""

import os
import sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from routes import db
from models import Order
from sqlalchemy import func, text

def get_duplicate_pi_orders():
    """Find all orders created from the same PaymentIntent"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Checking for duplicate orders from same PaymentIntent...")
        print("=" * 80)
        
        # Find PIs that have multiple orders
        duplicate_pis = db.session.query(
            Order.stripe_session_id,
            func.count(Order.id).label('count')
        ).filter(
            Order.stripe_session_id != None
        ).group_by(
            Order.stripe_session_id
        ).having(
            func.count(Order.id) > 1
        ).all()
        
        if not duplicate_pis:
            print("✅ No duplicate orders found! All PaymentIntents have single orders.")
            return
        
        print(f"⚠️  Found {len(duplicate_pis)} PaymentIntents with multiple orders:\n")
        
        total_duplicate_orders = 0
        total_charge_amount = 0
        
        for pi_id, count in duplicate_pis:
            orders = Order.query.filter_by(stripe_session_id=pi_id).all()
            
            print(f"💳 PaymentIntent: {pi_id}")
            print(f"   Orders: {count}")
            
            for idx, order in enumerate(orders, 1):
                status_icon = "❌" if idx > 1 else "✅"
                print(f"   {status_icon} Order #{idx}: {order.order_number}")
                print(f"      Amount: ${order.total_amount:.2f}")
                print(f"      Status: {order.status} | Payment: {order.payment_status}")
                print(f"      Created: {order.created_at}")
                print(f"      Customer: {order.email}")
                
                if idx > 1:
                    total_duplicate_orders += 1
                    total_charge_amount += float(order.total_amount)
            
            print()
        
        print("=" * 80)
        print(f"📊 SUMMARY:")
        print(f"   Duplicate Orders Found: {total_duplicate_orders}")
        print(f"   Total Overcharged Amount: ${total_charge_amount:.2f}")
        print(f"\n⚠️  ACTION REQUIRED:")
        print(f"   These customers were likely double-charged.")
        print(f"   Recommend contacting them for refunds of duplicate charges.")

def get_orders_with_incomplete_deliveries():
    """Find orders that succeeded on payment but failed on Uber delivery"""
    app = create_app()
    
    with app.app_context():
        print("\n🚚 Checking for orders with failed deliveries...")
        print("=" * 80)
        
        # Orders with "confirmed" status but no successful Uber delivery
        failed_delivery_orders = db.session.query(Order).outerjoin(
            Order.delivery
        ).filter(
            Order.status == 'confirmed',
            Order.delivery_type == 'delivery'
        ).all()
        
        # Filter to those without successful delivery
        no_delivery = [o for o in failed_delivery_orders if not o.delivery or o.delivery.status != 'completed']
        
        if not no_delivery:
            print("✅ No delivery failures found!")
            return
        
        print(f"⚠️  Found {len(no_delivery)} orders with no successful delivery:\n")
        
        for order in no_delivery:
            delivery_status = order.delivery.status if order.delivery else "NO DELIVERY RECORD"
            print(f"Order: {order.order_number}")
            print(f"   Customer: {order.email}")
            print(f"   Amount: ${order.total_amount:.2f}")
            print(f"   Delivery Status: {delivery_status}")
            print(f"   Created: {order.created_at}")
            print(f"   Address: {order.shipping_address}, {order.shipping_city}, {order.shipping_state}")
            print()

def get_recent_suspicious_activity():
    """Find suspicious patterns in recent orders"""
    app = create_app()
    
    with app.app_context():
        print("\n🕵️  Checking for suspicious activity in last 24 hours...")
        print("=" * 80)
        
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent = Order.query.filter(Order.created_at >= yesterday).all()
        
        print(f"\nRecent orders (last 24h): {len(recent)}")
        
        # Check for same email with multiple orders in short time
        email_groups = {}
        for order in recent:
            if order.email not in email_groups:
                email_groups[order.email] = []
            email_groups[order.email].append(order)
        
        suspicious = {k: v for k, v in email_groups.items() if len(v) > 1}
        
        if suspicious:
            print(f"\n⚠️  Found {len(suspicious)} customers with multiple recent orders:")
            for email, orders in suspicious.items():
                print(f"\n   Email: {email}")
                for order in orders:
                    print(f"   • {order.order_number} - ${order.total_amount:.2f} - {order.created_at}")
        else:
            print("✅ No suspicious duplicate customers found")

if __name__ == '__main__':
    try:
        get_duplicate_pi_orders()
        get_orders_with_incomplete_deliveries()
        get_recent_suspicious_activity()
        
        print("\n" + "=" * 80)
        print("✅ Analysis complete!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)