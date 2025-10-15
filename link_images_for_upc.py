#!/usr/bin/env python3
"""
Link images for a specific product UPC by creating a default variant (if needed)
and attaching all images from the provided UPC folder.

- Only touches the given product and its images
- Idempotent: skips already-linked images
- Sets the first suitable image as primary

Usage:
  python link_images_for_upc.py 782421589202
"""
import os
import sys
import re
from glob import glob

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Product, ProductVariant, ProductImage

STATIC_ROOT = "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static"
IMAGES_BASE = os.path.join(STATIC_ROOT, "IMG", "imagesForLovMeNow")

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif", "JPG", "JPEG", "PNG", "WEBP", "GIF"}


def pick_primary(files):
    """Pick a primary image: prefer filenames containing 'main' then fallback to first sorted."""
    if not files:
        return None
    # Prefer files that contain 'main' (case-insensitive)
    for f in files:
        name = os.path.basename(f)
        if re.search(r"main", name, re.IGNORECASE):
            return f
    return files[0]


def collect_images(folder):
    """Collect all image files in folder (allowed extensions) sorted by name."""
    if not os.path.isdir(folder):
        return []
    files = []
    for ext in ALLOWED_EXT:
        files.extend(glob(os.path.join(folder, f"*.{ext}")))
    files = sorted(set(files), key=lambda p: os.path.basename(p))
    return files


def ensure_variant(product):
    """Ensure there is at least one variant for the product, create a default if missing."""
    if product.variants:
        return product.variants[0]
    variant = ProductVariant(product_id=product.id, upc=product.upc, variant_name=None)
    db.session.add(variant)
    db.session.flush()  # get ID without full commit
    return variant


def link_images_for_upc(upc):
    upc = str(upc).strip()
    folder = os.path.join(IMAGES_BASE, upc)

    with app.app_context():
        product = Product.query.filter_by(upc=upc).first()
        if not product:
            print(f"❌ No product found with UPC {upc}")
            return 1

        print(f"📦 Product: {product.id} - {product.name} (UPC {upc})")
        files = collect_images(folder)
        if not files:
            print(f"⚠️ No image files found in {folder}")
            return 2

        variant = ensure_variant(product)
        print(f"🧩 Using variant ID: {variant.id}")

        # Choose primary and set sort order
        primary_file = pick_primary(files)
        added = 0
        skipped = 0
        sort_order = 0
        for fpath in files:
            # Compute relative URL from /static
            if not fpath.startswith(STATIC_ROOT + os.sep):
                print(f"⚠️ Skipping non-static file: {fpath}")
                continue
            rel_url = fpath.replace(STATIC_ROOT + os.sep, "")

            # Check if already exists
            existing = ProductImage.query.filter_by(product_variant_id=variant.id, url=rel_url).first()
            if existing:
                skipped += 1
                continue

            is_primary = (fpath == primary_file)
            img = ProductImage(
                product_variant_id=variant.id,
                url=rel_url,
                is_primary=is_primary,
                sort_order=sort_order,
                alt_text=f"{product.name} - {os.path.basename(fpath)}",
            )
            db.session.add(img)
            added += 1
            sort_order += 1

        try:
            db.session.commit()
            print(f"✅ Linked images for UPC {upc}. Added: {added}, Skipped existing: {skipped}")
            return 0
        except Exception as e:
            db.session.rollback()
            print(f"❌ DB commit failed: {e}")
            return 3


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python link_images_for_upc.py <UPC>")
        sys.exit(1)
    sys.exit(link_images_for_upc(sys.argv[1]))