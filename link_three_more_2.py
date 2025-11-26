import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from main import app, db
from models import Product, ProductVariant, ProductImage

# UPCs to process
UPCS = ['810124860103', '8714273491473', '847841024020']

def link_images_for_product(upc):
    """Link images from filesystem to product in database"""
    with app.app_context():
        print(f"\n{'='*60}")
        print(f"Processing UPC: {upc}")
        print('='*60)
        
        # Find product by UPC
        product = Product.query.filter_by(upc=upc).first()
        
        if not product:
            print(f"❌ Product with UPC {upc} not found in database")
            return False
        
        print(f"✅ Found product: {product.name}")
        
        # Check if variant exists, if not create default
        variant = ProductVariant.query.filter_by(product_id=product.id).first()
        
        if not variant:
            print("   Creating default variant...")
            variant = ProductVariant(
                product_id=product.id,
                variant_name="Default"
            )
            db.session.add(variant)
            db.session.commit()
            print(f"   ✅ Default variant created")
        else:
            print(f"   ✅ Using existing variant: {variant.variant_name}")
        
        # Check for images in filesystem
        image_dir = Path(f'/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow/{upc}')
        
        if not image_dir.exists():
            print(f"⚠️  No image directory found at: {image_dir}")
            return False
        
        # Get all image files (jpg, png, webp)
        image_files = sorted([f for f in image_dir.iterdir() 
                             if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']])
        
        if not image_files:
            print(f"⚠️  No image files found in directory")
            return False
        
        print(f"✅ Found {len(image_files)} image(s)")
        
        # Determine image names and sort order
        image_names = ['main', '2nd', '3rd', '4th', '5th']
        
        for idx, image_file in enumerate(image_files):
            image_name = image_names[idx] if idx < len(image_names) else f'img_{idx}'
            image_url = f'/static/IMG/imagesForLovMeNow/{upc}/{image_file.name}'
            
            # Check if image already exists
            existing_image = ProductImage.query.filter_by(
                product_variant_id=variant.id,
                url=image_url
            ).first()
            
            if existing_image:
                print(f"   ⚠️  Image already linked: {image_name} ({image_file.name})")
                continue
            
            # Create new ProductImage record
            product_image = ProductImage(
                product_variant_id=variant.id,
                url=image_url,
                is_primary=(idx == 0),  # First image is primary
                sort_order=idx
            )
            db.session.add(product_image)
            print(f"   ✅ Linked {image_name}: {image_file.name}")
        
        # Commit all changes
        db.session.commit()
        print(f"\n✅ Successfully processed UPC {upc}")
        return True

if __name__ == '__main__':
    print("\n" + "="*60)
    print("LINKING IMAGES FOR THREE PRODUCTS")
    print("="*60)
    
    results = {}
    for upc in UPCS:
        results[upc] = link_images_for_product(upc)
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for upc, success in results.items():
        status = "✅ Complete" if success else "⚠️  Incomplete"
        print(f"{upc}: {status}")
    print("="*60 + "\n")