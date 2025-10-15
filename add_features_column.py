#!/usr/bin/env python3
"""
Add features column to products table (idempotent).
- Column type: TEXT NULL
- Purpose: Store primary bullet-style features for PDP and API
"""
import sys
import os

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from routes import db
from sqlalchemy import text


def add_features_column():
    """Create 'features' TEXT column on products if missing."""
    with app.app_context():
        try:
            # Check existence
            check_sql = text(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'products'
                  AND COLUMN_NAME = 'features'
                  AND TABLE_SCHEMA = DATABASE()
                """
            )
            if db.session.execute(check_sql).fetchone():
                print("✅ 'features' column already exists on products")
                return True

            print("Adding 'features' column to products table...")
            alter_sql = text(
                """
                ALTER TABLE products
                ADD COLUMN features TEXT NULL COMMENT 'Primary bullet features (newline/semicolon separated)'
                """
            )
            db.session.execute(alter_sql)
            db.session.commit()
            print("✅ Successfully added 'features' column")
            return True
        except Exception as e:
            print(f"❌ Error adding features column: {str(e)}")
            db.session.rollback()
            return False


if __name__ == "__main__":
    print("Migrating: add 'features' column to products...")
    ok = add_features_column()
    if ok:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        sys.exit(1)