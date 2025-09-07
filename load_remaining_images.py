#!/usr/bin/env python3
"""
Script to load remaining product images into the database.
Only loads images for products that have UPC directories but no images in DB.
"""

import os
from main import app, db
from models import Product, ProductVariant, ProductImage, Color

def load_remaining_images():
    with app.app_context():
        print("=== LOADING REMAINING PRODUCT IMAGES ===")
        
        # Get products without images
        products_no_imgs = (Product.query
                           .outerjoin(ProductVariant)
                           .outerjoin(ProductImage)
                           .filter(ProductImage.id == None)
                           .all())
        
        # Get available UPC directories
        img_dir = 'static/IMG/imagesForLovMeNow'
        upc_dirs = [d for d in os.listdir(img_dir) if os.path.isdir(os.path.join(img_dir, d))]
        
        loaded_count = 0
        
        for product in products_no_imgs:
            product_upc = str(product.upc) if product.upc else None
            
            if product_upc and product_upc in upc_dirs:
                print(f"\n🔄 Processing: {product.name}")
                print(f"   UPC: {product_upc}")
                
                # Get image files
                dir_path = os.path.join(img_dir, product_upc)
                image_files = [f for f in os.listdir(dir_path) 
                              if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                
                if not image_files:
                    print(f"   ❌ No image files found in {product_upc}")
                    continue
                
                # Check if product has a variant
                variant = ProductVariant.query.filter_by(product_id=product.id).first()
                
                if not variant:
                    print(f"   📦 Creating variant for product...")
                    # Create a default variant
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=f"{product.upc}_DEFAULT",
                        price=product.price,
                        quantity_on_hand=product.quantity_on_hand,
                        color_id=None  # No specific color
                    )
                    db.session.add(variant)
                    db.session.flush()  # Get the variant ID
                
                # Load images
                print(f"   📸 Loading {len(image_files)} images...")
                for i, image_file in enumerate(sorted(image_files)):
                    image_url = f"/static/IMG/imagesForLovMeNow/{product_upc}/{image_file}"
                    
                    # Check if image already exists
                    existing_image = ProductImage.query.filter_by(
                        product_variant_id=variant.id,
                        url=image_url
                    ).first()
                    
                    if not existing_image:
                        product_image = ProductImage(
                            product_variant_id=variant.id,
                            url=image_url,
                            sort_order=i
                        )
                        db.session.add(product_image)
                        print(f"      ✅ Added: {image_file}")
                    else:
                        print(f"      ⏭️  Skipped (exists): {image_file}")
                
                loaded_count += 1
                
                try:
                    db.session.commit()
                    print(f"   ✅ Successfully loaded images for {product.name}")
                except Exception as e:
                    db.session.rollback()
                    print(f"   ❌ Error loading images for {product.name}: {e}")
            else:
                print(f"\n⏭️  Skipping: {product.name} (UPC: {product_upc}) - No image directory")
        
        print(f"\n🎉 COMPLETED!")
        print(f"   Processed {loaded_count} products")
        
        # Final status check
        total_products = Product.query.count()
        products_with_images = (Product.query
                              .join(ProductVariant)
                              .join(ProductImage)
                              .distinct()
                              .count())
        
        print(f"\n📊 FINAL STATUS:")
        print(f"   Total products: {total_products}")
        print(f"   Products with images: {products_with_images}")
        print(f"   Coverage: {(products_with_images/total_products*100):.1f}%")

if __name__ == "__main__":
    load_remaining_images()