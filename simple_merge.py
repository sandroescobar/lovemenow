#!/usr/bin/env python3
"""
Simple script to merge Du Douche products
"""

from app import create_app
from models import Product, ProductVariant, ProductImage, Color
from routes import db
from sqlalchemy import text

def merge_du_douche():
    """Merge Du Douche Stone and Midnight into one product with variants"""
    
    app = create_app()
    with app.app_context():
        print("Merging Du Douche products...")
        
        # Get the two products
        stone_product = Product.query.filter_by(id=63).first()
        midnight_product = Product.query.filter_by(id=64).first()
        
        if not stone_product or not midnight_product:
            print("❌ Could not find both products")
            return
        
        print(f"Stone product: {stone_product.name}")
        print(f"Midnight product: {midnight_product.name}")
        
        # Get colors
        stone_color = Color.query.filter_by(name='Greige (Warm Gray)').first()
        midnight_color = Color.query.filter_by(name='Black').first()
        
        if not stone_color or not midnight_color:
            print("❌ Could not find required colors")
            return
        
        # Update the main product
        stone_product.name = "Du Douche"  # Clean name without color
        stone_product.base_upc = "860008092000"  # Common base UPC
        
        # Update the stone variant to have the stone color
        stone_variant = stone_product.variants[0]
        stone_variant.color_id = stone_color.id
        stone_variant.variant_name = "Stone"
        
        # Create new variant for midnight
        midnight_variant = ProductVariant(
            product_id=stone_product.id,
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
        
        # Update cart items using raw SQL
        db.session.execute(text(
            "UPDATE cart SET product_id = :stone_id WHERE product_id = :midnight_id"
        ), {
            'stone_id': stone_product.id,
            'midnight_id': midnight_product.id
        })
        
        # Update wishlist items using raw SQL
        db.session.execute(text(
            "UPDATE wishlist SET product_id = :stone_id WHERE product_id = :midnight_id"
        ), {
            'stone_id': stone_product.id,
            'midnight_id': midnight_product.id
        })
        
        # Update the main product's colors relationship
        stone_product.colors = [stone_color, midnight_color]
        
        # Delete the midnight product and its variant
        db.session.delete(midnight_product.variants[0])
        db.session.delete(midnight_product)
        
        try:
            db.session.commit()
            print("✅ Successfully merged Du Douche products!")
            
            # Verify the result
            merged_product = Product.query.filter_by(id=63).first()
            print(f"Merged product: {merged_product.name}")
            print(f"Variants: {len(merged_product.variants)}")
            for variant in merged_product.variants:
                print(f"  Variant {variant.id}: {variant.variant_name} - {variant.color.name if variant.color else 'No color'}")
            print(f"Available colors: {[c.name for c in merged_product.available_colors]}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error merging products: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    merge_du_douche()