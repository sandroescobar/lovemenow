#!/usr/bin/env python3
"""
Script to remove all WebP files from the project
"""

import os
import glob

def remove_webp_files():
    """Remove all .webp files from the project"""
    project_root = "/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow"
    
    # Find all .webp files recursively
    webp_pattern = os.path.join(project_root, "**", "*.webp")
    webp_files = glob.glob(webp_pattern, recursive=True)
    
    print(f"🔍 Found {len(webp_files)} WebP files to remove:")
    print("=" * 60)
    
    removed_count = 0
    failed_count = 0
    
    for webp_file in webp_files:
        try:
            # Show relative path for cleaner output
            relative_path = os.path.relpath(webp_file, project_root)
            print(f"🗑️  Removing: {relative_path}")
            os.remove(webp_file)
            removed_count += 1
        except Exception as e:
            print(f"❌ Failed to remove {relative_path}: {e}")
            failed_count += 1
    
    print("=" * 60)
    print(f"✅ Successfully removed: {removed_count} WebP files")
    if failed_count > 0:
        print(f"❌ Failed to remove: {failed_count} WebP files")
    else:
        print("🎉 All WebP files have been removed!")

if __name__ == "__main__":
    print("🖼️  WebP File Remover")
    print("=" * 60)
    print("This will DELETE ALL .webp files from your project")
    print("⚠️  This action cannot be undone!")
    print("=" * 60)
    
    confirm = input("Are you sure you want to continue? (y/N): ").lower().strip()
    if confirm in ['y', 'yes']:
        remove_webp_files()
    else:
        print("Operation cancelled.")