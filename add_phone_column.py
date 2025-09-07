#!/usr/bin/env python3
"""
Add phone column to orders table
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from routes import db
from sqlalchemy import text

def add_phone_column():
    """Add phone column to orders table if it doesn't exist"""
    with app.app_context():
        try:
            # Check if phone column already exists
            result = db.session.execute(text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'phone'
                AND TABLE_SCHEMA = DATABASE()
            """))
            
            if result.fetchone():
                print("✅ Phone column already exists in orders table")
                return True
            
            # Add the phone column
            print("Adding phone column to orders table...")
            db.session.execute(text("""
                ALTER TABLE orders 
                ADD COLUMN phone VARCHAR(20) NULL 
                COMMENT 'Customer phone number'
            """))
            
            db.session.commit()
            print("✅ Successfully added phone column to orders table")
            return True
            
        except Exception as e:
            print(f"❌ Error adding phone column: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("Adding phone column to orders table...")
    success = add_phone_column()
    if success:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        sys.exit(1)