#!/usr/bin/env python3
"""
Script to migrate all image URLs in the database from .jpeg to .webp
"""

import os
from app import app
from models import db, ProductImage

def migrate_images_to_webp():
    """Update all image URLs from .jpeg/.jpg to .webp in the database"""
    
    with app.app_context():
        # Get all product images
        all_images = ProductImage.query.all()
        
        print(f"Found {len(all_images)} images in database")
        
        updated_count = 0
        
        for image in all_images:
            original_url = image.url
            updated_url = original_url
            
            # Convert .jpeg to __alpha.webp
            if original_url.endswith('.jpeg'):
                updated_url = original_url.replace('.jpeg', '__alpha.webp')
            # Convert .jpg to __alpha.webp  
            elif original_url.endswith('.jpg'):
                updated_url = original_url.replace('.jpg', '__alpha.webp')
            
            # Only update if URL changed
            if updated_url != original_url:
                # Check if the WebP file actually exists
                if updated_url.startswith('/static/'):
                    file_path = f"/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/{updated_url[8:]}"
                else:
                    file_path = f"/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/{updated_url}"
                
                if os.path.exists(file_path):
                    print(f"✅ Updating: {original_url} → {updated_url}")
                    image.url = updated_url
                    updated_count += 1
                else:
                    print(f"⚠️  WebP file not found: {file_path}")
                    print(f"   Keeping original: {original_url}")
        
        if updated_count > 0:
            try:
                db.session.commit()
                print(f"\n🎉 Successfully updated {updated_count} image URLs to WebP format!")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error updating database: {e}")
        else:
            print("\n📝 No images needed updating.")

if __name__ == "__main__":
    migrate_images_to_webp()