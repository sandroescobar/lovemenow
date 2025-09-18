#!/usr/bin/env python3
"""
Check Du-Douche product variants and images
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DB_URL = os.getenv('DB_URL')
if not DB_URL:
    print("Error: DB_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

def check_du_douche():
    """Check Du-Douche product variants and images"""
    session = Session()
    
    try:
        # Find Du-Douche product
        result = session.execute(text("""
            SELECT p.id, p.name, p.upc
            FROM products p
            WHERE p.name LIKE '%Du%Douche%' OR p.upc = '860008092007'
        """))
        
        products = result.fetchall()
        
        for product in products:
            print(f"Product: {product.name} (ID: {product.id}, UPC: {product.upc})")
            
            # Get variants
            result = session.execute(text("""
                SELECT pv.id, pv.color_id, c.name as color_name, c.hex as color_hex
                FROM product_variants pv
                LEFT JOIN colors c ON pv.color_id = c.id
                WHERE pv.product_id = :product_id
                ORDER BY pv.id
            """), {'product_id': product.id})
            
            variants = result.fetchall()
            print(f"  Variants ({len(variants)}):")
            
            for variant in variants:
                print(f"    Variant {variant.id}: Color = {variant.color_name} ({variant.color_hex})")
                
                # Get images for this variant
                result = session.execute(text("""
                    SELECT pi.id, pi.url
                    FROM product_images pi
                    WHERE pi.product_variant_id = :variant_id
                    ORDER BY pi.id
                """), {'variant_id': variant.id})
                
                images = result.fetchall()
                print(f"      Images ({len(images)}):")
                for image in images:
                    print(f"        {image.url}")
                print()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_du_douche()