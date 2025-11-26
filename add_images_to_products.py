#!/usr/bin/env python
"""
Script to add images to products using the product UPC (not variant UPC)
This will create a default variant if one doesn't exist
"""
import os
import sys
import glob
from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from routes import db
from models import Product, ProductVariant, ProductImage, Color
from sqlalchemy.orm import joinedload

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

def find_images_for_upc(upc):
    """Find all images for a given UPC in the imagesForLovMeNow folder"""
    base_dir = '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow'
    upc_dir = os.path.join(base_dir, upc)
    
    if not os.path.exists(upc_dir):
        print(f"  ⚠️  Image folder not found: {upc_dir}")
        return []
    
    # Look for images with the naming pattern: upc_Main_Image, upc_2nd_Image, etc.
    image_files = []
    
    # Get all files in the directory
    files = glob.glob(os.path.join(upc_dir, f"{upc}_*"))
    files.sort()
    
    for file_path in files:
        if os.path.isfile(file_path):
            # Get just the filename for storage
            filename = os.path.basename(file_path)
            image_files.append({
                'path': file_path,
                'filename': filename,
                'relative_path': f'IMG/imagesForLovMeNow/{upc}/{filename}'
            })
    
    return image_files

def get_or_create_default_variant(product):
    """Get or create a default variant for the product"""
    # Check if product already has a variant
    if product.variants and len(product.variants) > 0:
        default_variant = product.default_variant or product.variants[0]
        print(f"  ✓ Using existing variant: {default_variant.display_name} (ID: {default_variant.id})")
        return default_variant
    
    # Create a default variant
    print(f"  Creating default variant for product...")
    variant = ProductVariant(
        product_id=product.id,
        color_id=None,  # No color for this product
        variant_name="Default",
        upc=product.upc,
        in_stock=product.in_stock,
        quantity_on_hand=product.quantity_on_hand
    )
    db.session.add(variant)
    db.session.flush()  # Flush to get the ID
    print(f"  ✓ Created variant: {variant.display_name} (ID: {variant.id})")
    return variant

def add_images_for_product_upc(upc):
    """Add images for a product with the given UPC"""
    with app.app_context():
        # Find the product with this UPC
        product = Product.query.filter_by(upc=upc).first()
        
        if not product:
            print(f"❌ No product found with UPC: {upc}")
            return False
        
        print(f"\n✓ Found product {product.id}: {product.name}")
        
        # Get or create a default variant
        variant = get_or_create_default_variant(product)
        
        # Find images for this UPC
        images = find_images_for_upc(upc)
        
        if not images:
            print(f"⚠️  No images found for UPC: {upc}")
            print(f"   Expected folder: /Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow/{upc}")
            return False
        
        print(f"✓ Found {len(images)} image(s)")
        
        # Clear existing images for this variant
        existing = ProductImage.query.filter_by(product_variant_id=variant.id).all()
        if existing:
            for img in existing:
                print(f"  Removing existing image: {img.url}")
                db.session.delete(img)
        
        # Add new images
        for idx, img_info in enumerate(images):
            # Determine if this is the primary image (first one)
            is_primary = (idx == 0)
            
            # Create new ProductImage record
            new_image = ProductImage(
                product_variant_id=variant.id,
                url=img_info['relative_path'],
                is_primary=is_primary,
                sort_order=idx,
                alt_text=f"{product.name} - Image {idx + 1}"
            )
            db.session.add(new_image)
            print(f"  ✓ Added image {idx + 1}: {img_info['filename']} (primary: {is_primary})")
        
        db.session.commit()
        print(f"✅ Successfully added {len(images)} image(s) to product {product.id}")
        return True

if __name__ == '__main__':
    upcs = ['853115004001', '796494106310']
    
    print("\n" + "="*60)
    print("ADDING IMAGES TO PRODUCTS")
    print("="*60)
    
    results = {}
    for upc in upcs:
        print(f"\n{'─'*60}")
        print(f"Processing UPC: {upc}")
        print('─'*60)
        try:
            results[upc] = add_images_for_product_upc(upc)
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            results[upc] = False
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    for upc, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{upc}: {status}")