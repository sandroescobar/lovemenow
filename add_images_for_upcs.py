#!/usr/bin/env python
"""
Script to add images from the imagesForLovMeNow folder to product variants by UPC
"""
import os
import sys
import glob
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

# Setup Flask app
from flask import Flask
from routes import db
from models import ProductVariant, ProductImage

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
        print(f"❌ Directory not found: {upc_dir}")
        return []
    
    # Look for images with the naming pattern: upc_Main_Image, upc_2nd_Image, etc.
    image_files = []
    
    # Get all files in the directory
    files = glob.glob(os.path.join(upc_dir, f"{upc}_*"))

    def sort_key(file_path):
        name = os.path.basename(file_path).lower()
        # Ensure "main" images come first, followed by numbered sequence order
        priority_order = [
            "main", "1st", "first", "2nd", "second", "3rd", "third",
            "4th", "fourth", "5th", "fifth", "6th", "sixth", "7th", "seventh"
        ]
        priority = 100
        for idx, token in enumerate(priority_order):
            if token in name:
                priority = idx
                break
        return (priority, name)

    files.sort(key=sort_key)
    
    for file_path in files:
        if os.path.isfile(file_path):
            filename = os.path.basename(file_path)
            image_files.append({
                'path': file_path,
                'filename': filename,
                'relative_path': f'IMG/imagesForLovMeNow/{upc}/{filename}'
            })
    
    return image_files

def add_images_for_upc(upc):
    """Add images for a specific UPC to the database"""
    with app.app_context():
        # Find the variant with this UPC
        variant = ProductVariant.query.filter_by(upc=upc).first()
        
        if not variant:
            print(f"❌ No variant found with UPC: {upc}")
            return False
        
        print(f"\n✓ Found variant: {variant.display_name} (ID: {variant.id}, Product: {variant.product.name})")
        
        # Find images for this UPC
        images = find_images_for_upc(upc)
        
        if not images:
            print(f"⚠️  No images found for UPC: {upc}")
            return False
        
        print(f"✓ Found {len(images)} image(s)")
        
        # Clear existing images for this variant
        existing = ProductImage.query.filter_by(product_variant_id=variant.id).all()
        if existing:
            for img in existing:
                print(f"  Removing existing image: {img.url}")
                from routes import db
                db.session.delete(img)
            from routes import db
            db.session.commit()
        
        # Add new images
        from routes import db
        for idx, img_info in enumerate(images):
            # Determine if this is the primary image (first one)
            is_primary = (idx == 0)
            
            # Create new ProductImage record
            new_image = ProductImage(
                product_variant_id=variant.id,
                url=img_info['relative_path'],
                is_primary=is_primary,
                sort_order=idx,
                alt_text=f"{variant.display_name} - Image {idx + 1}"
            )
            db.session.add(new_image)
            print(f"  Added image {idx + 1}: {img_info['filename']} (primary: {is_primary})")
        
        db.session.commit()
        print(f"✅ Successfully added {len(images)} image(s) to variant {variant.id}")
        return True

if __name__ == '__main__':
    upcs = ['853115004001', '796494106310']
    
    results = {}
    for upc in upcs:
        print(f"\n{'='*60}")
        print(f"Processing UPC: {upc}")
        print('='*60)
        results[upc] = add_images_for_upc(upc)
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    for upc, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{upc}: {status}")