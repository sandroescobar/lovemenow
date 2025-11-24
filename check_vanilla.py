import os
from dotenv import load_dotenv

load_dotenv('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/.env')

import sys
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from app_factory import create_app
from models import ProductVariant, Product

app = create_app()
with app.app_context():
    # Find vanilla variant - search through all variants
    all_variants = ProductVariant.query.all()
    vanilla = None
    for v in all_variants:
        if v.color and 'vanilla' in v.color.name.lower():
            vanilla = v
            break
    
    if vanilla:
        print(f"✅ Found Vanilla Variant ID: {vanilla.id}")
        print(f"   in_stock: {vanilla.in_stock}")
        print(f"   quantity_on_hand: {vanilla.quantity_on_hand}")
        print(f"   is_available (calculated): {vanilla.is_available}")
        print(f"   Product '{vanilla.product.name}':")
        print(f"     in_stock: {vanilla.product.in_stock}")
        print(f"     quantity_on_hand: {vanilla.product.quantity_on_hand}")
    else:
        print("❌ No vanilla variant found. Listing all variants:")
        variants = ProductVariant.query.limit(10).all()
        for v in variants:
            color_name = v.color.name if v.color else 'No color'
            print(f"  ID {v.id}: {color_name} - in_stock: {v.in_stock}, qty: {v.quantity_on_hand}, available: {v.is_available}")
