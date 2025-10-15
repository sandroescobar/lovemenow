#!/usr/bin/env python3
"""
Backfill script: create missing variants and import images for specific new products by UPC.
- Does NOT touch other products.
- Mirrors the image patterns used in import_images.py.

Usage:
  python backfill_new_products_images.py
"""
import os
import glob
from datetime import datetime

from app import app
from models import db, Product, ProductVariant, ProductImage

# IMPORTANT: Update this list if you want to add/remove UPCs.
UPCS_TO_PROCESS = [
    # Satisfyer — Booty Call 3 Piece
    "4049369016594",
    # Satisfyer — Top Secret Plus Vibrator (Pink)
    "4061504003429",
    # Satisfyer — Backdoor Lover Vibrating Anal Plug (Black)
    "4061504004181",
    # XR Brands — Strap U Revolver II Strapless Vibrating Strap-On (Blue)
    "848518016799",
    # XR Brands — Seducer Silicone Dildo & Harness Set
    "848518037282",
    # XR Brands — Navigator Silicone G-Spot Strap-On Set
    "848518026095",
    # Evolved — Trifecta Triple-Stimulation Vibrator
    "844477015828",
    # DONA — Vibrator (Pink)
    "7707674738682",
    # Sliquid — H2O? (example) — Ensuring this UPC is processed
    "810080750012",
    # NOTE: "Sultry Wand Massager - Ruby" UPC not provided. Add here when available.
]

IMAGES_BASE_PATH = "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow"

# Patterns used to discover images
IMAGE_PATTERNS = [
    "{upc}_Main_Photo.*",
    "{upc}_Main_Image.*",
    "{upc}_2nd_Photo.*",
    "{upc}_2nd_Image.*",
    "{upc}_3rd_Photo.*",
    "{upc}_3rd_Image.*",
    "{upc}_4th_Photo.*",
    "{upc}_4th_Image.*",
    "{upc}_5th_Photo.*",
    "{upc}_5th_Image.*",
]


def determine_sort_and_primary(filename: str):
    """Return (sort_order, is_primary) based on filename semantics."""
    name = filename.lower()
    if "main" in name:
        return 0, True
    # Map ordinal hints to sort
    for idx, key in enumerate(["2nd", "3rd", "4th", "5th"], start=1):
        if key.lower() in name:
            return idx, False
    return 99, False  # fallback if naming differs


def ensure_variant_for_product(product: Product) -> ProductVariant:
    """Return a variant for this product, creating one if missing.
    Uses product.upc for the new variant's UPC when available.
    """
    existing = ProductVariant.query.filter_by(product_id=product.id).first()
    if existing:
        return existing
    new_variant = ProductVariant(
        product_id=product.id,
        color_id=None,
        variant_name=None,
        upc=product.upc,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(new_variant)
    db.session.flush()  # get id without full commit
    print(f"   ➕ Created variant {new_variant.id} for product '{product.name}' (UPC {product.upc})")
    return new_variant


def import_images_for_upc(upc: str):
    folder_path = os.path.join(IMAGES_BASE_PATH, upc)
    if not os.path.isdir(folder_path):
        print(f"⚠️  Folder not found for UPC {upc}: {folder_path}")
        return 0

    product = Product.query.filter_by(upc=upc).first()
    if not product:
        print(f"⚠️  No product found with UPC {upc}. Skipping.")
        return 0

    # Ensure a variant exists (create if needed)
    variant = ensure_variant_for_product(product)

    # Collect images by patterns
    found_images = []
    for pattern in IMAGE_PATTERNS:
        glob_pattern = os.path.join(folder_path, pattern.format(upc=upc))
        found_images.extend(glob.glob(glob_pattern))

    if not found_images:
        # Fallback only for the specific UPC that has PNGs not following the usual naming
        if upc == "810080750012":
            fallback_images = []
            # Look for any PNGs (case-insensitive)
            for patt in ["*.png", "*.PNG"]:
                fallback_images.extend(glob.glob(os.path.join(folder_path, patt)))

            # Stable order
            fallback_images.sort()

            if fallback_images:
                images_added = 0
                for idx, abs_path in enumerate(fallback_images):
                    # Store path relative to /static/
                    relative_path = abs_path.replace(
                        "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/", ""
                    )

                    # Skip if already present
                    existing = ProductImage.query.filter_by(
                        product_variant_id=variant.id,
                        url=relative_path,
                    ).first()
                    if existing:
                        print(f"   ⏭️  Exists: {os.path.basename(abs_path)}")
                        continue

                    # First image is primary, maintain index as sort order
                    img = ProductImage(
                        product_variant_id=variant.id,
                        url=relative_path,
                        is_primary=(idx == 0),
                        sort_order=idx,
                        alt_text=f"{product.name} - {os.path.basename(abs_path)}",
                    )
                    db.session.add(img)
                    # Ensure grid fallback works immediately: set product.image_url to first imported image if empty
                    if not product.image_url and idx == 0:
                        product.image_url = relative_path
                    images_added += 1
                    print(f"   ✅ Added (fallback): {os.path.basename(abs_path)} (primary={idx == 0}, sort={idx})")

                return images_added

        print(f"   No images found in {folder_path}")
        return 0

    # Sort for stable order
    found_images.sort()

    images_added = 0
    for abs_path in found_images:
        # Store path relative to /static/ for consistency with existing code
        relative_path = abs_path.replace(
            "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/", ""
        )

        # Skip if already present
        existing = ProductImage.query.filter_by(
            product_variant_id=variant.id,
            url=relative_path,
        ).first()
        if existing:
            print(f"   ⏭️  Exists: {os.path.basename(abs_path)}")
            continue

        sort_order, is_primary = determine_sort_and_primary(os.path.basename(abs_path))
        img = ProductImage(
            product_variant_id=variant.id,
            url=relative_path,
            is_primary=is_primary,
            sort_order=sort_order,
            alt_text=f"{product.name} - {os.path.basename(abs_path)}",
        )
        db.session.add(img)
        # Ensure grid fallback works: if product.image_url is empty and this is primary, set it
        if not product.image_url and is_primary:
            product.image_url = relative_path
        images_added += 1
        print(f"   ✅ Added: {os.path.basename(abs_path)} (primary={is_primary}, sort={sort_order})")

    return images_added


def main():
    with app.app_context():
        print(f"Processing {len(UPCS_TO_PROCESS)} UPCs…")
        total = 0
        for upc in UPCS_TO_PROCESS:
            print(f"\n📦 UPC {upc}")
            try:
                added = import_images_for_upc(upc)
                total += added
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Error for UPC {upc}: {e}")
        try:
            db.session.commit()
            print(f"\n🎉 Done. Added {total} images total.")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Commit failed: {e}")


if __name__ == "__main__":
    main()