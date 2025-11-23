"""
Create LOVEMENOWMIAMI discount code based on LOVEMENOW20 settings
"""
import os
import sys
from dotenv import load_dotenv
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from app import create_app
from routes import db
from models import DiscountCode

app = create_app()

with app.app_context():
    # Check existing LOVEMENOW20
    old_code = db.session.query(DiscountCode).filter_by(code='LOVEMENOW20').first()
    
    if old_code:
        print(f"📋 Found LOVEMENOW20:")
        print(f"   Type: {old_code.discount_type}")
        print(f"   Value: {old_code.discount_value}")
        print(f"   Active: {old_code.is_active}")
        
        # Check if LOVEMENOWMIAMI exists
        new_code = db.session.query(DiscountCode).filter_by(code='LOVEMENOWMIAMI').first()
        
        if new_code:
            print(f"\n✅ LOVEMENOWMIAMI already exists")
            print(f"   Type: {new_code.discount_type}")
            print(f"   Value: {new_code.discount_value}")
        else:
            # Create LOVEMENOWMIAMI with same settings as LOVEMENOW20
            new_code = DiscountCode(
                code='LOVEMENOWMIAMI',
                discount_type=old_code.discount_type,
                discount_value=old_code.discount_value,
                max_uses=old_code.max_uses,
                is_active=True,
                starts_at=old_code.starts_at,
                ends_at=old_code.ends_at
            )
            db.session.add(new_code)
            db.session.commit()
            print(f"\n✅ Created LOVEMENOWMIAMI:")
            print(f"   Type: {old_code.discount_type}")
            print(f"   Value: {old_code.discount_value}")
    
    # Show all active codes
    print("\n🎟️ Active discount codes:")
    active = db.session.query(DiscountCode).filter_by(is_active=True).all()
    for disc in active:
        print(f"   - {disc.code}: {disc.discount_type} {disc.discount_value}")

