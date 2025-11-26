#!/usr/bin/env python3
"""
Clear legacy product.image_url for products that now have variant images
"""
import os
import sys
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from routes import db
from models import Product

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
        print(f"\nProcessing UPC: {upc}")
        
        product = Product.query.filter_by(upc=upc).first()
        if not product:
            print(f"❌ Product not found")
            continue
        
        print(f"✅ Product: {product.name}")
        print(f"   Current image_url: {product.image_url}")
        
        # Clear the legacy image_url
        product.image_url = None
        print(f"   Updated image_url: {product.image_url}")
    
    print(f"\n{'='*60}")
    print("Committing changes...")
    db.session.commit()
    print("✅ Legacy product images cleared successfully!")
    print("   Products will now use only variant images")