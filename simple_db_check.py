"""Simple database check with proper context"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app_factory import create_app
app = create_app()

from routes import db
from models import Order, User

with app.app_context():
    print("=" * 80)
    print("CHECKING DATABASE FOR ORDERS")
    print("=" * 80)

    # Check total orders
    try:
        from sqlalchemy import text
        total = db.session.execute(
            text("SELECT COUNT(*) FROM orders")
        ).scalar()
        print(f"\n✅ Total orders in database: {total}")
    except Exception as e:
        print(f"\n❌ Error counting orders: {e}")

    # Check orders by status
    try:
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT payment_status, COUNT(*) as count FROM orders GROUP BY payment_status")
        )
        print(f"\n💳 Orders by payment_status:")
        for row in result:
            print(f"   • {row[0]}: {row[1]}")
    except Exception as e:
        print(f"\n❌ Error checking statuses: {e}")

    # Check for paid orders linked to users
    try:
        from sqlalchemy import text
        result = db.session.execute(
            text("""
                SELECT u.email, COUNT(o.id) as order_count, SUM(o.total_amount) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id AND o.payment_status = 'paid'
                WHERE o.id IS NOT NULL
                GROUP BY u.id, u.email
            """)
        )
        rows = list(result)
        print(f"\n👤 Users with paid orders: {len(rows)}")
        for row in rows[:10]:
            print(f"   • {row[0]}: {row[1]} orders, ${row[2]} total")
    except Exception as e:
        print(f"\n❌ Error checking repeat customers: {e}")

    print("\n" + "=" * 80)
