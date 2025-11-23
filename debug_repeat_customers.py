"""
Debug: Check repeat customer query logic in detail
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
    print("REGISTERED USERS WITH PAID ORDERS:")
    print("=" * 60)
    
    # Same query as email_campaign_preview.py
    users_with_orders = db.session.query(User).join(
        Order, User.id == Order.user_id
    ).filter(
        Order.payment_status == 'paid'
    ).distinct().all()
    
    print(f"\nFound {len(users_with_orders)} users with paid orders\n")
    
    for user in users_with_orders:
        orders = Order.query.filter_by(
            user_id=user.id,
            payment_status='paid'
        ).order_by(Order.created_at.desc()).all()
        
        total_spent = sum(float(order.total_amount or 0) for order in orders)
        
        print(f"User ID: {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Full Name: {user.full_name}")
        print(f"  Marketing Opt-in: {user.marketing_opt_in}")
        print(f"  Paid Orders: {len(orders)}")
        print(f"  Total Spent: ${total_spent:.2f}")
        if orders:
            print(f"  Last Order: {orders[0].created_at}")
        print()

