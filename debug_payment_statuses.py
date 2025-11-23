"""
Quick debug: Check what payment_status values exist for orders
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from app import create_app
from routes import db
from models import Order, User

app = create_app()

with app.app_context():
    print("=" * 60)
    print("ALL ORDERS IN DATABASE:")
    print("=" * 60)
    
    all_orders = db.session.query(Order).all()
    print(f"Total orders: {len(all_orders)}\n")
    
    # Group by payment_status
    statuses = {}
    for order in all_orders:
        status = order.payment_status or 'NULL'
        if status not in statuses:
            statuses[status] = []
        statuses[status].append(order)
    
    print("Payment Status Breakdown:")
    for status, orders in sorted(statuses.items()):
        print(f"\n  {status}: {len(orders)} orders")
        for order in orders:
            user_info = f"User: {order.user.email}" if order.user_id else "Guest"
            print(f"    - Order #{order.order_number} | {user_info} | ${order.total_amount}")
    
    print("\n" + "=" * 60)
    print("ORDERS WITH user_id (registered users):")
    print("=" * 60)
    registered = db.session.query(Order).filter(Order.user_id != None).all()
    print(f"Total: {len(registered)}\n")
    for order in registered:
        print(f"  Order #{order.order_number} | {order.user.email} | status={order.payment_status} | ${order.total_amount}")

