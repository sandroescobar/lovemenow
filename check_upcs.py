#!/usr/bin/env python
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from routes import db
from models import ProductVariant, Product

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    # Check for variants with these UPCs
    variant1 = ProductVariant.query.filter_by(upc='853115004001').first()
    variant2 = ProductVariant.query.filter_by(upc='796494106310').first()
    
    print("Checking ProductVariant UPCs:")
    print(f"  853115004001: {variant1}")
    print(f"  796494106310: {variant2}")
    
    # Check if they're in Product.upc
    prod1 = Product.query.filter_by(upc='853115004001').first()
    prod2 = Product.query.filter_by(upc='796494106310').first()
    
    print("\nChecking Product UPCs:")
    print(f"  853115004001: {prod1}")
    print(f"  796494106310: {prod2}")
    
    # Check base_upc
    prod1_base = Product.query.filter_by(base_upc='853115004001').first()
    prod2_base = Product.query.filter_by(base_upc='796494106310').first()
    
    print("\nChecking Product base_upc:")
    print(f"  853115004001: {prod1_base}")
    print(f"  796494106310: {prod2_base}")