#!/usr/bin/env python3
"""
Backfill products.features using the current heuristic from routes.main.process_product_details
- Only populate when products.features is NULL or empty
- Stores up to 4 bullets separated by newlines
"""
import sys
import os

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from routes import db
from models import Product

# Import the existing processing function
from routes.main import process_product_details


def backfill_features():
    updated = 0
    skipped = 0
    with app.app_context():
        products = Product.query.all()
        for p in products:
            try:
                if p.features and p.features.strip():
                    skipped += 1
                    continue
                # Use existing logic to compute features/specs/dims
                features, specs, dims = process_product_details(p)
                if features:
                    # Normalize to at most 4 bullets, newline-joined
                    cleaned = [str(f).strip() for f in features if str(f).strip()]
                    p.features = "\n".join(cleaned[:4])
                    updated += 1
            except Exception as e:
                # Soft-fail per item, continue
                print(f"Warning: failed to process product {p.id}: {e}")
        db.session.commit()
    print(f"✅ Backfill complete. Updated: {updated}, Skipped: {skipped}")


if __name__ == "__main__":
    print("Starting features backfill...")
    backfill_features()