#!/usr/bin/env python3
"""
Reorder product images for a set of UPCs so that the order is:
- Main image/photo first (also set as primary)
- 2nd image/photo second
- 3rd image/photo third
- Others follow in a stable order

Only touches the provided UPC list. Does not modify any other products.

Usage:
  python3 fix_image_sort_for_new_products.py
"""
import os
import re
from typing import List, Tuple

from app import app
from models import db, Product, ProductVariant, ProductImage

# UPCs to fix (from user's list)
UPCS = [
    "4049369016594",  # 83 Satisfyer — Booty Call 3 Piece
    "4061504003429",  # 84 Satisfyer — Top Secret Plus Vibrator (Pink)
    "4061504004181",  # 85 Satisfyer — Backdoor Lover Vibrating Anal Plug
    "848518016799",   # 86 XR Brands — Strap U Revolver II Strapless Vibrating Strap-On
    "848518037282",   # 87 XR Brands — Seducer Silicone Dildo & Harness Set
    "848518026095",   # 88 XR Brands — Navigator Silicone G-Spot Strap-On Set
    "844477015828",   # 89 Evolved — Trifecta Triple-Stimulation Vibrator
    "7707674738682",  # 90 DONA — Vibrator (Pink)
    "810080750012",   # 91 Sultry Wand Massager - Ruby
    "782421589202",   # 92 Doc Johnson — Red Boy Red Ringer Anal Wand
    "848518053886",   # 93 XR Brands — Pleasure Rose Petite Mini Silicone Rose Wand
    "6959532324136",  # 95 Pretty Love — Hyman G-Spot Vibrator
    "6959532312089",  # 96 Pretty Love — Felix 30-Function Rabbit Vibrator (Pink)
    "853858007222",   # 97 Blush — Performance VX5 Male Enhancement Pump System
    "196018782288",   # 98 Another Round 2pc Set S/M - Black
    "810080750050",   # 99 Viben — Razzle Thumping Rabbit (Ocean)
    "4061504036571",  # 100 Satisfyer — Hug Me Rabbit Vibrator (Grey/Blue)
]

# Patterns to detect image rank by filename
MAIN_PATTERNS = [r"main", r"main[_-]photo", r"main[_-]image"]
SECOND_PATTERNS = [r"2nd", r"second"]
THIRD_PATTERNS = [r"3rd", r"third"]
FOURTH_PATTERNS = [r"4th", r"fourth"]


def classify_rank(filename: str) -> int:
    """Return a rank for sorting based on name semantics.
    Lower rank appears earlier.
    """
    base = filename.lower()
    # helper to match any pattern
    def matches(patterns: List[str]) -> bool:
        return any(re.search(p, base, re.IGNORECASE) for p in patterns)

    if matches(MAIN_PATTERNS):
        return 0
    if matches(SECOND_PATTERNS):
        return 1
    if matches(THIRD_PATTERNS):
        return 2
    if matches(FOURTH_PATTERNS):
        return 3
    return 10  # default bucket after explicitly-ranked images


def reorder_images_for_variant(variant: ProductVariant) -> Tuple[int, int, bool]:
    """Reorder images for a given variant.
    Returns (updated_count, total_images, changed_flag).
    """
    images: List[ProductImage] = list(sorted(variant.images, key=lambda x: (x.sort_order, x.id)))
    if not images:
        return (0, 0, False)

    # Build sortable list with (rank, existing sort, filename, image)
    sortable = []
    for img in images:
        fname = os.path.basename(img.url)
        rank = classify_rank(fname)
        sortable.append((rank, img.sort_order if img.sort_order is not None else 9999, fname, img))

    # Sort by (rank, existing sort, filename)
    sortable.sort(key=lambda t: (t[0], t[1], t[2]))

    changed = False

    # Ensure only one primary and it's the first item
    for i, (_rank, _old_sort, _fname, img) in enumerate(sortable):
        desired_sort = i
        desired_primary = (i == 0)
        if img.sort_order != desired_sort:
            img.sort_order = desired_sort
            changed = True
        if bool(img.is_primary) != desired_primary:
            img.is_primary = desired_primary
            changed = True

    if changed:
        db.session.flush()

    return (sum(1 for _ in sortable), len(images), changed)


def fix_upcs():
    updated_products = 0
    updated_images = 0

    with app.app_context():
        for upc in UPCS:
            product = Product.query.filter_by(upc=str(upc)).first()
            if not product:
                print(f"⚠️  Skipping UPC {upc}: product not found")
                continue

            # Pick default variant (create none). Do NOT create new variants here; only fix existing.
            variant = product.default_variant
            if not variant:
                print(f"⚠️  Skipping {product.id} - {product.name} (UPC {upc}): no variant found")
                continue

            print(f"🔧 Fixing image order for Product {product.id} - {product.name} (UPC {upc}), Variant {variant.id}")
            _updated_count, _total, changed = reorder_images_for_variant(variant)
            if changed:
                updated_products += 1
                updated_images += _total

        try:
            db.session.commit()
            print(f"✅ Done. Updated products: {updated_products}, images touched: {updated_images}")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Commit failed: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        UPCS = [str(a) for a in sys.argv[1:]]
    fix_upcs()