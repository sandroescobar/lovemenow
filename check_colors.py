#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from models import db, Product, Color, ProductVariant
from main import app

def check_colors():
    with app.app_context():
        print("=== COLOR CHECK ===")
        
        # Check total colors in database
        total_colors = Color.query.count()
        print(f"Total colors in database: {total_colors}")
        
        if total_colors > 0:
            print("\nAll colors:")
            colors = Color.query.all()
            for color in colors:
                print(f"  - {color.name} (#{color.hex}) [slug: {color.slug}]")
        
        # Check products with colors
        products_with_colors = Product.query.filter(Product.colors.any()).count()
        print(f"\nProducts with colors linked: {products_with_colors}")
        
        # Check specific products
        print("\nChecking first 5 products:")
        products = Product.query.limit(5).all()
        for product in products:
            colors = list(product.available_colors)
            print(f"  - {product.name}: {len(colors)} colors")
            for color in colors:
                print(f"    * {color.name} ({color.slug})")
        
        # Check variants with colors
        variants_with_colors = ProductVariant.query.filter(ProductVariant.color_id.isnot(None)).count()
        total_variants = ProductVariant.query.count()
        print(f"\nVariants with colors: {variants_with_colors}/{total_variants}")
        
        # Check Du-Douche specifically
        du_douche = Product.query.filter(Product.name.like('%Du-Douche%')).first()
        if du_douche:
            print(f"\nDu-Douche colors: {[c.name for c in du_douche.available_colors]}")
            print(f"Du-Douche variants: {len(du_douche.variants)}")
            for variant in du_douche.variants:
                color_name = variant.color.name if variant.color else "No color"
                print(f"  - Variant {variant.id}: {color_name} (color_id: {variant.color_id})")
        
        # Check products page - should show colors from product.colors
        print(f"\nProducts page color display test:")
        sample_products = Product.query.filter(Product.colors.any()).limit(3).all()
        for product in sample_products:
            color_slugs = [c.slug for c in product.available_colors]
            print(f"  - {product.name}: colors={color_slugs}")
            
        # Check which products have variants with color_id
        products_with_variant_colors = db.session.query(Product).join(ProductVariant).filter(ProductVariant.color_id.isnot(None)).distinct().count()
        print(f"\nProducts with variants that have color_id: {products_with_variant_colors}")

if __name__ == "__main__":
    check_colors()