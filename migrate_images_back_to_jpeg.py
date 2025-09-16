#!/usr/bin/env python3
"""
Script to migrate all image URLs in the database from .webp back to .jpeg
This is the reverse of migrate_images_to_webp.py
"""

import os
from app import app
from models import db, ProductImage

def migrate_images_back_to_jpeg():
    """Update all image URLs from .webp back to .jpeg/.jpg in the database"""
    
    with app.app_context():
        # Get all product images
        all_images = ProductImage.query.all()
        
        print(f"Found {len(all_images)} images in database")
        
        updated_count = 0
        
        for image in all_images:
            original_url = image.url
            updated_url = original_url
            
            # Convert __alpha.webp back to .jpeg
            if original_url.endswith('__alpha.webp'):
                # Try .jpeg first (most common)
                jpeg_url = original_url.replace('__alpha.webp', '.jpeg')
                jpg_url = original_url.replace('__alpha.webp', '.jpg')
            elif original_url.endswith('.webp'):
                # Fallback for regular .webp files
                jpeg_url = original_url.replace('.webp', '.jpeg')
                jpg_url = original_url.replace('.webp', '.jpg')
                
                # Check which file exists
                if jpeg_url.startswith('/static/'):
                    jpeg_path = f"/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/{jpeg_url[8:]}"
                else:
                    jpeg_path = f"/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/{jpeg_url}"
                
                if jpg_url.startswith('/static/'):
                    jpg_path = f"/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/{jpg_url[8:]}"
                else:
                    jpg_path = f"/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/{jpg_url}"
                
                if os.path.exists(jpeg_path):
                    updated_url = jpeg_url
                elif os.path.exists(jpg_path):
                    updated_url = jpg_url
                else:
                    print(f"⚠️  Neither JPEG nor JPG file found for: {original_url}")
                    continue
            
            # Only update if URL changed
            if updated_url != original_url:
                print(f"✅ Reverting: {original_url} → {updated_url}")
                image.url = updated_url
                updated_count += 1
        
        if updated_count > 0:
            try:
                db.session.commit()
                print(f"\n🎉 Successfully reverted {updated_count} image URLs back to JPEG format!")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error updating database: {e}")
        else:
            print("\n📝 No images needed reverting.")

if __name__ == "__main__":
    migrate_images_back_to_jpeg()