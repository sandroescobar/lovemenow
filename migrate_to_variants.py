#!/usr/bin/env python3
"""
Migration script to convert existing products to the new ProductVariant system.

This script will:
1. Create ProductVariant records for each existing Product
2. Move inventory data from Product to ProductVariant
3. Update ProductImage references to point to variants
4. Update Cart, Wishlist, and OrderItem references
5. Handle products that should be grouped (like Du Douche Stone/Midnight)

Run this script AFTER updating your models.py but BEFORE running the application.
"""

import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routes import db
from models import Product, ProductVariant, ProductImage, Cart, Wishlist, OrderItem, Color

def create_default_colors():
    """Create some default colors if they don't exist"""
    default_colors = [
        {'name': 'Black', 'hex': '#000000', 'slug': 'black'},
        {'name': 'White', 'hex': '#FFFFFF', 'slug': 'white'},
        {'name': 'Stone', 'hex': '#8B7D6B', 'slug': 'stone'},
        {'name': 'Midnight', 'hex': '#2C3E50', 'slug': 'midnight'},
        {'name': 'Default', 'hex': '#808080', 'slug': 'default'},
    ]
    
    created_colors = {}
    for color_data in default_colors:
        existing_color = Color.query.filter_by(slug=color_data['slug']).first()
        if not existing_color:
            color = Color(**color_data)
            db.session.add(color)
            db.session.flush()  # Get the ID
            created_colors[color_data['slug']] = color
            print(f"Created color: {color.name}")
        else:
            created_colors[color_data['slug']] = existing_color
            print(f"Using existing color: {existing_color.name}")
    
    return created_colors

def identify_product_groups():
    """
    Identify products that should be grouped as variants.
    Returns a dict where key is the base product name and value is list of product IDs.
    """
    products = Product.query.all()
    groups = {}
    
    # Define patterns for grouping products
    # You can extend this logic based on your naming conventions
    for product in products:
        base_name = product.name
        
        # Handle "Du Douche" products
        if "Du Douche" in product.name:
            base_name = "Du Douche"
        # Add more grouping logic here as needed
        # elif "Another Product" in product.name:
        #     base_name = "Another Product"
        
        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(product)
    
    # Only return groups with multiple products
    return {k: v for k, v in groups.items() if len(v) > 1}

