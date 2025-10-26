#!/usr/bin/env python3
"""
CSS Optimization Script
Splits large CSS files into critical and non-critical parts for better performance
"""

import os
import re
from pathlib import Path

def extract_critical_css(css_content):
    """
    Extract critical CSS rules (above-the-fold content)
    """
    critical_patterns = [
        # Reset and base styles
        r'\*\s*\{[^}]+\}',
        r':root\s*\{[^}]+\}',
        r'html\s*\{[^}]+\}',
        r'body\s*\{[^}]+\}',
        
        # Navigation
        r'\.navbar[^{}]*\{[^}]+\}',
        r'\.nav[^{}]*\{[^}]+\}',
        r'\.navbar-[^{}]*\{[^}]+\}',
        
        # Hero section
        r'\.hero[^{}]*\{[^}]+\}',
        
        # Buttons (critical)
        r'\.btn[^{}]*\{[^}]+\}',
        
        # Container and grid
        r'\.container[^{}]*\{[^}]+\}',
        r'\.product-grid\s*\{[^}]+\}',
        r'\.product-card\s*\{[^}]+\}',
        r'\.product-image\s*\{[^}]+\}',
        
        # Typography
        r'h[1-6]\s*\{[^}]+\}',
        r'\.lead\s*\{[^}]+\}',
        
        # Utilities
        r'\.text-center\s*\{[^}]+\}',
        r'\.mb-\d+\s*\{[^}]+\}',
        r'\.mt-\d+\s*\{[^}]+\}',
        r'\.fade-in[^{}]*\{[^}]+\}',
    ]
    
    critical_css = []
    for pattern in critical_patterns:
        matches = re.findall(pattern, css_content, re.DOTALL | re.MULTILINE)
        critical_css.extend(matches)
    
    return '\n'.join(critical_css)

def minify_css(css_content):
    """
    Basic CSS minification
    """
    # Remove comments
    css_content = re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/', '', css_content)
    
    # Remove unnecessary whitespace
    css_content = re.sub(r'\s+', ' ', css_content)
    css_content = re.sub(r'\s*([{}:;,])\s*', r'\1', css_content)
    
    # Remove trailing semicolon before closing brace
    css_content = re.sub(r';\}', '}', css_content)
    
    return css_content.strip()

def split_css_file(input_path, output_dir):
    """
    Split CSS file into critical and non-critical parts
    """
    # Read the original CSS file
    with open(input_path, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Extract critical CSS
    critical_css = extract_critical_css(css_content)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save critical CSS
    critical_path = os.path.join(output_dir, 'critical.css')
    with open(critical_path, 'w', encoding='utf-8') as f:
        f.write(minify_css(critical_css))
    
    # Save minified version of full CSS
    minified_path = os.path.join(output_dir, 'styles.min.css')
    with open(minified_path, 'w', encoding='utf-8') as f:
        f.write(minify_css(css_content))
    
    print(f"✅ Critical CSS saved to: {critical_path}")
    print(f"✅ Minified CSS saved to: {minified_path}")
    
    # Calculate size reduction
    original_size = len(css_content)
    critical_size = len(critical_css)
    minified_size = len(minify_css(css_content))
    
    print(f"\n📊 Size Statistics:")
    print(f"  Original CSS: {original_size:,} bytes")
    print(f"  Critical CSS: {critical_size:,} bytes ({critical_size/original_size*100:.1f}%)")
    print(f"  Minified CSS: {minified_size:,} bytes ({minified_size/original_size*100:.1f}%)")
    print(f"  Size reduction: {(original_size - minified_size)/original_size*100:.1f}%")

def main():
    """
    Main function to optimize CSS files
    """
    project_root = Path(__file__).parent
    css_dir = project_root / 'static' / 'CSS'
    
    # Check if styles.css exists
    styles_css = css_dir / 'styles.css'
    if not styles_css.exists():
        print(f"❌ Error: {styles_css} not found!")
        return
    
    print("🚀 Starting CSS optimization...")
    split_css_file(styles_css, css_dir)
    
    print("\n✨ CSS optimization complete!")
    print("\n📝 Next steps:")
    print("1. Test the site with ?perf=1 query parameter to use optimized template")
    print("2. Inline critical.css in the <head> for best performance")
    print("3. Load styles.min.css asynchronously")

if __name__ == '__main__':
    main()