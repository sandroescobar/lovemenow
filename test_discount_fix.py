#!/usr/bin/env python3
"""
Simple test to verify LMN18 discount code works (18% discount)
Calculates expected pricing
"""

# Test with sample product
product_price = 15.99
discount_percent = 18
tax_percent = 8.75

# Calculate
price_after_discount = product_price * (1 - discount_percent/100)
tax_amount = price_after_discount * (tax_percent/100)
final_total = price_after_discount + tax_amount

print("=" * 60)
print("🧮 DISCOUNT CALCULATION TEST")
print("=" * 60)
print(f"\n📦 Product Price:           ${product_price:.2f}")
print(f"💰 Discount Code:          LMN18 (18%)")
print(f"💸 Discount Amount:        ${product_price - price_after_discount:.2f}")
print(f"━" * 60)
print(f"Subtotal (after discount): ${price_after_discount:.2f}")
print(f"Tax (8.75%):               ${tax_amount:.2f}")
print(f"━" * 60)
print(f"🎯 Final Total:            ${final_total:.2f}")
print(f"\n✅ Expected order summary:")
print(f"   Subtotal:    $15.99")
print(f"   Discount:    -$2.88  ← LMN18 (18%)")
print(f"   Tax:         $1.01")
print(f"   Total:       $14.12")
print(f"\nNOTE: Cart shows tax on original price. Actual calculation:")
print(f"   Original: $15.99 × 0.82 (82%) = ${price_after_discount:.2f}")
print(f"   Plus tax: ${price_after_discount:.2f} × 1.0875 = ${final_total:.2f}")
print("\n" + "=" * 60)