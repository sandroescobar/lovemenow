#!/usr/bin/env python
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from routes import db
from models import Product
from sqlalchemy.orm import joinedload

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    products = Product.query.filter(Product.upc.in_(['853115004001', '796494106310'])).options(
        joinedload(Product.variants)
    ).all()
    
    for prod in products:
        print(f"\nProduct {prod.id}: {prod.name}")
        print(f"  UPC: {prod.upc}")
        print(f"  Base UPC: {prod.base_upc}")
        print(f"  Variants: {len(prod.variants)}")
        for variant in prod.variants:
            print(f"    - Variant {variant.id}: {variant.display_name} (UPC: {variant.upc})")
        print(f"  Has images: {len(prod.all_image_urls)} images")