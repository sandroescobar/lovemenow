#!/usr/bin/env python3
"""
Fix missing images for specific UPCs: 657447102905 and 657447102899
"""
import os
import sys
from app import create_app
from models import db, Product, ProductVariant, ProductImage

def fix_missing_images():
    """Add missing ProductImage records for the specified UPCs"""
    app = create_app()
    
    with app.app_context():
        # UPCs to fix
        upcs_to_fix = ['657447102905', '657447102899']
        
        for upc in upcs_to_fix:
            print(f"\n🔍 Checking UPC: {upc}")
            
            # Find variant with this UPC
            variant = ProductVariant.query.filter_by(upc=upc).first()
            if not variant:
                print(f"❌ No variant found with UPC: {upc}")
                continue
                
            print(f"✅ Found variant ID: {variant.id} for product: {variant.product.name}")
            
            # Check if images already exist
            existing_images = ProductImage.query.filter_by(variant_id=variant.id).all()
            if existing_images:
                print(f"📸 Found {len(existing_images)} existing images:")
                for img in existing_images:
                    print(f"   - {img.url} (primary: {img.is_primary})")
                continue
            
            # Check if the PNG file exists
            image_path = f"IMG/imagesForLovMeNow/{upc}/{upc}_Main_Photo.png"
            full_path = os.path.join(app.static_folder, image_path)
            
            if not os.path.exists(full_path):
                print(f"❌ Image file not found: {full_path}")
                continue
                
            print(f"✅ Found image file: {image_path}")
            
            # Create ProductImage record
            try:
                product_image = ProductImage(
                    variant_id=variant.id,
                    url=image_path,
                    is_primary=True,
                    sort_order=1,
                    alt_text=f"{variant.product.name} - Main Photo"
                )
                
                db.session.add(product_image)
                db.session.commit()
                
                print(f"✅ Added ProductImage record for {upc}")
                
            except Exception as e:
                print(f"❌ Error adding ProductImage for {upc}: {str(e)}")
                db.session.rollback()
        
        print(f"\n🎉 Image fix process completed!")

if __name__ == '__main__':
    fix_missing_images()