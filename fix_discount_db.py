#!/usr/bin/env python3
"""
Direct database update script - fixes the discount from 23% to 18%
Uses the main.py app setup
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import main app and models
from main import app
from routes import db
from models import DiscountCode

def main():
    print("\n" + "="*60)
    print("FIXING LOVEMENOWMIAMI DISCOUNT: 23% → 18%")
    print("="*60 + "\n")
    
    with app.app_context():
        # Find the discount code
        code = DiscountCode.query.filter_by(code='LOVEMENOWMIAMI').first()
        
        if not code:
            print("❌ ERROR: LOVEMENOWMIAMI code not found in database!")
            print("   Make sure you've seeded the database with discount codes.")
            return False
        
        old_value = float(code.discount_value)
        
        if old_value == 18.0:
            print(f"✅ LOVEMENOWMIAMI is already 18% - no changes needed")
            return True
        
        print(f"📊 Found: LOVEMENOWMIAMI")
        print(f"   Current value: {old_value}%")
        print(f"   Type: {code.discount_type}")
        print(f"   Active: {code.is_active}")
        print(f"   Current uses: {code.current_uses}")
        
        # Update to 18%
        code.discount_value = 18.0
        db.session.commit()
        
        print(f"\n✅ Updated to: 18.0%")
        print(f"✅ Changes saved to database")
        
        # Verify
        code_verify = DiscountCode.query.filter_by(code='LOVEMENOWMIAMI').first()
        print(f"\n🔍 Verification: {code_verify.code} = {float(code_verify.discount_value)}%")
        
        return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)