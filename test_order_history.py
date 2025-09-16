#!/usr/bin/env python3
"""
Test script to verify order history functionality works
"""

import os
from dotenv import load_dotenv
from flask import Flask
from flask_login import login_user
from models import db, User, Order, OrderItem, Product

# Load environment variables
load_dotenv()

def create_flask_app():
    """Create Flask app similar to main.py"""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DB_URL",
        "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize extensions
    from routes import bcrypt, login_mgr
    db.init_app(app)
    bcrypt.init_app(app)
    login_mgr.init_app(app)
    
    return app

def test_order_history():
    """Test order history functionality"""
    app = create_flask_app()
    
    with app.app_context():
        print("=== TESTING ORDER HISTORY FUNCTIONALITY ===")
        
        # Check if we have any users
        users = User.query.all()
        print(f"Total users in database: {len(users)}")
        
        if users:
            # Get first user
            user = users[0]
            print(f"Testing with user: {user.email}")
            
            # Get user's orders
            orders = Order.query.filter_by(user_id=user.id).all()
            print(f"User has {len(orders)} orders")
            
            for order in orders:
                print(f"\nOrder: {order.order_number}")
                print(f"Date: {order.created_at}")
                print(f"Total: ${order.total_amount}")
                print(f"Delivery Type: {order.delivery_type}")
                print(f"Status: {order.status}")
                
                # Get order items
                items = OrderItem.query.filter_by(order_id=order.id).all()
                print(f"Items: {len(items)}")
                
                for item in items:
                    print(f"  - {item.product_name} (Qty: {item.quantity}) - ${item.total}")
        else:
            print("No users found in database")
        
        print("\n=== ORDER HISTORY ROUTE TEST ===")
        print("Route '/my-orders' should be accessible to logged-in users")
        print("JavaScript function 'viewOrders()' should redirect to '/my-orders'")
        print("Template 'order_status.html' should display order information")

if __name__ == "__main__":
    test_order_history()