#!/usr/bin/env python3
"""
Check what products and variants exist in the database
"""
import os
import sys
from app import create_app
from models import db, Product, ProductVariant, ProductImage

def check_products():
    """Check all products and their variants"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Checking all products and variants...")
        
        # Get all products
        products = Product.query.all()
        print(f"\n📦 Found {len(products)} products total")
        
        # Look for products that might match our UPCs
        target_upcs = ['657447102905', '657447102899']
        
        for product in products:
            # Check if product UPC matches
            if product.upc in target_upcs:
                print(f"\n✅ FOUND PRODUCT with UPC {product.upc}:")
                print(f"   ID: {product.id}")
                print(f"   Name: {product.name}")
                print(f"   Variants: {len(product.variants)}")
                
                for variant in product.variants:
                    print(f"   - Variant ID: {variant.id}, UPC: {variant.upc}")
                    images = ProductImage.query.filter_by(product_variant_id=variant.id).all()
                    print(f"     Images: {len(images)}")
                    for img in images:
                        print(f"       - {img.url}")
            
            # Check if any variant UPC matches
            for variant in product.variants:
                if variant.upc in target_upcs:
                    print(f"\n✅ FOUND VARIANT with UPC {variant.upc}:")
                    print(f"   Product ID: {product.id}")
                    print(f"   Product Name: {product.name}")
                    print(f"   Variant ID: {variant.id}")
                    images = ProductImage.query.filter_by(product_variant_id=variant.id).all()
                    print(f"   Images: {len(images)}")
                    for img in images:
                        print(f"     - {img.url}")
        
        # Also show products that contain these numbers in their name
        print(f"\n🔍 Searching for products containing '102905' or '102899' in name...")
        for product in products:
            if '102905' in product.name or '102899' in product.name:
                print(f"\n📦 Product: {product.name}")
                print(f"   ID: {product.id}")
                print(f"   UPC: {product.upc}")
                print(f"   Variants: {len(product.variants)}")
                for variant in product.variants:
                    print(f"   - Variant ID: {variant.id}, UPC: {variant.upc}")

if __name__ == '__main__':
    check_products()