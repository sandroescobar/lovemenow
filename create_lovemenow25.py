"""
Create or update the LOVEMENOW25 discount code (25% off)
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from app import create_app
from routes import db
from models import DiscountCode

app = create_app()

with app.app_context():
    # Check if code exists
    code = db.session.query(DiscountCode).filter_by(code='LOVEMENOW25').first()
    
    if code:
        print(f"✅ LOVEMENOW25 already exists: {code.discount_percent}% off")
        # Update to ensure it's 25%
        if code.discount_percent != 25:
            code.discount_percent = 25
            code.is_active = True
            db.session.commit()
            print(f"   Updated to 25%")
    else:
        # Create new discount code
        new_code = DiscountCode(
            code='LOVEMENOW25',
            discount_percent=25,
            is_active=True,
            usage_limit=None,  # No limit
            description='25% off promo popup discount'
        )
        db.session.add(new_code)
        db.session.commit()
        print(f"✅ Created LOVEMENOW25 discount code: 25% off")
    
    # Show all active codes
    print("\nActive discount codes:")
    active = db.session.query(DiscountCode).filter_by(is_active=True).all()
    for disc in active:
        limit_text = f" (limit: {disc.usage_limit} uses)" if disc.usage_limit else " (no limit)"
        print(f"   - {disc.code}: {disc.discount_percent}% off{limit_text}")

