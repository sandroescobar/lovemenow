#!/usr/bin/env python3
"""
Check if test products exist in the database
"""
import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from app import create_app
from models import Product

def check_products():
    """Check if test products exist"""
    app = create_app()
    
    with app.app_context():
        print("🔍 CHECKING TEST PRODUCTS")
        print("=" * 40)
        
        # Check for products with IDs 1 and 2
        for product_id in [1, 2]:
            product = Product.query.get(product_id)
            if product:
                print(f"✅ Product {product_id}: {product.name} (${product.price})")
            else:
                print(f"❌ Product {product_id}: NOT FOUND")
        
        # Show first few products in database
        print("\n📦 FIRST 5 PRODUCTS IN DATABASE:")
        print("-" * 40)
        products = Product.query.limit(5).all()
        if products:
            for product in products:
                print(f"ID {product.id}: {product.name} (${product.price})")
        else:
            print("❌ No products found in database")
        
        print(f"\n📊 Total products in database: {Product.query.count()}")

if __name__ == "__main__":
    check_products()