"""Quick diagnostic to check orders in database"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app_factory import create_app
from routes import db
from models import Order, User

app = create_app()

with app.app_context():
    print("=" * 80)
    print("DATABASE DIAGNOSTICS")
    print("=" * 80)
    
    # Total orders
    total_orders = db.session.query(Order).count()
    print(f"\n📊 Total orders in database: {total_orders}")
    
    if total_orders == 0:
        print("   ⚠️ No orders found! This might be why repeat customers list is empty.")
    
    # Orders by payment_status
    print(f"\n💳 Orders by payment_status:")
    statuses = db.session.query(Order.payment_status, db.func.count()).group_by(Order.payment_status).all()
    for status, count in statuses:
        print(f"   • {status}: {count}")
    
    # Orders with user_id (registered customers)
    registered_orders = db.session.query(Order).filter(Order.user_id != None).count()
    print(f"\n👤 Orders from registered users: {registered_orders}")
    
    # Orders as guests (no user_id)
    guest_orders = db.session.query(Order).filter(Order.user_id == None).count()
    print(f"👤 Orders from guests (user_id=None): {guest_orders}")
    
    # Users with paid orders
    print(f"\n🔍 Users with paid orders:")
    users_with_paid = db.session.query(User).join(
        Order, User.id == Order.user_id
    ).filter(
        Order.payment_status == 'paid'
    ).distinct().all()
    print(f"   • Total: {len(users_with_paid)}")
    for user in users_with_paid[:5]:  # Show first 5
        paid_count = db.session.query(Order).filter_by(user_id=user.id, payment_status='paid').count()
        print(f"     - {user.email}: {paid_count} paid orders")
    
    # Sample of recent orders
    print(f"\n📋 Recent orders (last 5):")
    recent = db.session.query(Order).order_by(Order.created_at.desc()).limit(5).all()
    for order in recent:
        user_info = f"User: {order.user.email}" if order.user else "Guest"
        print(f"   • {order.order_number} | Status: {order.payment_status} | {user_info} | ${order.total_amount}")
    
    print("\n" + "=" * 80)

