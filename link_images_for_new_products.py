#!/usr/bin/env python3
"""
Link images for the 3 new products to their database entries.
This script creates ProductVariant and ProductImage entries for:
- 810124861230
- 810124861186
- 850000918283
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from app import app, db
from models import Product, ProductVariant, ProductImage

# UPCs and their image files
PRODUCTS_TO_LINK = {
    '810124861230': '810124861230_Main_Image.webp',
    '810124861186': '810124861186_Main_Image.webp',
    '850000918283': '850000918283_Main_Image.webp',
}

IMAGE_BASE_PATH = '/static/IMG/imagesForLovMeNow'

def link_images():
    """Link images for the new products."""
    with app.app_context():
        print("=" * 80)
        print("LINKING IMAGES FOR NEW PRODUCTS")
        print("=" * 80)
        
        for upc, image_filename in PRODUCTS_TO_LINK.items():
            print(f"\n{'='*80}")
            print(f"UPC: {upc}")
            print(f"{'='*80}")
            
            # Find product by UPC
            product = Product.query.filter_by(upc=upc).first()
            
            if not product:
                print(f"❌ Product with UPC {upc} NOT FOUND in database!")
                continue
            
            print(f"✓ Found product: {product.name} (ID: {product.id})")
            
            # Check if product already has variants
            variants = ProductVariant.query.filter_by(product_id=product.id).all()
            print(f"  Existing variants: {len(variants)}")
            
            if not variants:
                # Create a default variant
                print(f"  Creating default variant...")
                variant = ProductVariant(
                    product_id=product.id,
                    variant_name="Default",
                    upc=upc
                )
                db.session.add(variant)
                db.session.flush()  # Get the variant ID
                print(f"  ✓ Created variant: {variant.variant_name} (ID: {variant.id})")
            else:
                # Use the first existing variant
                variant = variants[0]
                print(f"  Using existing variant: {variant.variant_name} (ID: {variant.id})")
            
            # Check if image already exists for this variant
            existing_image = ProductImage.query.filter_by(product_variant_id=variant.id).first()
            
            if existing_image:
                print(f"  ⚠ Image already exists for this variant: {existing_image.url}")
                print(f"  Skipping...")
                continue
            
            # Create image URL path
            image_url = f"{IMAGE_BASE_PATH}/{upc}/{image_filename}"
            
            # Create ProductImage entry
            product_image = ProductImage(
                product_variant_id=variant.id,
                url=image_url,
                is_primary=True
            )
            db.session.add(product_image)
            print(f"  ✓ Created ProductImage entry")
            print(f"    - Image URL: {image_url}")
            print(f"    - Is Primary: True")
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n{'='*80}")
            print("✅ ALL IMAGES LINKED SUCCESSFULLY!")
            print(f"{'='*80}\n")
        except Exception as e:
            db.session.rollback()
            print(f"\n{'='*80}")
            print(f"❌ ERROR: {str(e)}")
            print(f"{'='*80}\n")
            return False
        
        return True

if __name__ == '__main__':
    link_images()