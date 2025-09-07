#!/usr/bin/env python3
"""
Complete image import script that handles both UPC and SKU directories
and updates product image_url fields
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

def get_all_image_directories():
    """Get all image directories (both UPC and SKU)"""
    base_path = Path('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow')
    directories = {}
    
    for root, dirs, files in os.walk(base_path):
        directory_name = Path(root).name
        
        # Skip the base directory itself
        if directory_name == 'imagesForLovMeNow':
            continue
            
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
            directories[directory_name] = {
                'type': 'UPC' if directory_name.isdigit() else 'SKU',
                'images': images
            }
    
    return directories

def determine_image_priority(filename):
    """Determine if image should be primary based on filename"""
    filename_lower = filename.lower()
    
    # Main/Primary images should be primary
    if 'main' in filename_lower or 'primary' in filename_lower:
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
    elif '8th' in filename_lower:
        return False, 7
    else:
        # For images without specific numbering, use filename for consistent ordering
        return False, 0

def get_image_sort_key(image_info):
    """Get sort key for proper image ordering"""
    filename = image_info['filename'].lower()
    
    # Main/Primary images first
    if 'main' in filename or 'primary' in filename:
        return (0, filename)
    
    # Then numbered images in order
    if '2nd' in filename:
        return (1, filename)
    elif '3rd' in filename:
        return (2, filename)
    elif '4th' in filename:
        return (3, filename)
    elif '5th' in filename:
        return (4, filename)
    elif '6th' in filename:
        return (5, filename)
    elif '7th' in filename:
        return (6, filename)
    elif '8th' in filename:
        return (7, filename)
    else:
        # For images without specific numbering, treat as main image (first)
        return (0, filename)

def find_product_by_upc(upc):
    """Find product by UPC or base_upc"""
    product = Product.query.filter_by(upc=upc).first()
    if not product:
        product = Product.query.filter_by(base_upc=upc).first()
    return product

def extract_product_name_from_filename(filename):
    """Extract product name hints from filename"""
    # Remove file extension
    name = Path(filename).stem
    
    # Common patterns to clean up
    name = re.sub(r'(Main|Primary|2nd|3rd|4th|5th|6th|7th)(Image|Photo|Photos)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'_+', ' ', name)  # Replace underscores with spaces
    name = re.sub(r'\s+', ' ', name)  # Normalize spaces
    name = name.strip()
    
    return name

def find_product_by_name_similarity(search_name):
    """Find product by name similarity"""
    products = Product.query.all()
    
    # Clean search name
    search_clean = search_name.lower().replace(' ', '').replace('_', '').replace('-', '').replace('&', '').replace("'", '')
    
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

def complete_image_import():
    """Complete image import and URL update"""
    app = create_flask_app()
    
    with app.app_context():
        print("🚀 Starting complete image import process...")
        
        # Step 1: Clear existing images
        print("\n=== STEP 1: CLEARING EXISTING IMAGES ===")
        result = db.session.execute(text("SELECT COUNT(*) FROM product_images"))
        count = result.scalar()
        print(f"Found {count} existing images to remove")
        
        db.session.execute(text("DELETE FROM product_images"))
        db.session.commit()
        print("✅ All existing images cleared")
        
        # Step 2: Get all directories
        print("\n=== STEP 2: SCANNING IMAGE DIRECTORIES ===")
        directories = get_all_image_directories()
        
        upc_dirs = {k: v for k, v in directories.items() if v['type'] == 'UPC'}
        sku_dirs = {k: v for k, v in directories.items() if v['type'] == 'SKU'}
        
        print(f"Found {len(upc_dirs)} UPC directories")
        print(f"Found {len(sku_dirs)} SKU directories")
        print(f"Total image files: {sum(len(d['images']) for d in directories.values())}")
        
        imported_count = 0
        skipped_count = 0
        
        # Step 3: Process UPC directories
        print("\n=== STEP 3: PROCESSING UPC DIRECTORIES ===")
        for directory_name, dir_data in upc_dirs.items():
            print(f"\nProcessing UPC directory: {directory_name}")
            
            product = find_product_by_upc(directory_name)
            if not product:
                print(f"  ❌ No product found for UPC: {directory_name}")
                skipped_count += len(dir_data['images'])
                continue
            
            print(f"  ✅ Found product: {product.name}")
            
            # Get default variant
            variant = product.default_variant
            if not variant and product.variants:
                variant = product.variants[0]
            
            if not variant:
                print(f"  ❌ No variants found for product")
                skipped_count += len(dir_data['images'])
                continue
            
            # Import images with proper sorting
            images = dir_data['images']
            images.sort(key=get_image_sort_key)
            
            for i, img in enumerate(images):
                is_primary, sort_order = determine_image_priority(img['filename'])
                
                alt_text = img['filename'].replace('_', ' ').replace('.jpeg', '').replace('.jpg', '').replace('.png', '')
                
                product_image = ProductImage(
                    product_variant_id=variant.id,
                    url=img['url'],
                    is_primary=is_primary,
                    sort_order=i,  # Use enumeration index for consistent ordering
                    alt_text=alt_text
                )
                
                db.session.add(product_image)
                imported_count += 1
                
                print(f"    📷 Added: {img['filename']} (Primary: {is_primary})")
        
        # Step 4: Process SKU directories
        print("\n=== STEP 4: PROCESSING SKU DIRECTORIES ===")
        for directory_name, dir_data in sku_dirs.items():
            print(f"\nProcessing SKU directory: {directory_name}")
            
            # Extract product name from first image
            if dir_data['images']:
                first_image = dir_data['images'][0]['filename']
                product_name_hint = extract_product_name_from_filename(first_image)
                print(f"  Product name hint: '{product_name_hint}'")
                
                product = find_product_by_name_similarity(product_name_hint)
                
                if not product:
                    print(f"  ❌ No matching product found")
                    skipped_count += len(dir_data['images'])
                    continue
                
                print(f"  ✅ Matched to product: {product.name}")
                
                # Get default variant
                variant = product.default_variant
                if not variant and product.variants:
                    variant = product.variants[0]
                
                if not variant:
                    print(f"  ❌ No variants found for product")
                    skipped_count += len(dir_data['images'])
                    continue
                
                # Check if variant already has images (avoid duplicates)
                existing_images = ProductImage.query.filter_by(product_variant_id=variant.id).count()
                if existing_images > 0:
                    print(f"  ⚠️  Variant already has {existing_images} images. Skipping.")
                    skipped_count += len(dir_data['images'])
                    continue
                
                # Import images with proper sorting
                images = dir_data['images']
                images.sort(key=get_image_sort_key)
                
                for i, img in enumerate(images):
                    is_primary, sort_order = determine_image_priority(img['filename'])
                    
                    alt_text = img['filename'].replace('_', ' ').replace('.jpeg', '').replace('.jpg', '').replace('.png', '')
                    
                    product_image = ProductImage(
                        product_variant_id=variant.id,
                        url=img['url'],
                        is_primary=is_primary,
                        sort_order=i,  # Use enumeration index for consistent ordering
                        alt_text=alt_text
                    )
                    
                    db.session.add(product_image)
                    imported_count += 1
                    
                    print(f"    📷 Added: {img['filename']} (Primary: {is_primary})")
        
        # Step 5: Commit all changes (removed image_url updates as we now use product_images table)
        print("\n=== STEP 5: SAVING ALL CHANGES ===")
        try:
            db.session.commit()
            
            # Final statistics
            result = db.session.execute(text("SELECT COUNT(*) FROM product_images"))
            total_images = result.scalar()
            
            total_products = Product.query.count()
            products_with_images = 0
            
            for product in Product.query.all():
                has_images = any(
                    ProductImage.query.filter_by(product_variant_id=variant.id).count() > 0 
                    for variant in product.variants
                )
                if has_images:
                    products_with_images += 1
            
            print(f"✅ SUCCESS! Import completed:")
            print(f"   • Total images imported: {imported_count}")
            print(f"   • Images skipped: {skipped_count}")
            print(f"   • Total images in database: {total_images}")
            print(f"   • Products with images: {products_with_images}/{total_products}")
            print(f"   • Coverage: {(products_with_images/total_products)*100:.1f}%")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {e}")
            raise

if __name__ == "__main__":
    complete_image_import()