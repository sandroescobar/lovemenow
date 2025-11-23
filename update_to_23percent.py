"""
Update LOVEMENOWMIAMI to 23% discount
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
    code = db.session.query(DiscountCode).filter_by(code='LOVEMENOWMIAMI').first()
    
    if code:
        print(f"Before: {code.code} = {code.discount_value}%")
        code.discount_value = Decimal('23.00')
        db.session.commit()
        print(f"After:  {code.code} = {code.discount_value}%")
    else:
        print("❌ LOVEMENOWMIAMI not found!")

