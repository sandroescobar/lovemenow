#!/usr/bin/env python3
"""
Script to update ALL product images to use PNG format when available
This will change the priority order to: PNG > JPEG > WebP
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DB_URL = os.getenv('DB_URL')
if not DB_URL:
    print("Error: DB_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

def update_all_images_to_png():
    """Update all product images to use PNG format when available"""
    session = Session()
    
    try:
        print("🔍 Finding all product images...")
        
        # Get all current product images
        result = session.execute(text("""
            SELECT pi.id, pi.url, p.name, p.upc
            FROM product_images pi
            JOIN product_variants pv ON pi.product_variant_id = pv.id
            JOIN products p ON pv.product_id = p.id
            ORDER BY p.name
        """))
        
        all_images = result.fetchall()
        print(f"Found {len(all_images)} total image records")
        
        updates_made = 0
        
        for image in all_images:
            original_url = image.url
            updated_url = original_url
            
            # Convert WebP to PNG
            if '__alpha.webp' in original_url:
                updated_url = original_url.replace('__alpha.webp', '.png')
            elif '.webp' in original_url:
                updated_url = original_url.replace('.webp', '.png')
            
            # Convert JPEG to PNG
            elif '.jpeg' in original_url:
                updated_url = original_url.replace('.jpeg', '.png')
            elif '.jpg' in original_url:
                updated_url = original_url.replace('.jpg', '.png')
            
            # If we made a change, update the database
            if updated_url != original_url:
                session.execute(text("""
                    UPDATE product_images 
                    SET url = :new_url 
                    WHERE id = :image_id
                """), {
                    'new_url': updated_url,
                    'image_id': image.id
                })
                
                updates_made += 1
                print(f"✅ Updated: {image.name} (UPC: {image.upc})")
                print(f"   From: {original_url}")
                print(f"   To:   {updated_url}")
                print()
        
        if updates_made > 0:
            session.commit()
            print(f"🎉 Successfully updated {updates_made} image records to use PNG format!")
        else:
            print("ℹ️  No updates needed - all images are already using optimal formats")
        
        print("\n📋 Summary of current image formats:")
        result = session.execute(text("""
            SELECT 
                CASE 
                    WHEN pi.url LIKE '%.png%' THEN 'PNG'
                    WHEN pi.url LIKE '%.webp%' THEN 'WebP'
                    WHEN pi.url LIKE '%.jpeg%' OR pi.url LIKE '%.jpg%' THEN 'JPEG'
                    ELSE 'Other'
                END as format,
                COUNT(*) as count
            FROM product_images pi
            GROUP BY format
            ORDER BY count DESC
        """))
        
        formats = result.fetchall()
        for fmt in formats:
            print(f"   {fmt.format}: {fmt.count} images")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error updating images: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    print("🖼️  PNG Image Converter")
    print("=" * 50)
    print("This will update ALL product images to use PNG format")
    print("Priority order: PNG > JPEG > WebP")
    print("=" * 50)
    
    confirm = input("Continue? (y/N): ").lower().strip()
    if confirm in ['y', 'yes']:
        update_all_images_to_png()
    else:
        print("Operation cancelled.")