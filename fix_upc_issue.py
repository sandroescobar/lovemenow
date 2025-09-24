#!/usr/bin/env python3
"""
Fix UPC issue for products 657447102905 and 657447102899
The variants need to have their UPC values set to match the product UPCs
"""

from app import create_app
from models import Product, ProductVariant, db

def fix_upc_issue():
    """Fix the UPC values for the specific variants"""
    
    # Target UPCs
    target_upcs = ['657447102905', '657447102899']
    
    print("🔧 Fixing UPC issue for variants...")
    
    for upc in target_upcs:
        # Find the product by UPC
        product = Product.query.filter_by(upc=upc).first()
        
        if product:
            print(f"\n✅ Found product with UPC {upc}:")
            print(f"   ID: {product.id}")
            print(f"   Name: {product.name}")
            print(f"   Variants: {len(product.variants)}")
            
            # Update all variants for this product to have the correct UPC
            for variant in product.variants:
                print(f"   - Variant ID: {variant.id}, Current UPC: {variant.upc}")
                
                if variant.upc != upc:
                    print(f"     🔄 Updating variant UPC from {variant.upc} to {upc}")
                    variant.upc = upc
                else:
                    print(f"     ✅ Variant UPC already correct")
        else:
            print(f"❌ No product found with UPC {upc}")
    
    # Commit the changes
    try:
        db.session.commit()
        print("\n✅ Successfully updated variant UPCs!")
        
        # Verify the changes
        print("\n🔍 Verifying changes...")
        for upc in target_upcs:
            product = Product.query.filter_by(upc=upc).first()
            if product:
                for variant in product.variants:
                    print(f"   Product {product.name} - Variant {variant.id}: UPC = {variant.upc}")
                    
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating UPCs: {str(e)}")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        fix_upc_issue()