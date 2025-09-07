#!/usr/bin/env python3
"""
Add variant_name column to order_items table
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from routes import db
from sqlalchemy import text

def add_variant_name_column():
    """Add variant_name column to order_items table if it doesn't exist"""
    with app.app_context():
        try:
            # Check if variant_name column already exists
            result = db.session.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'order_items' 
                AND COLUMN_NAME = 'variant_name'
                AND TABLE_SCHEMA = DATABASE()
            """))
            
            if result.fetchone():
                print("✅ variant_name column already exists in order_items table")
                return True
            
            # Add the variant_name column
            print("Adding variant_name column to order_items table...")
            db.session.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN variant_name VARCHAR(255) NULL 
                COMMENT 'Store variant/color info'
            """))
            
            db.session.commit()
            print("✅ Successfully added variant_name column to order_items table")
            return True
            
        except Exception as e:
            print(f"❌ Error adding variant_name column: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("Adding variant_name column to order_items table...")
    success = add_variant_name_column()
    if success:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        sys.exit(1)