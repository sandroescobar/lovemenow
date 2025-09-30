#!/usr/bin/env python3
"""
Migration script to create discount system tables
Run this script to add the new discount functionality to your database
"""

import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from routes import db
from models import DiscountCode, DiscountUsage, CartDiscount

def migrate_discount_system():
    """Create discount system tables and initialize default codes"""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 Creating discount system tables...")
            
            # Create all tables
            db.create_all()
            
            print("✅ Tables created successfully!")
            
            # Initialize default discount codes
            print("🔄 Initializing default discount codes...")
            
            default_codes = [
                {
                    'code': 'SAVE20',
                    'description': '20% off your order',
                    'discount_type': 'percentage',
                    'discount_value': 20,
                    'max_uses': 100,
                    'is_active': True
                },
                {
                    'code': 'WELCOME10',
                    'description': '10% off for new customers',
                    'discount_type': 'percentage',
                    'discount_value': 10,
                    'max_uses': 100,
                    'is_active': True
                },
                {
                    'code': 'FIRST15',
                    'description': '15% off first order',
                    'discount_type': 'percentage',
                    'discount_value': 15,
                    'max_uses': 100,
                    'is_active': True
                },
                {
                    'code': 'LOVEME20',
                    'description': '20% off special',
                    'discount_type': 'percentage',
                    'discount_value': 20,
                    'max_uses': 100,
                    'is_active': True
                },
                {
                    'code': 'MIAMI25',
                    'description': '25% off Miami special',
                    'discount_type': 'percentage',
                    'discount_value': 25,
                    'max_uses': 100,
                    'is_active': True
                }
            ]
            
            codes_added = 0
            for code_data in default_codes:
                existing_code = DiscountCode.query.filter_by(code=code_data['code']).first()
                if not existing_code:
                    discount_code = DiscountCode(**code_data)
                    db.session.add(discount_code)
                    codes_added += 1
                    print(f"  ➕ Added discount code: {code_data['code']}")
                else:
                    print(f"  ⏭️  Discount code already exists: {code_data['code']}")
            
            if codes_added > 0:
                db.session.commit()
                print(f"✅ Added {codes_added} new discount codes!")
            else:
                print("✅ All discount codes already exist!")
            
            print("\n🎉 Discount system migration completed successfully!")
            print("\nNew features available:")
            print("  • Cart-wide discount application")
            print("  • Session-based discount tracking")
            print("  • One-time use per customer enforcement")
            print("  • Persistent discount across pages")
            print("  • Automatic discount finalization on checkout")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("🚀 Starting discount system migration...")
    success = migrate_discount_system()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("You can now use the new discount system features.")
    else:
        print("\n❌ Migration failed!")
        print("Please check the error messages above and try again.")
        sys.exit(1)