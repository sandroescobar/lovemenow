# imageConverter.py
from pathlib import Path
from rembg import remove
from PIL import Image
import argparse
import re

IMG_PAT = re.compile(r".+\.(jpe?g|png|webp)$", re.I)

def to_alpha(src: Path, dst: Path):
    im = Image.open(src).convert("RGBA")
    cut = remove(
        im,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_structure_size=10,
        alpha_matting_base_size=1000,
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    cut.save(dst, format="WEBP", lossless=True)

def process_dir(src_root: Path):
    if not src_root.exists():
        raise FileNotFoundError(f"Source folder not found: {src_root}")

    count = 0
    for upc_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
        for p in upc_dir.iterdir():
            if not IMG_PAT.match(p.name):
                continue
            # write next to original: <stem>__alpha.webp
            dst = p.with_suffix("").with_name(p.stem + "__alpha").with_suffix(".webp")
            if dst.exists():
                continue
            try:
                to_alpha(p, dst)
                print("✓", dst.relative_to(src_root))
                count += 1
            except Exception as e:
                print("skip:", p, "-", e)
    print(f"\nDone. Newly created alpha images: {count}")

def main():
    ap = argparse.ArgumentParser(description="Create transparent __alpha.webp images for product photos.")
    ap.add_argument(
        "--src",
        default=None,
        help="Path to images root (folder that contains UPC subfolders). "
             "If omitted, defaults to ./static/IMG/imagesForLovMeNow relative to this script."
    )
    args = ap.parse_args()

    if args.src:
        src_root = Path(args.src).expanduser().resolve()
    else:
        # default: ./static/IMG/imagesForLovMeNow (relative to this file)
        src_root = (Path(__file__).resolve().parent / "static" / "IMG" / "imagesForLovMeNow").resolve()

    print("Using source:", src_root)
    process_dir(src_root)

if __name__ == "__main__":
    main()
