#!/usr/bin/env python
"""
Quick test to verify database migrations work correctly.
Run this locally: python test_migrations.py
"""

import sys
from app import create_app
from routes import db
from database_migrations import run_all_migrations

def test_migrations():
    """Test that migrations run without errors"""
    print("🧪 Testing database migrations...")
    
    try:
        app = create_app()
        
        with app.app_context():
            print("\n1. Testing migration system...")
            run_all_migrations(db, app)
            print("✅ Migrations completed successfully")
            
            # Verify the column exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            print("\n2. Verifying discount_usages table schema...")
            columns = [col['name'] for col in inspector.get_columns('discount_usages')]
            
            if 'created_at' in columns:
                print(f"✅ Column 'created_at' exists in discount_usages")
            else:
                print(f"❌ Column 'created_at' NOT found in discount_usages")
                print(f"   Available columns: {columns}")
                return False
            
            print("\n3. Testing DiscountUsage model insert...")
            from models import DiscountUsage, DiscountCode, Order, User
            
            # Create a test code if needed
            test_code = DiscountCode.query.filter_by(code='TEST_MIG').first()
            if not test_code:
                test_code = DiscountCode(
                    code='TEST_MIG',
                    discount_type='percentage',
                    discount_value=10.00,
                    max_uses=999,
                    is_active=True
                )
                db.session.add(test_code)
                db.session.commit()
            
            # Try to create a DiscountUsage (this would have failed before the fix)
            usage = DiscountUsage(
                discount_code_id=test_code.id,
                user_id=None,
                session_identifier='test_session',
                original_amount=100.00,
                discount_amount=10.00
            )
            db.session.add(usage)
            db.session.commit()
            
            print(f"✅ Successfully created DiscountUsage record (ID: {usage.id})")
            print(f"   - created_at: {usage.created_at}")
            
            print("\n✅ ALL TESTS PASSED - Migrations working correctly!")
            return True
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_migrations()
    sys.exit(0 if success else 1)