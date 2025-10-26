#!/usr/bin/env python3
"""
Detect and fix WebP files that have white backgrounds.
- Checks for predominantly white backgrounds in WebP files
- Recreates problematic WebP files from PNG/JPG sources
"""
from pathlib import Path
from PIL import Image
import numpy as np

BASE_DIR = Path("/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow/static/IMG/imagesForLovMeNow")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".PNG", ".JPG", ".JPEG"}


def detect_white_background(image_path):
    """
    Check if an image has a predominantly white background.
    Returns True if it appears to have a white background.
    """
    try:
        img = Image.open(image_path)
        
        # Skip if already has alpha channel (transparency)
        if img.mode == "RGBA":
            # Check if there are transparent pixels
            if img.mode == "RGBA":
                alpha = np.array(img.split()[-1])
                if np.any(alpha < 200):  # Has significant transparency
                    return False
        
        # Convert to RGB for analysis
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Convert to numpy array
        arr = np.array(img)
        
        # Get corner pixels (likely to represent background)
        h, w = arr.shape[:2]
        corners = [
            arr[0:10, 0:10],  # top-left
            arr[0:10, w-10:w],  # top-right
            arr[h-10:h, 0:10],  # bottom-left
            arr[h-10:h, w-10:w]  # bottom-right
        ]
        
        # Check if corners are predominantly white (> 240 brightness)
        white_count = 0
        total_pixels = 0
        
        for corner in corners:
            # Calculate brightness (average of RGB)
            brightness = np.mean(corner, axis=2)
            white_pixels = np.sum(brightness > 240)
            white_count += white_pixels
            total_pixels += corner.size // 3
        
        white_ratio = white_count / total_pixels if total_pixels > 0 else 0
        return white_ratio > 0.7  # If >70% of corners are white
        
    except Exception as e:
        print(f"Error analyzing {image_path}: {e}")
        return False


def find_source_image(webp_path):
    """Find the original PNG/JPG file for a WebP file."""
    parent = webp_path.parent
    stem = webp_path.stem.replace("__alpha", "")
    
    for ext in IMAGE_EXTS:
        source = parent / (stem + ext)
        if source.exists():
            return source
    
    return None


def convert_to_webp_proper(src: Path, dst: Path):
    """
    Convert image to WebP, preserving transparency properly.
    """
    try:
        img = Image.open(src)
        
        # Convert to RGBA to preserve transparency
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        img.save(dst, format="WEBP", quality=80, method=6)
        return True
    except Exception as e:
        print(f"Error converting {src}: {e}")
        return False


def main():
    if not BASE_DIR.exists():
        raise SystemExit(f"Base directory not found: {BASE_DIR}")
    
    print("🔍 Scanning for WebP files with white backgrounds...\n")
    
    problematic_files = []
    checked = 0
    
    for upc_dir in sorted(p for p in BASE_DIR.iterdir() if p.is_dir()):
        for webp_file in upc_dir.glob("*__alpha.webp"):
            checked += 1
            
            if detect_white_background(webp_file):
                problematic_files.append(webp_file)
                print(f"❌ Found white background: {webp_file.relative_to(BASE_DIR)}")
    
    print(f"\n📊 Checked {checked} WebP files")
    print(f"🚨 Found {len(problematic_files)} files with white backgrounds\n")
    
    if problematic_files:
        print("🔧 Fixing problematic WebP files...\n")
        fixed = 0
        failed = 0
        
        for webp_file in problematic_files:
            source = find_source_image(webp_file)
            
            if source:
                if convert_to_webp_proper(source, webp_file):
                    print(f"✅ Fixed: {webp_file.relative_to(BASE_DIR)}")
                    print(f"   Source: {source.name}\n")
                    fixed += 1
                else:
                    print(f"⚠️  Failed to fix: {webp_file.relative_to(BASE_DIR)}\n")
                    failed += 1
            else:
                print(f"⚠️  No source image found for: {webp_file.relative_to(BASE_DIR)}\n")
                failed += 1
        
        print(f"\n✅ Fixed: {fixed}")
        print(f"❌ Failed: {failed}")
    else:
        print("✨ All WebP files look good!")


if __name__ == "__main__":
    main()