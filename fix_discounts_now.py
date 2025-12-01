#!/usr/bin/env python3
"""
FIX DISCOUNTS: Delete LOVEMENOW20, ensure LMN18 exists with 18% and LOVEMENOWMIAMI with 18%
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from routes import db
from models import DiscountCode
from datetime import datetime

app = create_app()

with app.app_context():
    print("\n" + "="*70)
    print("🔧 FIXING DISCOUNT CODES")
    print("="*70)
    
    # ========== STEP 1: DELETE LOVEMENOW20 ==========
    print("\n1️⃣ DELETING LOVEMENOW20...")
    old_code = DiscountCode.query.filter_by(code='LOVEMENOW20').first()
    if old_code:
        # First delete any DiscountUsage records that reference this code
        from models import DiscountUsage
        usages = DiscountUsage.query.filter_by(discount_code_id=old_code.id).all()
        for usage in usages:
            db.session.delete(usage)
        db.session.flush()
        
        # Now delete the discount code
        db.session.delete(old_code)
        db.session.commit()
        print(f"   ✅ DELETED: LOVEMENOW20 (was {old_code.discount_value}%, {len(usages)} usages removed)")
    else:
        print("   ℹ️ LOVEMENOW20 not found (already deleted?)")
    
    # ========== STEP 2: CREATE/UPDATE LMN18 with 18% ==========
    print("\n2️⃣ SETTING UP LMN18 (18% discount)...")
    lmn18 = DiscountCode.query.filter_by(code='LMN18').first()
    if lmn18:
        old_val = lmn18.discount_value
        lmn18.discount_value = 18.0
        lmn18.is_active = True
        lmn18.discount_type = 'percentage'
        db.session.commit()
        print(f"   ✅ UPDATED: LMN18 from {old_val}% → 18%")
    else:
        lmn18 = DiscountCode(
            code='LMN18',
            discount_type='percentage',
            discount_value=18.0,
            max_uses=999999,  # Unlimited
            current_uses=0,
            is_active=True
        )
        db.session.add(lmn18)
        db.session.commit()
        print(f"   ✅ CREATED: LMN18 with 18% discount")
    
    # ========== STEP 3: CREATE/UPDATE LOVEMENOWMIAMI with 18% ==========
    print("\n3️⃣ SETTING UP LOVEMENOWMIAMI (18% discount)...")
    miami = DiscountCode.query.filter_by(code='LOVEMENOWMIAMI').first()
    if miami:
        old_val = miami.discount_value
        miami.discount_value = 18.0
        miami.is_active = True
        miami.discount_type = 'percentage'
        db.session.commit()
        print(f"   ✅ UPDATED: LOVEMENOWMIAMI from {old_val}% → 18%")
    else:
        miami = DiscountCode(
            code='LOVEMENOWMIAMI',
            discount_type='percentage',
            discount_value=18.0,
            max_uses=999999,  # Unlimited
            current_uses=0,
            is_active=True
        )
        db.session.add(miami)
        db.session.commit()
        print(f"   ✅ CREATED: LOVEMENOWMIAMI with 18% discount")
    
    # ========== VERIFICATION ==========
    print("\n" + "="*70)
    print("✅ ALL ACTIVE DISCOUNT CODES:")
    print("="*70)
    all_codes = DiscountCode.query.filter_by(is_active=True).order_by(DiscountCode.code).all()
    for code in all_codes:
        remaining = f"∞" if code.max_uses is None else f"{code.max_uses - code.current_uses}/{code.max_uses}"
        print(f"   {code.code:20} | {code.discount_value}% off | Uses: {remaining}")
    
    print("\n" + "="*70)
    print("🧮 PRICING VERIFICATION FOR $15.99 PRODUCT:")
    print("="*70)
    price = 15.99
    for code in [lmn18, miami]:
        discount_pct = float(code.discount_value)  # Convert Decimal to float
        discount = price * (discount_pct / 100.0)
        after_discount = price - discount
        tax = after_discount * 0.0875
        total = after_discount + tax
        print(f"\n   Code: {code.code}")
        print(f"   Original price:      ${price:.2f}")
        print(f"   Discount ({discount_pct:.0f}%):     -${discount:.2f}")
        print(f"   After discount:      ${after_discount:.2f}")
        print(f"   Tax (8.75%):         ${tax:.2f}")
        print(f"   💰 TOTAL:             ${total:.2f}")
    
    print("\n" + "="*70)
    print("✨ DISCOUNT CODES FIXED SUCCESSFULLY!")
    print("="*70 + "\n")