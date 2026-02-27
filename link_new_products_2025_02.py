#!/usr/bin/env python3
"""
Migration: link images for new products added Feb 2025 (product IDs 196-213).
Run from Render shell: python link_new_products_2025_02.py
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from main import app
from models import db, Product, ProductVariant, ProductImage

PRODUCTS = [
    (196, '603912274561'),
    (197, '735380150174'),
    (198, '603912318913'),
    (199, '603912291223'),
    (200, '735380522063'),
    (201, '4890808063408'),
    (202, '603912746303'),
    (203, '603912746310'),
    (204, '844477011202'),
    (205, '844477016535'),
    (206, '819835024118'),
    (207, '8714273533654'),
    (208, '850052871208'),
    (209, '810124860882'),
    (210, '603912764352'),
    (212, '810124861933'),
    (213, '9356358000881'),
]

def run():
    with app.app_context():
        for product_id, upc in PRODUCTS:
            product = Product.query.get(product_id)
            if not product:
                print(f"❌ Product {product_id} not found — skipping")
                continue

            print(f"\n📦 {product.name} (id={product_id}, upc={upc})")

            variant = ProductVariant.query.filter_by(product_id=product_id).first()
            if not variant:
                variant = ProductVariant(product_id=product_id, variant_name='Default', upc=upc)
                db.session.add(variant)
                db.session.flush()
                print(f"  ✓ Created variant id={variant.id}")
            else:
                print(f"  → Using existing variant id={variant.id}")

            img_dir = os.path.join(BASE_DIR, 'static', 'IMG', 'imagesForLovMeNow', upc)
            if not os.path.isdir(img_dir):
                print(f"  ❌ Image folder not found: {img_dir}")
                continue

            image_files = sorted([
                f for f in os.listdir(img_dir)
                if f.lower().endswith(('.webp', '.png', '.jpg', '.jpeg'))
            ])

            if not image_files:
                print(f"  ❌ No images in folder")
                continue

            for idx, fname in enumerate(image_files):
                url = f'/static/IMG/imagesForLovMeNow/{upc}/{fname}'
                exists = ProductImage.query.filter_by(product_variant_id=variant.id, url=url).first()
                if exists:
                    print(f"  ⚠ Already linked: {fname}")
                    continue
                db.session.add(ProductImage(
                    product_variant_id=variant.id,
                    url=url,
                    is_primary=(idx == 0),
                    sort_order=idx,
                    alt_text=f"{product.name} - {fname}"
                ))
                print(f"  ✓ Linked: {fname} (primary={idx==0})")

        db.session.commit()
        print("\n✅ Done — all changes committed.")

if __name__ == '__main__':
    run()
