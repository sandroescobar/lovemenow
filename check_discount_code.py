"""
Check if LOVEMENOW25 discount code exists
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from app import create_app
from routes import db
from models import Discount

app = create_app()

with app.app_context():
    code = db.session.query(Discount).filter_by(code='LOVEMENOW25').first()
    
    if code:
        print(f"✅ Discount code exists: {code.code}")
        print(f"   Discount: {code.discount_percent}% off")
        print(f"   Active: {code.is_active}")
        print(f"   Usage: {code.usage_count} times")
    else:
        print("❌ LOVEMENOW25 discount code does NOT exist")
        print("\nExisting discount codes:")
        all_codes = db.session.query(Discount).all()
        for disc in all_codes:
            print(f"   - {disc.code}: {disc.discount_percent}% off (active: {disc.is_active})")

