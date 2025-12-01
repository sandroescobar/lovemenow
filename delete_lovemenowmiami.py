#!/usr/bin/env python3
"""
Delete LOVEMENOWMIAMI discount code and ensure only LMN18 exists
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from routes import db
from models import DiscountCode, DiscountUsage

# Create app context
app = create_app()

def delete_lovemenowmiami():
    """Delete LOVEMENOWMIAMI code from database"""
    print("\n🔍 Checking for LOVEMENOWMIAMI discount code...")
    
    # Find LOVEMENOWMIAMI
    code = DiscountCode.query.filter_by(code='LOVEMENOWMIAMI').first()
    
    if not code:
        print("✅ LOVEMENOWMIAMI already deleted")
    else:
        print(f"❌ Found LOVEMENOWMIAMI (id={code.id}, discount={code.discount_value}%)")
        
        # Delete related DiscountUsage records
        print(f"   Deleting {code.usages.count()} related usage records...")
        DiscountUsage.query.filter_by(discount_code_id=code.id).delete()
        
        # Delete the code
        db.session.delete(code)
        db.session.commit()
        print("✅ LOVEMENOWMIAMI deleted successfully")

def verify_only_lmn18():
    """Verify only LMN18 and LOVEMENOW25 exist (if any)"""
    print("\n📋 Verifying discount codes in database...")
    
    codes = DiscountCode.query.filter_by(is_active=True).all()
    print(f"\nActive discount codes:")
    for c in codes:
        print(f"  • {c.code}: {c.discount_value}% {c.discount_type} (max uses: {c.max_uses})")
    
    # Check for LMN18
    lmn18 = DiscountCode.query.filter_by(code='LMN18').first()
    if lmn18:
        print(f"\n✅ LMN18 exists with {lmn18.discount_value}% discount")
    else:
        print(f"\n⚠️  LMN18 NOT FOUND - Creating it now...")
        lmn18 = DiscountCode(
            code='LMN18',
            discount_type='percent',
            discount_value=18.0,
            is_active=True,
            max_uses=999999
        )
        db.session.add(lmn18)
        db.session.commit()
        print(f"✅ LMN18 created with 18% discount")
    
    # Check for unwanted codes
    unwanted = DiscountCode.query.filter_by(code='LOVEMENOWMIAMI').first()
    if unwanted:
        print(f"\n⚠️  WARNING: LOVEMENOWMIAMI still exists - running delete again...")
        delete_lovemenowmiami()
    
    # Check for LOVEMENOW20
    old_20 = DiscountCode.query.filter_by(code='LOVEMENOW20').first()
    if old_20:
        print(f"\n⚠️  WARNING: LOVEMENOW20 still exists - should have been deleted")
    else:
        print(f"✅ LOVEMENOW20 successfully deleted")

def main():
    print("=" * 60)
    print("DELETE LOVEMENOWMIAMI DISCOUNT CODE")
    print("=" * 60)
    
    with app.app_context():
        delete_lovemenowmiami()
        verify_only_lmn18()
    
    print("\n" + "=" * 60)
    print("✨ Discount codes cleanup complete!")
    print("=" * 60 + "\n")

if __name__ == '__main__':
    main()