def migrate_products_to_variants():
    """Main migration function"""
    print("Starting migration to ProductVariant system...")
    
    # Create default colors
    colors = create_default_colors()
    db.session.commit()
    
    # Identify product groups
    product_groups = identify_product_groups()
    print(f"Found {len(product_groups)} product groups to merge:")
    for group_name, products in product_groups.items():
        print(f"  {group_name}: {[p.name for p in products]}")
    
    processed_products = set()
    
    # Process grouped products first
    for base_name, products in product_groups.items():
        print(f"\nProcessing group: {base_name}")
        
        # Use the first product as the base product
        base_product = products[0]
        print(f"Using {base_product.name} (ID: {base_product.id}) as base product")
        
        # Update base product name to remove variant-specific parts
        base_product.name = base_name
        
        # Create variants for each product in the group
        for i, product in enumerate(products):
            # Determine color and variant name
            color = None
            variant_name = None
            
            if "Stone" in product.name:
                color = colors['stone']
                variant_name = "Stone"
            elif "Midnight" in product.name:
                color = colors['midnight']
                variant_name = "Midnight"
            else:
                color = colors['default']
                variant_name = "Default"
            
            # Create variant
            variant = ProductVariant(
                product_id=base_product.id,
                color_id=color.id if color else None,
                variant_name=variant_name,
                in_stock=product.in_stock,
                quantity_on_hand=product.quantity_on_hand,
                upc=product.upc
            )
            
            db.session.add(variant)
            db.session.flush()  # Get the variant ID
            
            print(f"  Created variant: {variant.display_name} (ID: {variant.id})")
            
            # Move images from product to variant
            images = ProductImage.query.filter_by(product_id=product.id).all()
            for image in images:
                image.product_variant_id = variant.id
                print(f"    Moved image: {image.url}")
            
            # If this is not the base product, we need to update references
            if product.id != base_product.id:
                # Update cart items
                cart_items = Cart.query.filter_by(product_id=product.id).all()
                for cart_item in cart_items:
                    cart_item.product_variant_id = variant.id
                    print(f"    Updated cart item for user {cart_item.user_id}")
                
                # Update wishlist items
                wishlist_items = Wishlist.query.filter_by(product_id=product.id).all()
                for wishlist_item in wishlist_items:
                    wishlist_item.product_variant_id = variant.id
                    print(f"    Updated wishlist item for user {wishlist_item.user_id}")
                
                # Update order items
                order_items = OrderItem.query.filter_by(product_id=product.id).all()
                for order_item in order_items:
                    order_item.product_variant_id = variant.id
                    order_item.variant_name = variant_name
                    print(f"    Updated order item in order {order_item.order_id}")
                
                # Mark this product for deletion (we'll delete it later)
                processed_products.add(product.id)
            else:
                # For the base product, update references to point to its variant
                cart_items = Cart.query.filter_by(product_id=product.id).all()
                for cart_item in cart_items:
                    cart_item.product_variant_id = variant.id
                
                wishlist_items = Wishlist.query.filter_by(product_id=product.id).all()
                for wishlist_item in wishlist_items:
                    wishlist_item.product_variant_id = variant.id
                
                order_items = OrderItem.query.filter_by(product_id=product.id).all()
                for order_item in order_items:
                    order_item.product_variant_id = variant.id
                    order_item.variant_name = variant_name
        
        processed_products.update(p.id for p in products)
    
    # Process remaining single products
    single_products = Product.query.filter(~Product.id.in_(processed_products)).all()
    print(f"\nProcessing {len(single_products)} single products...")
    
    for product in single_products:
        print(f"Processing single product: {product.name} (ID: {product.id})")
        
        # Create a single variant for this product
        variant = ProductVariant(
            product_id=product.id,
            color_id=colors['default'].id,
            variant_name="Default",
            in_stock=product.in_stock,
            quantity_on_hand=product.quantity_on_hand,
            upc=product.upc
        )
        
        db.session.add(variant)
        db.session.flush()
        
        print(f"  Created variant: {variant.display_name} (ID: {variant.id})")
        
        # Move images
        images = ProductImage.query.filter_by(product_id=product.id).all()
        for image in images:
            image.product_variant_id = variant.id
        
        # Update references
        cart_items = Cart.query.filter_by(product_id=product.id).all()
        for cart_item in cart_items:
            cart_item.product_variant_id = variant.id
        
        wishlist_items = Wishlist.query.filter_by(product_id=product.id).all()
        for wishlist_item in wishlist_items:
            wishlist_item.product_variant_id = variant.id
        
        order_items = OrderItem.query.filter_by(product_id=product.id).all()
        for order_item in order_items:
            order_item.product_variant_id = variant.id
            order_item.variant_name = "Default"
    
    # Delete duplicate products (keeping only base products)
    products_to_delete = Product.query.filter(Product.id.in_(processed_products)).all()
    base_product_ids = set()
    
    for base_name, products in product_groups.items():
        base_product_ids.add(products[0].id)  # Keep the first product as base
    
    for product in products_to_delete:
        if product.id not in base_product_ids:
            print(f"Deleting duplicate product: {product.name} (ID: {product.id})")
            db.session.delete(product)
    
    # Commit all changes
    try:
        db.session.commit()
        print("\n✅ Migration completed successfully!")
        print("\nSummary:")
        print(f"- Created variants for {len(single_products) + sum(len(products) for products in product_groups.values())} products")
        print(f"- Merged {len(product_groups)} product groups")
        print(f"- Updated all cart, wishlist, and order references")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise

def verify_migration():
    """Verify that the migration was successful"""
    print("\nVerifying migration...")
    
    # Check that all products have variants
    products_without_variants = Product.query.filter(~Product.variants.any()).all()
    if products_without_variants:
        print(f"⚠️  Warning: {len(products_without_variants)} products have no variants:")
        for product in products_without_variants:
            print(f"  - {product.name} (ID: {product.id})")
    else:
        print("✅ All products have variants")
    
    # Check that all images are linked to variants
    orphaned_images = ProductImage.query.filter_by(product_variant_id=None).all()
    if orphaned_images:
        print(f"⚠️  Warning: {len(orphaned_images)} images are not linked to variants")
    else:
        print("✅ All images are linked to variants")
    
    # Check cart items
    orphaned_cart_items = Cart.query.filter_by(product_variant_id=None).all()
    if orphaned_cart_items:
        print(f"⚠️  Warning: {len(orphaned_cart_items)} cart items are not linked to variants")
    else:
        print("✅ All cart items are linked to variants")
    
    print("\nMigration verification complete!")

if __name__ == "__main__":
    print("ProductVariant Migration Script")
    print("=" * 50)
    
    response = input("This will modify your database. Are you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        sys.exit(0)
    
    try:
        migrate_products_to_variants()
        verify_migration()
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)