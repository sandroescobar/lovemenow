#!/usr/bin/env python3
"""
Fix discount code: Rename LOVEMENOW20 to LMN18 and update to 18% discount
"""
import sys
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from app_factory import create_app
from models import db, DiscountCode

app = create_app()

with app.app_context():
    # Find and update LOVEMENOW20 to LMN18 with 18%
    code = DiscountCode.query.filter_by(code='LOVEMENOW20').first()
    
    if code:
        print(f"Found: {code.code} = {code.discount_value}%")
        code.code = 'LMN18'
        code.discount_value = 18.0
        db.session.commit()
        print(f"✅ Updated to: {code.code} = {code.discount_value}%")
    else:
        print("❌ LOVEMENOW20 not found in database")
        
    # Verify LOVEMENOWMIAMI also exists and is 18%
    lovemenowmiami = DiscountCode.query.filter_by(code='LOVEMENOWMIAMI').first()
    if lovemenowmiami:
        print(f"✅ LOVEMENOWMIAMI exists: {lovemenowmiami.discount_value}%")
    else:
        print("⚠️ LOVEMENOWMIAMI not found")
    
    # List all active discount codes
    print("\n📊 All Active Discount Codes:")
    all_codes = DiscountCode.query.filter_by(is_active=True).all()
    for c in all_codes:
        print(f"  {c.code}: {c.discount_value}% (uses: {c.current_uses}/{c.max_uses if c.max_uses else '∞'})")