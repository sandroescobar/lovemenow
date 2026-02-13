#!/usr/bin/env python3
import os
import sys

# Set working directory
BASE_DIR = '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow'
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from main import app
from models import db, Product, ProductVariant, ProductImage

def link_images():
    mapping = {
        186: '782421077877',
        187: '891875004626',
        188: '680174004631',
        190: '782421100889',
        191: '012436771218',
        192: '782421177805',
        193: '532720007088',
        194: '925326153226',
        195: '532720007064'
    }

    with app.app_context():
        for product_id, upc in mapping.items():
            print(f"\nProcessing Product ID: {product_id} (UPC: {upc})")
            
            product = Product.query.get(product_id)
            if not product:
                print(f"❌ Product not found with ID: {product_id}")
                continue

            print(f"✓ Found product: {product.name}")

            # Get or create default variant
            variant = ProductVariant.query.filter_by(product_id=product.id).first()
            if not variant:
                print(f"  Creating default variant...")
                variant = ProductVariant(
                    product_id=product.id,
                    variant_name='Default',
                    upc=upc
                )
                db.session.add(variant)
                db.session.flush()
                print(f"  ✓ Created variant ID: {variant.id}")
            else:
                print(f"  Using existing variant ID: {variant.id}")
                if not variant.upc:
                    variant.upc = upc
                    db.session.add(variant)

            # Link images from directory
            img_dir = f'static/IMG/imagesForLovMeNow/{upc}'
            if not os.path.exists(img_dir):
                print(f"  ❌ Image directory not found: {img_dir}")
                continue

            # Get all image files (filtering for webp, png, jpg, jpeg)
            image_files = sorted([
                f for f in os.listdir(img_dir) 
                if f.lower().endswith(('.webp', '.png', '.jpg', '.jpeg'))
            ])

            if not image_files:
                print(f"  ❌ No images found in {img_dir}")
                continue

            print(f"  Found {len(image_files)} images. Linking...")
            
            for idx, img_file in enumerate(image_files):
                img_url = f'/static/IMG/imagesForLovMeNow/{upc}/{img_file}'
                
                # Check if image already linked
                existing = ProductImage.query.filter_by(
                    product_variant_id=variant.id,
                    url=img_url
                ).first()

                if existing:
                    print(f"    ⚠ Image already exists: {img_file}")
                    continue

                is_primary = (idx == 0)
                new_img = ProductImage(
                    product_variant_id=variant.id,
                    url=img_url,
                    is_primary=is_primary,
                    sort_order=idx,
                    alt_text=f"{product.name} - {img_file}"
                )
                db.session.add(new_img)
                print(f"    ✓ Linked: {img_file} (Primary: {is_primary})")

        db.session.commit()
        print("\n✅ All updates committed to database.")

if __name__ == "__main__":
    link_images()
