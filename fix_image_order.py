import os
import sys

# Add the project root to the path
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from main import app, db
from models import Product, ProductImage

# UPCs to fix
UPCS = ['4251460612258', '603912349993', '819835022473', '819835027133']

def fix_image_order(upc):
    """Delete and relink images in correct order"""
    with app.app_context():
        print(f"\nFixing image order for UPC: {upc}")
        
        # Find product by UPC
        product = Product.query.filter_by(upc=upc).first()
        
        if not product:
            print(f"  ❌ Product not found")
            return
        
        # Get all variants for this product
        for variant in product.variants:
            # Delete all existing images for this variant
            images_to_delete = ProductImage.query.filter_by(product_variant_id=variant.id).all()
            if images_to_delete:
                print(f"  Deleting {len(images_to_delete)} existing image(s)...")
                for img in images_to_delete:
                    db.session.delete(img)
                db.session.commit()
                print(f"  ✅ Deleted old images")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("CLEARING OLD IMAGES")
    print("="*60)
    
    for upc in UPCS:
        fix_image_order(upc)
    
    print("\n" + "="*60)
    print("Now running image linking with correct order...")
    print("="*60 + "\n")
    
    # Now run the linking script
    import link_four_more