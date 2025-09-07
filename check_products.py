#!/usr/bin/env python3
"""
Script to check what products exist in the database and their identifiers
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

def check_products():
    """Check what products exist in the database"""
    app = create_flask_app()
    
    with app.app_context():
        print("=== PRODUCTS IN DATABASE ===")
        products = Product.query.all()
        print(f"Total products: {len(products)}")
        
        print("\n=== PRODUCT DETAILS ===")
        for product in products:
            print(f"ID: {product.id}")
            print(f"Name: {product.name}")
            print(f"UPC: {product.upc}")
            print(f"Base UPC: {product.base_upc}")
            print(f"Wholesale ID: {product.wholesale_id}")
            print(f"Variants: {len(product.variants)}")
            
            # Check images for each variant
            for variant in product.variants:
                images = ProductImage.query.filter_by(product_variant_id=variant.id).all()
                print(f"  Variant {variant.id}: {len(images)} images")
            
            print("-" * 50)
        
        print("\n=== IMAGE STATISTICS ===")
        total_images = ProductImage.query.count()
        print(f"Total images in database: {total_images}")
        
        # Check for variants with no images
        variants_without_images = []
        for product in products:
            for variant in product.variants:
                images = ProductImage.query.filter_by(product_variant_id=variant.id).all()
                if len(images) == 0:
                    variants_without_images.append((product, variant))
        
        print(f"Variants without images: {len(variants_without_images)}")
        for product, variant in variants_without_images:
            print(f"  - {product.name} (Variant ID: {variant.id})")

if __name__ == "__main__":
    check_products()