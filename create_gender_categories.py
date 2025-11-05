#!/usr/bin/env python3
"""
Migration script to create Gender-based filter categories.
Creates "Men" and "Women" as parent categories in the database.

Usage:
    python create_gender_categories.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from routes import db
from models import Category


def create_gender_categories():
    """Create Men and Women parent categories"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if gender categories already exist
            men_exists = Category.query.filter_by(name="Men", parent_id=None).first()
            women_exists = Category.query.filter_by(name="Women", parent_id=None).first()
            
            if men_exists:
                print("✓ 'Men' category already exists (ID: {})".format(men_exists.id))
            else:
                men_category = Category(
                    name="Men",
                    slug="men",
                    parent_id=None
                )
                db.session.add(men_category)
                print("✓ Created 'Men' category")
            
            if women_exists:
                print("✓ 'Women' category already exists (ID: {})".format(women_exists.id))
            else:
                women_category = Category(
                    name="Women",
                    slug="women",
                    parent_id=None
                )
                db.session.add(women_category)
                print("✓ Created 'Women' category")
            
            # Commit changes
            db.session.commit()
            
            # Get the created categories for reference
            men = Category.query.filter_by(name="Men", parent_id=None).first()
            women = Category.query.filter_by(name="Women", parent_id=None).first()
            
            print("\n✅ Gender categories created successfully!")
            print(f"\nMen Category ID: {men.id if men else 'N/A'}")
            print(f"Women Category ID: {women.id if women else 'N/A'}")
            
            print("\n📝 Category Mapping Reference:")
            print("\nMen's Categories:")
            men_ids = [34, 60, 35, 33, 55, 56, 57, 4, 11, 37, 53, 38, 51]
            for cat_id in men_ids:
                cat = Category.query.get(cat_id)
                if cat:
                    print(f"  • {cat.name} (ID: {cat_id})")
                else:
                    print(f"  • ID: {cat_id} (Category not found)")
            
            print("\nWomen's Categories:")
            women_ids = [36, 39, 5, 33, 54, 1, 7, 10, 40, 50, 4, 55, 56, 57, 58, 11, 38]
            for cat_id in women_ids:
                cat = Category.query.get(cat_id)
                if cat:
                    print(f"  • {cat.name} (ID: {cat_id})")
                else:
                    print(f"  • ID: {cat_id} (Category not found)")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error creating gender categories: {e}")
            db.session.rollback()
            return False


if __name__ == "__main__":
    success = create_gender_categories()
    sys.exit(0 if success else 1)