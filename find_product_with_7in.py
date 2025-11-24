"""
Find products with "Total length: 7 in" in description
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from app import create_app
from routes import db
from models import Product

app = create_app()

with app.app_context():
    # First check the specific UPC
    product = db.session.query(Product).filter_by(upc='657447098000').first()
    
    if product:
        print(f"Product with UPC 657447098000:")
        print(f"  Name: {product.name}")
        print(f"  ID: {product.id}")
        print(f"  Full description:\n{product.description}\n")
    
    # Search for "7 in" or "7\"" in descriptions
    print("=" * 60)
    print("Searching for products with '7 in' or '7\"' in description:")
    products = db.session.query(Product).all()
    found_any = False
    for p in products:
        if p.description and ("7 in" in p.description or '7"' in p.description):
            print(f"\nID: {p.id}, UPC: {p.upc}, Name: {p.name}")
            # Show just the relevant line
            for line in p.description.split('\n'):
                if '7' in line:
                    print(f"  {line.strip()}")
            found_any = True
    
    if not found_any:
        print("  (none found)")

