#!/usr/bin/env python3
"""
Script to check what images exist for a specific product
"""

import os
from dotenv import load_dotenv
from flask import Flask
from models import db, Product, ProductVariant, ProductImage

# Load environment variables
load_dotenv()

def create_flask_app():
    """Create Flask app similar to main.py"""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DB_URL",
        "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize extensions
    from routes import bcrypt, login_mgr
    db.init_app(app)
    bcrypt.init_app(app)
    login_mgr.init_app(app)
    
    return app

def check_images():
    """Check what images exist for the first product"""
    app = create_flask_app()
    
    with app.app_context():
        # Get the first product
        product = Product.query.first()
        if not product:
            print("No products found")
            return
        
        print(f"=== IMAGES FOR PRODUCT: {product.name} ===")
        print(f"UPC: {product.upc}")
        print(f"Wholesale ID: {product.wholesale_id}")
        
        for variant in product.variants:
            print(f"\n--- Variant {variant.id} ---")
            images = ProductImage.query.filter_by(product_variant_id=variant.id).all()
            print(f"Total images: {len(images)}")
            
            for i, img in enumerate(images[:10]):  # Show first 10 images
                print(f"  {i+1}. URL: {img.url}")
                print(f"     Primary: {img.is_primary}")
                print(f"     Sort Order: {img.sort_order}")
                print(f"     Alt Text: {img.alt_text}")
                print()
            
            if len(images) > 10:
                print(f"  ... and {len(images) - 10} more images")

if __name__ == "__main__":
    check_images()