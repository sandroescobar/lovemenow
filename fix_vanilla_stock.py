import os
from dotenv import load_dotenv
load_dotenv('/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/.env')

import sys
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from main import app, db
from models import ProductVariant

with app.app_context():
    # Find ALL vanilla variants and fix them
    vanilla_variants = ProductVariant.query.filter(
        ProductVariant.color.has(name='Vanilla')
    ).all()
    
    if vanilla_variants:
        for v in vanilla_variants:
            print(f"\nBefore: Vanilla variant {v.id}")
            print(f"  in_stock: {v.in_stock}")
            print(f"  quantity_on_hand: {v.quantity_on_hand}")
            print(f"  is_available: {v.is_available}")
            
            # Fix it
            v.in_stock = True
            if v.quantity_on_hand is None or v.quantity_on_hand <= 0:
                v.quantity_on_hand = 100  # Set reasonable stock
            
            print(f"After: Vanilla variant {v.id}")
            print(f"  in_stock: {v.in_stock}")
            print(f"  quantity_on_hand: {v.quantity_on_hand}")
            print(f"  is_available: {v.is_available}")
        
        db.session.commit()
        print("\n✅ Fixed all vanilla variants!")
    else:
        print("❌ No vanilla variants found")
