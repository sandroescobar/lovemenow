import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Database connection
DB_URL = os.getenv('DB_URL')
engine = create_engine(DB_URL)

# UPCs to check
UPCS = ['810124861230', '810124861186', '850000918283']
IMAGE_BASE_PATH = '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow'

print("=" * 80)
print("CHECKING NEW PRODUCTS")
print("=" * 80)

with engine.connect() as conn:
    for upc in UPCS:
        print(f"\n{'='*80}")
        print(f"UPC: {upc}")
        print(f"{'='*80}")
        
        # Check if product exists
        result = conn.execute(text("""
            SELECT id, name, image_url 
            FROM product 
            WHERE upc = :upc
        """), {"upc": upc})
        
        product = result.fetchone()
        
        if product:
            product_id, name, legacy_image = product
            print(f"✓ Product exists:")
            print(f"  - ID: {product_id}")
            print(f"  - Name: {name}")
            print(f"  - Legacy image_url: {legacy_image}")
            
            # Check for product images
            result = conn.execute(text("""
                SELECT pv.id, pv.variant_name, pi.image_url
                FROM product_image pi
                JOIN product_variant pv ON pi.variant_id = pv.id
                WHERE pv.product_id = :product_id
                ORDER BY pi.id
            """), {"product_id": product_id})
            
            images = result.fetchall()
            if images:
                print(f"✓ Product images found: {len(images)}")
                for var_id, var_name, img_url in images:
                    print(f"  - Variant: {var_name}, Image: {img_url}")
            else:
                print(f"✗ NO product images found!")
            
            # Check filesystem
            upc_path = os.path.join(IMAGE_BASE_PATH, upc)
            if os.path.exists(upc_path):
                files = os.listdir(upc_path)
                print(f"✓ Filesystem images found: {len(files)}")
                for f in sorted(files):
                    full_path = os.path.join(upc_path, f)
                    if os.path.isfile(full_path):
                        print(f"  - {f}")
            else:
                print(f"✗ NO filesystem images found at: {upc_path}")
        else:
            print(f"✗ Product NOT found in database!")
            
            # Check filesystem anyway
            upc_path = os.path.join(IMAGE_BASE_PATH, upc)
            if os.path.exists(upc_path):
                files = os.listdir(upc_path)
                print(f"⚠ Filesystem images exist but product not in DB: {len(files)} files")
                for f in sorted(files):
                    print(f"  - {f}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
