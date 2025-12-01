#!/usr/bin/env python3
"""
Setup script to update the discount system:
1. Change LOVEMENOWMIAMI from 23% to 18%
2. Create LOVEMENOW10 - a new $10 fixed discount (one-time per user)
"""
import sys
from app_factory import create_app
from routes import db
from models import DiscountCode
from datetime import datetime

# Create app context
app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("UPDATING DISCOUNT SYSTEM")
    print("="*60)
    
    # ─── Step 1: Update LOVEMENOWMIAMI to 18% ───
    print("\n📝 Step 1: Updating LOVEMENOWMIAMI from 23% to 18%...")
    lovemenowmiami = db.session.query(DiscountCode).filter_by(code='LOVEMENOWMIAMI').first()
    
    if lovemenowmiami:
        old_value = lovemenowmiami.discount_value
        lovemenowmiami.discount_value = 18.0
        db.session.commit()
        print(f"   ✅ Updated: {old_value}% → 18%")
    else:
        print("   ⚠️  LOVEMENOWMIAMI not found, creating it...")
        lovemenowmiami = DiscountCode(
            code='LOVEMENOWMIAMI',
            discount_type='percentage',
            discount_value=18.0,
            is_active=True,
            current_uses=0
        )
        db.session.add(lovemenowmiami)
        db.session.commit()
        print(f"   ✅ Created: LOVEMENOWMIAMI as 18% discount")
    
    # ─── Step 2: Create LOVEMENOW10 ───
    print("\n📝 Step 2: Creating LOVEMENOW10 ($10 fixed discount)...")
    lovemenow10 = db.session.query(DiscountCode).filter_by(code='LOVEMENOW10').first()
    
    if lovemenow10:
        print(f"   ℹ️  LOVEMENOW10 already exists (${lovemenow10.discount_value})")
        print(f"   • Type: {lovemenow10.discount_type}")
        print(f"   • Active: {lovemenow10.is_active}")
        print(f"   • Max Uses: {lovemenow10.max_uses}")
        print(f"   • Current Uses: {lovemenow10.current_uses}")
    else:
        lovemenow10 = DiscountCode(
            code='LOVEMENOW10',
            discount_type='fixed',
            discount_value=10.0,
            max_uses=None,  # Unlimited global uses, but one per user via DiscountUsage table
            is_active=True,
            current_uses=0
        )
        db.session.add(lovemenow10)
        db.session.commit()
        print(f"   ✅ Created: LOVEMENOW10")
        print(f"   • Type: Fixed amount ($10)")
        print(f"   • Active: Yes")
        print(f"   • Max Uses: Unlimited (one-time per user via tracking)")
        print(f"   • Current Uses: 0")
    
    # ─── Summary ───
    print("\n" + "="*60)
    print("✅ DISCOUNT SYSTEM UPDATED")
    print("="*60)
    print("\n📋 Summary:")
    print(f"   1. LOVEMENOWMIAMI: 18% off (percentage)")
    print(f"   2. LOVEMENOW10: $10 off (fixed, public but undocumented)")
    print(f"\n⛔ Anti-stacking: Users cannot combine both codes")
    print(f"   • One code per cart/checkout")
    print(f"   • System will reject attempts to apply one if other is active")
    print(f"\n🔐 One-time tracking: Each user can use each code once")
    print(f"   • Tracked via DiscountUsage table")
    print(f"   • session + user_id prevents duplicate redemptions")
    print("\n" + "="*60 + "\n")