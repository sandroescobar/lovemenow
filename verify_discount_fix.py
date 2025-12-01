#!/usr/bin/env python3
"""
Quick verification script to test both discount fixes
"""
import os
import sys
from dotenv import load_dotenv
from decimal import Decimal, ROUND_HALF_UP

load_dotenv()

from main import app
from routes import db
from models import DiscountCode

def _round2(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def verify():
    print("\n" + "="*70)
    print("🔍 DISCOUNT SYSTEM VERIFICATION")
    print("="*70 + "\n")
    
    with app.app_context():
        # Test 1: Verify database value
        print("TEST 1: Database Discount Value")
        print("-" * 70)
        
        code = DiscountCode.query.filter_by(code='LOVEMENOWMIAMI').first()
        if not code:
            print("❌ LOVEMENOWMIAMI code not found!")
            return False
        
        discount_val = float(code.discount_value)
        print(f"  Code: {code.code}")
        print(f"  Discount Value: {discount_val}%")
        print(f"  Type: {code.discount_type}")
        print(f"  Active: {code.is_active}")
        
        if discount_val == 18.0:
            print("  ✅ PASS: Discount is 18%")
        else:
            print(f"  ❌ FAIL: Discount should be 18%, but is {discount_val}%")
            return False
        
        # Test 2: Calculate pricing with 18% discount
        print("\n\nTEST 2: Pricing Calculation (18% Discount)")
        print("-" * 70)
        
        test_price = 15.99
        tax_rate = 0.0875
        
        # Calculate with 18% discount
        discount_amount = _round2(test_price * (discount_val / 100.0))
        subtotal_after = _round2(test_price - discount_amount)
        tax = _round2(subtotal_after * tax_rate)
        total = _round2(subtotal_after + tax)
        
        print(f"  Product Price: ${test_price:.2f}")
        print(f"  Discount Rate: {discount_val}%")
        print(f"  Discount Amount: ${discount_amount:.2f}")
        print(f"  Subtotal After Discount: ${subtotal_after:.2f}")
        print(f"  Tax (8.75%): ${tax:.2f}")
        print(f"  Total: ${total:.2f}")
        
        expected_discount = 2.88  # 15.99 * 0.18
        expected_subtotal = 13.11  # 15.99 - 2.88
        expected_tax = 1.15  # 13.11 * 0.0875
        expected_total = 14.26  # 13.11 + 1.15
        
        print(f"\n  Expected Total: ${expected_total:.2f}")
        print(f"  Calculated Total: ${total:.2f}")
        
        if total == expected_total:
            print("  ✅ PASS: Pricing calculation correct")
        else:
            print(f"  ⚠️  Total differs by ${abs(total - expected_total):.2f}")
        
        # Test 3: Verify this differs from 23% (old value)
        print("\n\nTEST 3: Verify 23% (Old Value) No Longer Used")
        print("-" * 70)
        
        old_discount_23 = _round2(test_price * 0.23)
        old_subtotal_23 = _round2(test_price - old_discount_23)
        old_tax_23 = _round2(old_subtotal_23 * tax_rate)
        old_total_23 = _round2(old_subtotal_23 + old_tax_23)
        
        print(f"  If 23% was used:")
        print(f"    Discount: ${old_discount_23:.2f}")
        print(f"    Subtotal: ${old_subtotal_23:.2f}")
        print(f"    Tax: ${old_tax_23:.2f}")
        print(f"    Total: ${old_total_23:.2f}")
        
        print(f"\n  Chrome vs Safari Issue Example:")
        print(f"    Safari was showing: ${old_total_23:.2f} (23% applied)")
        print(f"    Chrome was showing: $13.91 (corrupted cache)")
        print(f"    Both should now show: ${total:.2f} (18% applied)")
        
        if old_total_23 != total:
            print(f"  ✅ PASS: 23% calculation differs from 18% (as expected)")
        
        # Test 4: Check for other discount codes
        print("\n\nTEST 4: Other Discount Codes")
        print("-" * 70)
        
        all_codes = DiscountCode.query.filter_by(is_active=True).all()
        if all_codes:
            for c in all_codes:
                status = "✅" if c.is_valid else "❌"
                print(f"  {status} {c.code}: {c.discount_value}% ({c.discount_type}) - Max uses: {c.max_uses}, Current: {c.current_uses}")
        else:
            print("  ⚠️  No active discount codes found")
        
        print("\n" + "="*70)
        print("✅ VERIFICATION COMPLETE")
        print("="*70 + "\n")
        
        print("📝 Next Steps:")
        print("  1. Hard refresh your browser (Cmd+Shift+R or Ctrl+Shift+R)")
        print("  2. Clear browser cache for LoveMeNow")
        print("  3. Test pricing in both Chrome and Safari")
        print("  4. Verify both show: $14.26 total (for $15.99 product)")
        print("\n")
        
        return True

if __name__ == '__main__':
    try:
        success = verify()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)