#!/usr/bin/env python3
"""Update product images in DB for UPC: 657447098000"""

import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from routes import db
from models import ProductVariant, ProductImage, Product

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DB_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    # Find product by UPC
    product = db.session.query(Product).filter_by(upc='657447098000').first()
    if not product:
        print("❌ Product not found with UPC 657447098000")
        exit(1)
    
    print(f"✅ Found product: {product.name} (ID: {product.id})")
    
    # Find variant(s) for this product
    variants = db.session.query(ProductVariant).filter_by(product_id=product.id).all()
    if not variants:
        print("❌ No variants found for this product")
        exit(1)
    
    print(f"✅ Found {len(variants)} variant(s)")
    
    for variant in variants:
        print(f"\n  Variant: {variant.variant_name or 'N/A'} (ID: {variant.id})")
        
        # Delete old images for this variant
        old_images = db.session.query(ProductImage).filter_by(product_variant_id=variant.id).all()
        if old_images:
            print(f"  🗑️  Deleting {len(old_images)} old image(s)...")
            for img in old_images:
                db.session.delete(img)
        
        # Add new images
        new_images = [
            {
                'url': '/static/IMG/imagesForLovMeNow/657447098000/657447098000_Main_Image.webp',
                'is_primary': True,
                'sort_order': 0,
                'alt_text': f"{product.name} - Main Image"
            },
            {
                'url': '/static/IMG/imagesForLovMeNow/657447098000/657447098000_2nd_Image.webp',
                'is_primary': False,
                'sort_order': 1,
                'alt_text': f"{product.name} - Secondary Image"
            }
        ]
        
        print(f"  ✨ Adding {len(new_images)} new image(s)...")
        for img_data in new_images:
            new_img = ProductImage(
                product_variant_id=variant.id,
                url=img_data['url'],
                is_primary=img_data['is_primary'],
                sort_order=img_data['sort_order'],
                alt_text=img_data['alt_text']
            )
            db.session.add(new_img)
            print(f"     • {img_data['url']}")
    
    # Commit changes
    db.session.commit()
    print("\n✅ Database updated successfully!")
    print("🎉 New images will now appear on the product page")