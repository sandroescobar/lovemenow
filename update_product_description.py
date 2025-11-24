"""
Update product description: change 7 in to 8 in for UPC 657447098000
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
    # Find product by UPC
    product = db.session.query(Product).filter_by(upc='657447098000').first()
    
    if not product:
        print("❌ Product with UPC 657447098000 not found")
        sys.exit(1)
    
    print(f"Found product: {product.name} (ID: {product.id})")
    print(f"\nBefore:")
    print(f"  Description snippet: {product.description[:200] if product.description else 'No description'}")
    
    # Update: 7 in (model shown) → 8 in (model shown)
    if product.description and "Total length: 7 in" in product.description:
        product.description = product.description.replace("Total length: 7 in", "Total length: 8 in")
        db.session.commit()
        print(f"\n✅ Updated!")
        print(f"After:")
        print(f"  Description snippet: {product.description[:200] if product.description else 'No description'}")
    else:
        print("\n⚠️ Could not find 'Total length: 7 in' in description")
        if product.description:
            print(f"\nFull description:\n{product.description}")

