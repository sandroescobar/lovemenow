#!/usr/bin/env python3
"""
Fix duplicate ProductImage records for specific products
"""
import os
import sys
from dotenv import load_dotenv
from flask import Flask

# Load environment variables
load_dotenv()

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from routes import db
from models import Product, ProductVariant, ProductImage

# Create a simple Flask app for database access
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    # The two products with duplicate images
    target_upcs = ['853115004001', '796494106310']
    
    for upc in target_upcs:
        print(f"\n{'='*60}")
        print(f"Processing UPC: {upc}")
        print(f"{'='*60}")
        
        # Find the product by UPC
        product = Product.query.filter_by(upc=upc).first()
        if not product:
            print(f"❌ Product with UPC {upc} not found")
            continue
        
        print(f"✅ Found product: {product.name} (ID: {product.id})")
        
        # Get all variants for this product
        variants = ProductVariant.query.filter_by(product_id=product.id).all()
        print(f"   Variants for this product: {len(variants)}")
        
        for variant in variants:
            images = ProductImage.query.filter_by(product_variant_id=variant.id).all()
            print(f"\n   Variant ID {variant.id}: {len(images)} image(s)")
            
            # If more than one image, delete duplicates (keep first one)
            if len(images) > 1:
                print(f"   ⚠️  Found {len(images)} images - cleaning up...")
                
                # Sort by id to keep the first one
                images_sorted = sorted(images, key=lambda x: x.id)
                
                for i, img in enumerate(images_sorted):
                    if i == 0:
                        print(f"      [KEEP] ID {img.id}: {img.url}")
                    else:
                        print(f"      [DELETE] ID {img.id}: {img.url}")
                        db.session.delete(img)
            else:
                for img in images:
                    print(f"      ✅ ID {img.id}: {img.url}")
    
    # Commit all deletions
    print(f"\n{'='*60}")
    print("Committing changes to database...")
    db.session.commit()
    print("✅ Duplicate images removed successfully!")