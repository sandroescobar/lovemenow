#!/usr/bin/env python3
"""Link product images for three more products"""
import os
import sys

# Set working directory
os.chdir('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from dotenv import load_dotenv
load_dotenv('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/.env')

from main import app
from models import db, Product, ProductVariant, ProductImage

with app.app_context():
    print("=" * 80)
    print("LINKING IMAGES FOR NEW PRODUCTS")
    print("=" * 80)
    
    products_images = {
        '603912742312': [
            '/static/IMG/imagesForLovMeNow/603912742312/603912742312_Main_Image.webp',
            '/static/IMG/imagesForLovMeNow/603912742312/603912742312_2nd_Image.webp'
        ],
        '810124860103': [],  # No images found
        '8714273543240': [
            '/static/IMG/imagesForLovMeNow/8714273543240/8714273543240_Main-Image.webp',
            '/static/IMG/imagesForLovMeNow/8714273543240/8714273543240_2nd_Image.webp',
            '/static/IMG/imagesForLovMeNow/8714273543240/8714273543240_3rd_Image.webp'
        ]
    }
    
    for upc, image_urls in products_images.items():
        print()
        print("=" * 80)
        print(f"UPC: {upc}")
        print("=" * 80)
        
        product = Product.query.filter_by(upc=upc).first()
        if not product:
            print(f"❌ Product not found with UPC: {upc}")
            continue
        
        print(f"✓ Found product: {product.name} (ID: {product.id})")
        
        if not image_urls:
            print(f"⚠ No images to link for this product")
            continue
        
        variant = ProductVariant.query.filter_by(product_id=product.id).first()
        if not variant:
            print(f"  Creating default variant...")
            variant = ProductVariant(
                product_id=product.id,
                variant_name='Default'
            )
            db.session.add(variant)
            db.session.flush()
            print(f"  ✓ Created variant: {variant.variant_name or 'Default'} (ID: {variant.id})")
        else:
            print(f"  Using existing variant: {variant.variant_name or 'Default'} (ID: {variant.id})")
        
        print(f"  Linking {len(image_urls)} image(s)...")
        for idx, image_url in enumerate(image_urls):
            existing = ProductImage.query.filter_by(
                product_variant_id=variant.id,
                url=image_url
            ).first()
            
            if existing:
                print(f"    ⚠ Image already exists: {image_url}")
                continue
            
            is_primary = (idx == 0)
            product_image = ProductImage(
                product_variant_id=variant.id,
                url=image_url,
                alt_text=f'{product.name} - Image {idx + 1}',
                is_primary=is_primary,
                sort_order=idx
            )
            db.session.add(product_image)
            print(f"    ✓ Linked image {idx + 1}/{len(image_urls)}: {image_url}")
            if is_primary:
                print(f"      (Primary image)")
        
        db.session.commit()
    
    print()
    print("=" * 80)
    print("✅ ALL IMAGES LINKED!")
    print("=" * 80)
    print("\n⚠ Note: 810124860103 has no images in the filesystem yet.")