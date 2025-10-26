#!/usr/bin/env python3
"""
Image Optimization Script
Optimizes images for web performance and generates WebP versions
"""

import os
import sys
from pathlib import Path
from PIL import Image
import concurrent.futures

def optimize_image(image_path, quality=85, max_width=1200):
    """
    Optimize a single image file
    """
    try:
        with Image.open(image_path) as img:
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize if too large
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Save optimized version
            output_path = image_path.with_suffix('.opt' + image_path.suffix)
            img.save(output_path, optimize=True, quality=quality)
            
            # Save WebP version for modern browsers
            webp_path = image_path.with_suffix('.webp')
            img.save(webp_path, 'WEBP', optimize=True, quality=quality)
            
            # Get file sizes
            original_size = os.path.getsize(image_path)
            optimized_size = os.path.getsize(output_path)
            webp_size = os.path.getsize(webp_path)
            
            return {
                'path': str(image_path),
                'original_size': original_size,
                'optimized_size': optimized_size,
                'webp_size': webp_size,
                'saved': original_size - min(optimized_size, webp_size)
            }
    except Exception as e:
        return {
            'path': str(image_path),
            'error': str(e)
        }

def generate_placeholder(image_path, size=(20, 20)):
    """
    Generate a low-quality placeholder image for lazy loading
    """
    try:
        with Image.open(image_path) as img:
            # Create tiny placeholder
            img_small = img.resize(size, Image.Resampling.LANCZOS)
            
            # Convert to base64-encoded data URI
            from io import BytesIO
            import base64
            
            buffer = BytesIO()
            img_small.save(buffer, format='JPEG', quality=20)
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_base64}"
    except:
        return None

def optimize_directory(directory_path, extensions=('.jpg', '.jpeg', '.png')):
    """
    Optimize all images in a directory
    """
    image_files = []
    for ext in extensions:
        image_files.extend(Path(directory_path).rglob(f'*{ext}'))
        image_files.extend(Path(directory_path).rglob(f'*{ext.upper()}'))
    
    if not image_files:
        print(f"No images found in {directory_path}")
        return
    
    print(f"Found {len(image_files)} images to optimize")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_image = {executor.submit(optimize_image, img): img for img in image_files}
        
        for future in concurrent.futures.as_completed(future_to_image):
            result = future.result()
            results.append(result)
            
            if 'error' in result:
                print(f"❌ Error: {result['path']} - {result['error']}")
            else:
                saved_mb = result['saved'] / 1024 / 1024
                print(f"✅ Optimized: {Path(result['path']).name} - Saved {saved_mb:.2f} MB")
    
    # Summary
    total_saved = sum(r.get('saved', 0) for r in results if 'saved' in r)
    total_saved_mb = total_saved / 1024 / 1024
    
    print(f"\n📊 Optimization Summary:")
    print(f"  Total images processed: {len(results)}")
    print(f"  Total space saved: {total_saved_mb:.2f} MB")
    
    return results

def generate_picture_tag(image_path, alt_text="", lazy=True):
    """
    Generate a <picture> tag with WebP and fallback
    """
    webp_path = image_path.replace('.jpg', '.webp').replace('.png', '.webp').replace('.jpeg', '.webp')
    
    loading = 'lazy' if lazy else 'eager'
    
    return f'''<picture>
    <source srcset="{webp_path}" type="image/webp">
    <source srcset="{image_path}" type="image/jpeg">
    <img src="{image_path}" alt="{alt_text}" loading="{loading}" decoding="async">
</picture>'''

def create_image_config(directory_path):
    """
    Create a configuration file with optimized image paths
    """
    config = {}
    
    for img_file in Path(directory_path).rglob('*.webp'):
        relative_path = img_file.relative_to(directory_path)
        original_name = str(relative_path).replace('.webp', '')
        
        # Try to find the original
        for ext in ['.jpg', '.jpeg', '.png']:
            original = directory_path / (original_name + ext)
            if original.exists():
                config[str(original.relative_to(directory_path))] = {
                    'webp': str(relative_path),
                    'placeholder': generate_placeholder(original)
                }
                break
    
    # Save config
    import json
    config_path = directory_path / 'image_config.json'
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Image configuration saved to {config_path}")
    return config

def main():
    """
    Main function
    """
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = Path(__file__).parent / 'static' / 'IMG'
    
    if not os.path.exists(directory):
        print(f"❌ Directory not found: {directory}")
        return
    
    print(f"🚀 Starting image optimization in {directory}...")
    
    # Install required packages
    try:
        from PIL import Image
    except ImportError:
        print("Installing required packages...")
        os.system("pip install Pillow")
        from PIL import Image
    
    # Optimize images
    results = optimize_directory(directory)
    
    if results:
        # Generate configuration
        create_image_config(Path(directory))
        
        print("\n✨ Image optimization complete!")
        print("\n📝 Next steps:")
        print("1. Update your templates to use WebP images with fallbacks")
        print("2. Use the <picture> tag for better browser support")
        print("3. Implement lazy loading for below-the-fold images")
        print("4. Consider using a CDN for image delivery")

if __name__ == '__main__':
    main()