#!/usr/bin/env python3
"""
Fix the ProductImage records to point to the correct PNG files
"""

from app import create_app
from models import Product, ProductVariant, ProductImage, db

def fix_image_paths():
    """Fix the ProductImage paths to match the actual PNG files"""
    
    # Target UPCs and their correct image paths
    fixes = {
        '657447102899': {
            'variant_id': 24,
            'new_path': '/static/IMG/imagesForLovMeNow/657447102899/657447102899_Main_Photo.png'
        },
        '657447102905': {
            'variant_id': 33,
            'new_path': '/static/IMG/imagesForLovMeNow/657447102905/657447102905_Main_Photo.png'
        }
    }
    
    print("🔧 Fixing ProductImage paths...")
    
    for upc, fix_data in fixes.items():
        variant_id = fix_data['variant_id']
        new_path = fix_data['new_path']
        
        # Find the ProductImage record for this variant
        image = ProductImage.query.filter_by(product_variant_id=variant_id).first()
        
        if image:
            print(f"\n✅ Found ProductImage for variant {variant_id} (UPC {upc}):")
            print(f"   Current path: {image.url}")
            print(f"   New path: {new_path}")
            
            # Update the path
            image.url = new_path
            print(f"   ✅ Updated!")
        else:
            print(f"❌ No ProductImage found for variant {variant_id}")
    
    # Commit the changes
    try:
        db.session.commit()
        print("\n✅ Successfully updated ProductImage paths!")
        
        # Verify the changes
        print("\n🔍 Verifying changes...")
        for upc, fix_data in fixes.items():
            variant_id = fix_data['variant_id']
            image = ProductImage.query.filter_by(product_variant_id=variant_id).first()
            if image:
                print(f"   Variant {variant_id}: {image.url}")
                    
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating paths: {str(e)}")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        fix_image_paths()