#!/usr/bin/env python
"""
Migration script to add missing 'created_at' column to discount_usages table.
This fixes the "Unknown column 'created_at' in 'field list'" error.

Run this once on your database to fix the schema mismatch.
"""

import sys
from datetime import datetime
from app_factory import create_app
from routes import db
from sqlalchemy import text

def migrate():
    app = create_app()
    
    with app.app_context():
        try:
            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('discount_usages')]
            
            if 'created_at' in columns:
                print("✓ Column 'created_at' already exists in discount_usages table")
                return True
            
            print("Adding 'created_at' column to discount_usages table...")
            
            # Add the column
            db.session.execute(text("""
                ALTER TABLE discount_usages 
                ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            """))
            db.session.commit()
            
            print("✓ Successfully added 'created_at' column!")
            print("  - Default value: CURRENT_TIMESTAMP")
            print("  - Type: DATETIME")
            
            return True
            
        except Exception as e:
            print(f"✗ Error during migration: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)