#!/usr/bin/env python3
"""
Diagnose why products are showing duplicate images
"""
import os
import sys
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from routes import db
from models import Product, ProductVariant, ProductImage

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    target_upcs = ['853115004001', '796494106310']
    
    for upc in target_upcs:
        print(f"\n{'='*80}")
        print(f"UPC: {upc}")
        print(f"{'='*80}")
        
        product = Product.query.filter_by(upc=upc).first()
        if not product:
            print(f"❌ Product not found")
            continue
        
        print(f"Product Name: {product.name}")
        print(f"Product ID: {product.id}")
        print(f"Product.image_url: {product.image_url}")  # <-- This could be the issue!
        print(f"Number of variants: {len(product.variants)}")
        
        for variant in product.variants:
            print(f"\n  Variant ID: {variant.id}")
            print(f"  Variant Name: {variant.variant_name}")
            print(f"  Number of images: {len(variant.images)}")
            for img in variant.images:
                print(f"    - Image ID {img.id}: {img.url} (primary={img.is_primary}, sort={img.sort_order})")
        
        print(f"\nProperty: all_image_urls = {product.all_image_urls}")
        print(f"Property: main_image_url = {product.main_image_url}")