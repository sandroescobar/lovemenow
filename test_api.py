#!/usr/bin/env python3
"""
Test the API endpoint to see what's being returned for the variants
"""

from app import create_app
from models import ProductVariant
import os

def test_api_endpoint():
    """Test the variant images API endpoint"""
    
    # Target variant IDs
    variant_ids = [24, 33]  # Medium and Large
    
    print("🔍 Testing API endpoint for variant images...")
    
    for variant_id in variant_ids:
        variant = ProductVariant.query.get(variant_id)
        if variant:
            print(f"\n✅ Variant ID {variant_id}:")
            print(f"   Product: {variant.product.name}")
            print(f"   UPC: {variant.upc}")
            
            # Simulate what the API endpoint does
            upc = variant.upc
            if upc:
                images = [
                    f"/static/IMG/imagesForLovMeNow/{upc}/{upc}_Main_Photo.png",
                    f"/static/IMG/imagesForLovMeNow/{upc}/{upc}_2nd_Photo.png"
                ]
                print(f"   API would return: {images}")
                
                # Check if files actually exist
                for img_path in images:
                    # Convert web path to file system path
                    file_path = img_path.replace("/static/", "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/")
                    exists = os.path.exists(file_path)
                    print(f"   File exists: {exists} - {file_path}")
                    
                    if exists:
                        # Get file size
                        size = os.path.getsize(file_path)
                        print(f"     Size: {size} bytes")
            else:
                print(f"   ❌ No UPC found!")
        else:
            print(f"❌ Variant {variant_id} not found")
    
    # Also check what files actually exist in the directories
    print(f"\n🔍 Checking actual files in directories...")
    base_dir = "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow"
    
    for upc in ['657447102905', '657447102899']:
        upc_dir = os.path.join(base_dir, upc)
        if os.path.exists(upc_dir):
            print(f"\n📁 Directory {upc}:")
            files = os.listdir(upc_dir)
            for file in files:
                if file.endswith('.png'):
                    file_path = os.path.join(upc_dir, file)
                    size = os.path.getsize(file_path)
                    print(f"   - {file} ({size} bytes)")
        else:
            print(f"❌ Directory {upc} does not exist")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        test_api_endpoint()