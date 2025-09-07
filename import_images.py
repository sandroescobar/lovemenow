#!/usr/bin/env python3
"""
Script to import product images from the organized UPC folders into the database.
Images are organized as: static/IMG/imagesForLovMeNow/{UPC}/{UPC}_Main_Photo.jpeg, etc.
"""

import os
import glob
from app import app
from models import db, Product, ProductVariant, ProductImage

def import_images():
    """Import images from the UPC-organized folder structure"""
    
    with app.app_context():
        images_base_path = "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow"
        
        # Get all UPC folders
        upc_folders = [d for d in os.listdir(images_base_path) 
                      if os.path.isdir(os.path.join(images_base_path, d))]
        
        print(f"Found {len(upc_folders)} UPC folders")
        
        images_added = 0
        products_updated = 0
        
        for upc_folder in upc_folders:
            folder_path = os.path.join(images_base_path, upc_folder)
            
            # Find product by UPC (could be in Product or ProductVariant)
            product = Product.query.filter_by(upc=upc_folder).first()
            variant = ProductVariant.query.filter_by(upc=upc_folder).first()
            
            if not product and not variant:
                print(f"⚠️  No product/variant found for UPC: {upc_folder}")
                continue
            
            # If we found a variant, get its product
            if variant:
                product = variant.product
                print(f"📦 Processing variant {variant.id} for product: {product.name}")
            else:
                print(f"📦 Processing product: {product.name}")
            
            # Find all image files in this UPC folder
            image_patterns = [
                f"{upc_folder}_Main_Photo.*",
                f"{upc_folder}_Main_Image.*", 
                f"{upc_folder}_2nd_Photo.*",
                f"{upc_folder}_2nd_Image.*",
                f"{upc_folder}_3rd_Photo.*",
                f"{upc_folder}_3rd_Image.*",
                f"{upc_folder}_4th_Photo.*",
                f"{upc_folder}_4th_Image.*",
                f"{upc_folder}_5th_Photo.*",
                f"{upc_folder}_5th_Image.*",
            ]
            
            found_images = []
            for pattern in image_patterns:
                matches = glob.glob(os.path.join(folder_path, pattern))
                found_images.extend(matches)
            
            if not found_images:
                print(f"   No images found in {folder_path}")
                continue
            
            # Sort images by name to maintain order (Main, 2nd, 3rd, etc.)
            found_images.sort()
            
            print(f"   Found {len(found_images)} images")
            
            # Process each image
            for image_path in found_images:
                # Convert absolute path to relative path for database storage
                relative_path = image_path.replace("/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/", "")
                
                # Determine which variant to use
                target_variant = variant if variant else product.variants[0] if product.variants else None
                
                if not target_variant:
                    print(f"   ⚠️  No variant found for product {product.name}")
                    continue
                
                # Check if this image already exists
                existing_image = ProductImage.query.filter_by(
                    product_variant_id=target_variant.id,
                    url=relative_path
                ).first()
                
                if existing_image:
                    print(f"   ⏭️  Image already exists: {os.path.basename(image_path)}")
                    continue
                
                # Create new ProductImage
                new_image = ProductImage(
                    product_variant_id=target_variant.id,
                    url=relative_path,
                    alt_text=f"{product.name} - {os.path.basename(image_path)}"
                )
                
                db.session.add(new_image)
                images_added += 1
                print(f"   ✅ Added image: {os.path.basename(image_path)}")
            
            products_updated += 1
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\\n🎉 Successfully imported {images_added} images for {products_updated} products!")
        except Exception as e:
            db.session.rollback()
            print(f"\\n❌ Error committing changes: {e}")

if __name__ == "__main__":
    import_images()