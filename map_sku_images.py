#!/usr/bin/env python3
"""
Script to map SKU directories to products by analyzing filenames and product names
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

def get_sku_directories():
    """Get all SKU directories and their images"""
    base_path = Path('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow')
    sku_dirs = {}
    
    for root, dirs, files in os.walk(base_path):
        directory_name = Path(root).name
        
        # Only process SKU directories
        if directory_name.startswith('SKU-') or directory_name.startswith('SKU_'):
            images = []
            for file in files:
                if Path(file).suffix.lower() in IMAGE_EXTENSIONS:
                    full_path = Path(root) / file
                    relative_path = full_path.relative_to(Path('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static'))
                    
                    images.append({
                        'file_path': str(full_path),
                        'relative_path': str(relative_path),
                        'filename': file,
                        'url': f"/static/{relative_path}"
                    })
            
            if images:  # Only include directories with images
                sku_dirs[directory_name] = images
    
    return sku_dirs

def extract_product_name_from_filename(filename):
    """Extract product name hints from filename"""
    # Remove file extension
    name = Path(filename).stem
    
    # Common patterns to clean up
    name = re.sub(r'(Main|2nd|3rd|4th|5th|6th|7th)Image', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(Main|2nd|3rd|4th|5th|6th|7th)Photo', '', name, flags=re.IGNORECASE)
    name = re.sub(r'_+', ' ', name)  # Replace underscores with spaces
    name = re.sub(r'\s+', ' ', name)  # Normalize spaces
    name = name.strip()
    
    return name

def find_product_by_name_similarity(search_name):
    """Find product by name similarity"""
    products = Product.query.all()
    
    # Clean search name
    search_clean = search_name.lower().replace(' ', '').replace('_', '')
    
    best_match = None
    best_score = 0
    
    for product in products:
        product_clean = product.name.lower().replace(' ', '').replace('_', '').replace('-', '').replace('&', '').replace("'", '')
        
        # Simple similarity check
        if search_clean in product_clean or product_clean in search_clean:
            # Calculate a simple similarity score
            common_chars = sum(1 for c in search_clean if c in product_clean)
            score = common_chars / max(len(search_clean), len(product_clean))
            
            if score > best_score:
                best_score = score
                best_match = product
    
    return best_match if best_score > 0.3 else None

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

def map_and_import_sku_images():
    """Map SKU directories to products and import images"""
    app = create_flask_app()
    
    with app.app_context():
        print("🔍 Starting SKU image mapping and import...")
        
        # Get all SKU directories
        sku_dirs = get_sku_directories()
        print(f"Found {len(sku_dirs)} SKU directories")
        
        imported_count = 0
        skipped_count = 0
        
        for sku_dir, images in sku_dirs.items():
            print(f"\n=== Processing {sku_dir} ===")
            print(f"Images: {len(images)}")
            
            # Try to extract product name from first image filename
            if images:
                first_image = images[0]['filename']
                product_name_hint = extract_product_name_from_filename(first_image)
                print(f"Product name hint: '{product_name_hint}'")
                
                # Find matching product
                product = find_product_by_name_similarity(product_name_hint)
                
                if product:
                    print(f"✅ Matched to product: {product.name}")
                    
                    # Get the default variant
                    variant = product.default_variant
                    if not variant and product.variants:
                        variant = product.variants[0]
                    
                    if variant:
                        # Check if variant already has images
                        existing_images = ProductImage.query.filter_by(product_variant_id=variant.id).count()
                        if existing_images > 0:
                            print(f"  ⚠️  Variant already has {existing_images} images. Skipping to avoid duplicates.")
                            skipped_count += len(images)
                            continue
                        
                        print(f"  Importing to variant {variant.id}")
                        
                        # Sort images to ensure main image is processed first
                        images.sort(key=lambda x: (not determine_image_priority(x['filename'])[0], x['filename']))
                        
                        # Import images
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
                            
                            print(f"    📷 Added: {img['filename']} (Primary: {is_primary}, Sort: {sort_order if sort_order > 0 else i})")
                    else:
                        print(f"  ❌ No variants found for product")
                        skipped_count += len(images)
                else:
                    print(f"  ❌ No matching product found")
                    skipped_count += len(images)
        
        # Commit changes
        print(f"\n=== SAVING CHANGES ===")
        try:
            db.session.commit()
            print(f"✅ Successfully imported {imported_count} SKU images")
            print(f"⚠️  Skipped {skipped_count} images")
            
            # Final count
            result = db.session.execute(text("SELECT COUNT(*) FROM product_images"))
            total_images = result.scalar()
            print(f"📊 Total images in database: {total_images}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {e}")
            raise

if __name__ == "__main__":
    map_and_import_sku_images()