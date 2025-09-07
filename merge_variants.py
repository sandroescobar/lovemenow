#!/usr/bin/env python3
"""
Script to merge duplicate products into proper variants
"""

from app import create_app
from models import Product, ProductVariant, ProductImage, Color, Cart, Wishlist
from routes import db
import re

def merge_du_douche_products():
    """Merge Du Douche Stone and Midnight into one product with variants"""
    
    app = create_app()
    with app.app_context():
        print("Merging Du Douche products...")
        
        # Get the two products
        stone_product = Product.query.get(63)  # Du Douche Stone
        midnight_product = Product.query.get(64)  # du douche midnight
        
        if not stone_product or not midnight_product:
            print("❌ Could not find both products")
            return
        
        print(f"Stone product: {stone_product.name}")
        print(f"Midnight product: {midnight_product.name}")
        
        # Use the stone product as the main product and standardize the name
        main_product = stone_product
        main_product.name = "Du Douche"  # Clean name without color
        main_product.base_upc = "860008092000"  # Common base UPC
        
        # Get colors
        stone_color = Color.query.filter_by(name='Greige (Warm Gray)').first()
        midnight_color = Color.query.filter_by(name='Black').first()
        
        if not stone_color or not midnight_color:
            print("❌ Could not find required colors")
            return
        
        # Update the main product's variant to have the stone color
        stone_variant = main_product.variants[0]
        stone_variant.color_id = stone_color.id
        stone_variant.variant_name = "Stone"
        
        # Create new variant for midnight
        midnight_variant = ProductVariant(
            product_id=main_product.id,
            color_id=midnight_color.id,
            variant_name="Midnight",
            in_stock=True,
            quantity_on_hand=midnight_product.variants[0].quantity_on_hand
        )
        db.session.add(midnight_variant)
        db.session.flush()  # Get the ID
        
        # Move images from midnight product to the new variant
        midnight_images = ProductImage.query.filter_by(product_variant_id=midnight_product.variants[0].id).all()
        for img in midnight_images:
            img.product_variant_id = midnight_variant.id
        
        # Update cart items that reference the midnight product
        cart_items = Cart.query.filter_by(product_id=midnight_product.id).all()
        for cart_item in cart_items:
            cart_item.product_id = main_product.id
            # Note: We should also update to reference the specific variant, but Cart model needs updating
        
        # Update wishlist items (using product_id since table hasn't been migrated yet)
        # Note: Wishlist table still uses product_id, not product_variant_id
        from sqlalchemy import text
        db.session.execute(text(
            "UPDATE wishlist SET product_id = :main_product_id WHERE product_id = :midnight_product_id"
        ), {
            'main_product_id': main_product.id,
            'midnight_product_id': midnight_product.id
        })
        
        # Update the main product's colors relationship
        main_product.colors = [stone_color, midnight_color]
        
        # Delete the midnight product and its variant
        db.session.delete(midnight_product.variants[0])
        db.session.delete(midnight_product)
        
        try:
            db.session.commit()
            print("✅ Successfully merged Du Douche products!")
            print(f"Main product now has {len(main_product.variants)} variants")
            print(f"Available colors: {[c.name for c in main_product.available_colors]}")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error merging products: {e}")
            import traceback
            traceback.print_exc()

def find_similar_products():
    """Find products that should be merged based on similar names"""
    
    app = create_app()
    with app.app_context():
        print("\nFinding products that should be merged...")
        
        products = Product.query.all()
        
        # Group products by base name (remove color words)
        color_words = ['black', 'white', 'red', 'blue', 'green', 'pink', 'purple', 'yellow', 'orange', 
                      'stone', 'midnight', 'beige', 'flesh', 'clear', 'silver', 'gold', 'brown']
        
        product_groups = {}
        
        for product in products:
            # Clean the product name
            clean_name = product.name.lower()
            
            # Remove color words and common size indicators
            for color in color_words:
                clean_name = re.sub(rf'\b{color}\b', '', clean_name)
            
            # Remove size indicators
            clean_name = re.sub(r'\b(small|medium|large|xl|xxl|s|m|l)\b', '', clean_name)
            clean_name = re.sub(r'\b\d+(\.\d+)?\s*(in|inch|inches|cm|mm|oz|ml)\b', '', clean_name)
            
            # Clean up whitespace and punctuation
            clean_name = re.sub(r'[^\w\s]', ' ', clean_name)
            clean_name = ' '.join(clean_name.split())
            clean_name = clean_name.strip()
            
            if clean_name:
                if clean_name not in product_groups:
                    product_groups[clean_name] = []
                product_groups[clean_name].append(product)
        
        # Find groups with multiple products
        merge_candidates = {name: products for name, products in product_groups.items() if len(products) > 1}
        
        print(f"Found {len(merge_candidates)} product groups that might need merging:")
        
        for base_name, products in merge_candidates.items():
            print(f"\n'{base_name}' group ({len(products)} products):")
            for product in products:
                colors = [c.name for c in product.colors]
                print(f"  ID {product.id}: {product.name} - Colors: {colors}")

if __name__ == "__main__":
    # First merge the Du Douche products
    merge_du_douche_products()
    
    # Then find other similar products
    find_similar_products()