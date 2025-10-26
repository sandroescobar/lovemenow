#!/usr/bin/env python3
"""
Create __alpha.webp versions next to existing images using Pillow only (no background removal).
Outputs files like <stem>__alpha.webp in the same folder.
"""
from pathlib import Path
from PIL import Image
import os

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"}

BASE_DIR = Path("/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow")


def convert_to_webp(src: Path, dst: Path):
    # Convert and save as WebP (lossy, quality 80) retaining alpha if present
    im = Image.open(src)
    # Ensure RGB(A) mode for WebP
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, format="WEBP", quality=80, method=6)


def main():
    if not BASE_DIR.exists():
        raise SystemExit(f"Base directory not found: {BASE_DIR}")

    created = 0
    skipped = 0
    failed = 0

    for upc_dir in sorted(p for p in BASE_DIR.iterdir() if p.is_dir()):
        for p in upc_dir.iterdir():
            if p.suffix not in IMAGE_EXTS:
                continue
            # Skip already-generated alpha files
            if p.name.endswith("__alpha.webp"):
                continue
            dst = p.with_suffix("").with_name(p.stem + "__alpha").with_suffix(".webp")
            if dst.exists():
                skipped += 1
                continue
            try:
                convert_to_webp(p, dst)
                print(f"✓ {dst.relative_to(BASE_DIR)}")
                created += 1
            except Exception as e:
                print(f"skip: {p} - {e}")
                failed += 1

    print(f"\nDone. Newly created __alpha.webp images: {created}, skipped existing: {skipped}, failed: {failed}")


if __name__ == "__main__":
    main()