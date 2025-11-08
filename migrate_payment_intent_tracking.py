#!/usr/bin/env python
"""
Migration script to add PaymentIntent tracking columns to the orders table.
This prevents duplicate charges from multiple PaymentIntents.

Adds:
- is_duplicate_payment: Boolean flag if this order duplicates another from same PI
- payment_intent_status_at_creation: PI status when order was created
- cancellation_reason: Why order was cancelled/incomplete
"""

import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from routes import db
from sqlalchemy import text

def migrate():
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting migration...")
        
        # Check if columns already exist
        with db.engine.connect() as conn:
            # Check for is_duplicate_payment column
            result = conn.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME='orders' AND COLUMN_NAME='is_duplicate_payment'
            """))
            if result.fetchone():
                print("✅ Column 'is_duplicate_payment' already exists, skipping...")
            else:
                print("➕ Adding 'is_duplicate_payment' column...")
                conn.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN is_duplicate_payment BOOLEAN DEFAULT FALSE
                """))
                conn.commit()
                print("   ✅ Added is_duplicate_payment")
            
            # Check for payment_intent_status_at_creation column
            result = conn.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME='orders' AND COLUMN_NAME='payment_intent_status_at_creation'
            """))
            if result.fetchone():
                print("✅ Column 'payment_intent_status_at_creation' already exists, skipping...")
            else:
                print("➕ Adding 'payment_intent_status_at_creation' column...")
                conn.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN payment_intent_status_at_creation VARCHAR(50) NULL
                """))
                conn.commit()
                print("   ✅ Added payment_intent_status_at_creation")
            
            # Check for cancellation_reason column
            result = conn.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME='orders' AND COLUMN_NAME='cancellation_reason'
            """))
            if result.fetchone():
                print("✅ Column 'cancellation_reason' already exists, skipping...")
            else:
                print("➕ Adding 'cancellation_reason' column...")
                conn.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN cancellation_reason VARCHAR(255) NULL
                """))
                conn.commit()
                print("   ✅ Added cancellation_reason")
        
        print("\n✅ Migration completed successfully!")
        print("\nNEW COLUMNS ADDED:")
        print("  • is_duplicate_payment: Tracks if this order duplicates another from same PaymentIntent")
        print("  • payment_intent_status_at_creation: PI status when order was created (for debugging)")
        print("  • cancellation_reason: Reason if order was incomplete/cancelled")
        print("\nBENEFITS:")
        print("  ✅ Prevents duplicate charges from same PaymentIntent")
        print("  ✅ You can filter 'is_duplicate_payment=True' to see affected orders")
        print("  ✅ Admin dashboard can display which orders are duplicates")
        print("  ✅ Fully backward compatible - no existing data affected")

if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        sys.exit(1)