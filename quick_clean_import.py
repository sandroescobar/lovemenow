#!/usr/bin/env python3
"""
Script to quickly clean existing images and properly import all images from imagesForLovMeNow directory
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from models import db, Product, ProductVariant, ProductImage
from sqlalchemy import text

# Load environment variables
load_dotenv()

# Image file extensions to look for
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

def create_flask_app():
    """Create Flask app similar to main.py"""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DB_URL",
        "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize extensions
    from routes import bcrypt, login_mgr
    db.init_app(app)
    bcrypt.init_app(app)
    login_mgr.init_app(app)
    
    return app

def get_image_files():
    """Get all image files from the imagesForLovMeNow directory"""
    base_path = Path('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow')
    image_files = []
    
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if Path(file).suffix.lower() in IMAGE_EXTENSIONS:
                full_path = Path(root) / file
                # Get the directory name (SKU or UPC)
                directory_name = Path(root).name
                
                # Create relative path from static directory
                relative_path = full_path.relative_to(Path('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static'))
                
                image_files.append({
                    'file_path': str(full_path),
                    'relative_path': str(relative_path),
                    'directory_name': directory_name,
                    'filename': file,
                    'url': f"/static/{relative_path}"
                })
    
    return image_files

def determine_image_priority(filename):
    """Determine if image should be primary based on filename"""
    filename_lower = filename.lower()
    
    # Main images should be primary
    if 'main' in filename_lower:
        return True, 0
    
    # Otherwise, determine sort order based on filename
    if '2nd' in filename_lower:
        return False, 1
    elif '3rd' in filename_lower:
        return False, 2
    elif '4th' in filename_lower:
        return False, 3
    elif '5th' in filename_lower:
        return False, 4
    elif '6th' in filename_lower:
        return False, 5
    elif '7th' in filename_lower:
        return False, 6
    else:
        return False, 0

def find_matching_product_variant(identifier):
    """Find product variant by UPC, base_upc, or wholesale_id"""
    # First try to find by UPC
    product = Product.query.filter_by(upc=identifier).first()
    if not product:
        # Try with base_upc
        product = Product.query.filter_by(base_upc=identifier).first()
    
    if not product:
        # Try to find by wholesale_id (exact match)
        product = Product.query.filter_by(wholesale_id=identifier).first()
    
    if not product:
        # Try to find by wholesale_id (convert identifier to int if possible)
        try:
            wholesale_id = int(identifier)
            product = Product.query.filter_by(wholesale_id=wholesale_id).first()
        except ValueError:
            pass
    
    if product:
        # Get the default variant for this product
        variant = product.default_variant
        if variant:
            return variant
        
        # If no default variant, get the first variant
        if product.variants:
            return product.variants[0]
    
    return None

def quick_clean_and_import():
    """Main function to quickly clean and import images"""
    app = create_flask_app()
    
    with app.app_context():
        print("🧹 Starting quick image cleanup and import process...")
        
        # Step 1: Quick clean using SQL
        print("\n=== STEP 1: QUICK CLEANING EXISTING IMAGES ===")
        result = db.session.execute(text("SELECT COUNT(*) FROM product_images"))
        count = result.scalar()
        print(f"Found {count} existing images to remove")
        
        # Use raw SQL for faster deletion
        db.session.execute(text("DELETE FROM product_images"))
        db.session.commit()
        print("✅ All existing images removed")
        
        # Step 2: Get all image files
        print("\n=== STEP 2: SCANNING IMAGE FILES ===")
        image_files = get_image_files()
        print(f"Found {len(image_files)} image files")
        
        # Group images by directory (product)
        images_by_directory = {}
        for img in image_files:
            dir_name = img['directory_name']
            if dir_name not in images_by_directory:
                images_by_directory[dir_name] = []
            images_by_directory[dir_name].append(img)
        
        print(f"Found images for {len(images_by_directory)} products")
        
        # Step 3: Process each directory
        print("\n=== STEP 3: IMPORTING IMAGES ===")
        imported_count = 0
        skipped_count = 0
        
        for directory_name, images in images_by_directory.items():
            print(f"\nProcessing directory: {directory_name}")
            
            # For UPC directories, use the directory name directly
            if directory_name.isdigit():
                identifier = directory_name
            else:
                # For SKU directories, skip for now since they don't match
                print(f"  ⚠️  Skipping SKU directory: {directory_name} (no matching logic)")
                skipped_count += len(images)
                continue
            
            print(f"  Looking for product with UPC: {identifier}")
            
            # Find matching product variant
            variant = find_matching_product_variant(identifier)
            
            if not variant:
                print(f"  ❌ No matching product variant found for {identifier}")
                skipped_count += len(images)
                continue
            
            print(f"  ✅ Found product: {variant.product.name} (Variant ID: {variant.id})")
            
            # Sort images to ensure main image is processed first
            images.sort(key=lambda x: (not determine_image_priority(x['filename'])[0], x['filename']))
            
            # Import images for this variant
            for i, img in enumerate(images):
                is_primary, sort_order = determine_image_priority(img['filename'])
                
                # Create alt text from filename
                alt_text = img['filename'].replace('_', ' ').replace('.jpeg', '').replace('.jpg', '').replace('.png', '')
                
                # Create ProductImage record
                product_image = ProductImage(
                    product_variant_id=variant.id,
                    url=img['url'],
                    is_primary=is_primary,
                    sort_order=sort_order if sort_order > 0 else i,
                    alt_text=alt_text
                )
                
                db.session.add(product_image)
                imported_count += 1
                
                print(f"    📷 Added image: {img['filename']} (Primary: {is_primary}, Sort: {sort_order if sort_order > 0 else i})")
        
        # Step 4: Commit all changes
        print("\n=== STEP 4: SAVING CHANGES ===")
        try:
            db.session.commit()
            print(f"✅ Successfully imported {imported_count} images")
            print(f"⚠️  Skipped {skipped_count} images (no matching product)")
            
            # Final verification
            result = db.session.execute(text("SELECT COUNT(*) FROM product_images"))
            total_images = result.scalar()
            print(f"📊 Total images in database: {total_images}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {e}")
            raise

if __name__ == "__main__":
    quick_clean_and_import()