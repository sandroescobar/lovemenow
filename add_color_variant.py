#!/usr/bin/env python3
"""
Helper script to add new color variants to existing products.

Usage examples:
python add_color_variant.py --product-id 1 --color-name "Red" --color-hex "#FF0000" --quantity 5
python add_color_variant.py --product-name "Du Douche" --color-name "Blue" --color-hex "#0000FF" --quantity 3
"""

import sys
import os
import argparse

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routes import db
from models import Product, ProductVariant, Color

def create_color_if_not_exists(name, hex_code):
    """Create a color if it doesn't exist"""
    slug = name.lower().replace(' ', '-')
    
    existing_color = Color.query.filter_by(slug=slug).first()
    if existing_color:
        print(f"Using existing color: {existing_color.name}")
        return existing_color
    
    color = Color(name=name, hex=hex_code, slug=slug)
    db.session.add(color)
    db.session.flush()
    print(f"Created new color: {color.name} ({color.hex})")
    return color

def add_color_variant(product_id=None, product_name=None, color_name=None, color_hex=None, quantity=1, variant_name=None):
    """Add a new color variant to a product"""
    
    # Find the product
    if product_id:
        product = Product.query.get(product_id)
        if not product:
            print(f"Product with ID {product_id} not found")
            return False
    elif product_name:
        product = Product.query.filter(Product.name.ilike(f"%{product_name}%")).first()
        if not product:
            print(f"Product with name containing '{product_name}' not found")
            return False
    else:
        print("Either product_id or product_name must be provided")
        return False
    
    print(f"Found product: {product.name} (ID: {product.id})")
    
    # Create or find the color
    color = create_color_if_not_exists(color_name, color_hex)
    
    # Check if this color variant already exists
    existing_variant = ProductVariant.query.filter_by(
        product_id=product.id,
        color_id=color.id
    ).first()
    
    if existing_variant:
        print(f"Color variant already exists: {existing_variant.display_name}")
        response = input("Update quantity? (y/n): ")
        if response.lower() == 'y':
            existing_variant.quantity_on_hand = quantity
            existing_variant.in_stock = quantity > 0
            db.session.commit()
            print(f"Updated quantity to {quantity}")
        return True
    
    # Create the new variant
    variant = ProductVariant(
        product_id=product.id,
        color_id=color.id,
        variant_name=variant_name or color_name,
        quantity_on_hand=quantity,
        in_stock=quantity > 0
    )
    
    db.session.add(variant)
    db.session.commit()
    
    print(f"✅ Created new variant: {variant.display_name}")
    print(f"   Quantity: {variant.quantity_on_hand}")
    print(f"   In Stock: {variant.in_stock}")
    
    return True

def list_product_variants(product_id=None, product_name=None):
    """List all variants for a product"""
    
    # Find the product
    if product_id:
        product = Product.query.get(product_id)
    elif product_name:
        product = Product.query.filter(Product.name.ilike(f"%{product_name}%")).first()
    else:
        print("Either product_id or product_name must be provided")
        return
    
    if not product:
        print("Product not found")
        return
    
    print(f"\nVariants for: {product.name} (ID: {product.id})")
    print("-" * 50)
    
    if not product.variants:
        print("No variants found")
        return
    
    for variant in product.variants:
        color_info = f" ({variant.color.name})" if variant.color else ""
        stock_status = "✅ In Stock" if variant.is_available else "❌ Out of Stock"
        print(f"ID: {variant.id} | {variant.variant_name}{color_info} | Qty: {variant.quantity_on_hand} | {stock_status}")

def main():
    parser = argparse.ArgumentParser(description='Add color variants to products')
    parser.add_argument('--product-id', type=int, help='Product ID')
    parser.add_argument('--product-name', help='Product name (partial match)')
    parser.add_argument('--color-name', help='Color name')
    parser.add_argument('--color-hex', help='Color hex code (e.g., #FF0000)')
    parser.add_argument('--quantity', type=int, default=1, help='Initial quantity (default: 1)')
    parser.add_argument('--variant-name', help='Custom variant name (defaults to color name)')
    parser.add_argument('--list-variants', action='store_true', help='List existing variants for a product')
    
    args = parser.parse_args()
    
    if args.list_variants:
        list_product_variants(args.product_id, args.product_name)
    else:
        if not args.color_name or not args.color_hex:
            print("--color-name and --color-hex are required when adding variants")
            return
        
        success = add_color_variant(
            product_id=args.product_id,
            product_name=args.product_name,
            color_name=args.color_name,
            color_hex=args.color_hex,
            quantity=args.quantity,
            variant_name=args.variant_name
        )
        
        if success:
            print("\n✅ Variant added successfully!")

if __name__ == "__main__":
    main()