#!/usr/bin/env python3
"""
Link product images for newly added products
Products: 713079902228, 810124861292, 603912349948 (3 images)
"""
import os
import sys
from app_factory import create_app
from models import db, Product, ProductVariant, ProductImage

def link_product_images():
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("LINKING IMAGES FOR NEW PRODUCTS")
        print("=" * 80)
        
        # Define products and their images
        products_images = {
            '713079902228': [
                '/static/IMG/imagesForLovMeNow/713079902228/713079902228_Main_Image.webp'
            ],
            '810124861292': [
                '/static/IMG/imagesForLovMeNow/810124861292/810124861292_Main_Image.webp'
            ],
            '603912349948': [
                '/static/IMG/imagesForLovMeNow/603912349948/603912349948_Main_Image.webp',
                '/static/IMG/imagesForLovMeNow/603912349948/603912349948_2nd_Image.webp',
                '/static/IMG/imagesForLovMeNow/603912349948/603912349948_3rd_Image.webp'
            ]
        }
        
        for upc, image_urls in products_images.items():
            print("\n" + "=" * 80)
            print(f"UPC: {upc}")
            print("=" * 80)
            
            # Find product by UPC
            product = Product.query.filter_by(upc=upc).first()
            if not product:
                print(f"❌ Product not found with UPC: {upc}")
                continue
            
            print(f"✓ Found product: {product.name} (ID: {product.id})")
            
            # Get or create default variant
            variant = ProductVariant.query.filter_by(product_id=product.id).first()
            if not variant:
                print(f"  Creating default variant...")
                variant = ProductVariant(
                    product_id=product.id,
                    name='Default',
                    price=product.price,
                    is_default=True
                )
                db.session.add(variant)
                db.session.flush()
                print(f"  ✓ Created variant: {variant.name} (ID: {variant.id})")
            else:
                print(f"  Using existing variant: {variant.name} (ID: {variant.id})")
            
            # Link images
            print(f"  Linking {len(image_urls)} image(s)...")
            for idx, image_url in enumerate(image_urls):
                # Check if image already exists
                existing = ProductImage.query.filter_by(
                    product_variant_id=variant.id,
                    url=image_url
                ).first()
                
                if existing:
                    print(f"    ⚠ Image already exists: {image_url}")
                    continue
                
                # Create image entry
                is_primary = (idx == 0)  # First image is primary
                product_image = ProductImage(
                    product_variant_id=variant.id,
                    url=image_url,
                    alt_text=f"{product.name} - Image {idx + 1}",
                    is_primary=is_primary,
                    sort_order=idx
                )
                db.session.add(product_image)
                print(f"    ✓ Linked image {idx + 1}/{len(image_urls)}: {image_url}")
                if is_primary:
                    print(f"      (Primary image)")
            
            db.session.commit()
        
        print("\n" + "=" * 80)
        print("✅ ALL IMAGES LINKED SUCCESSFULLY!")
        print("=" * 80)

if __name__ == '__main__':
    link_product_images()