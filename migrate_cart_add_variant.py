#!/usr/bin/env python3
"""
Migration script to add variant_id column to cart table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from routes import db
from sqlalchemy import text

def migrate_cart_table():
    """Add variant_id column to cart table and update constraints"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Starting cart table migration...")
            
            # Check if variant_id column already exists
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.columns 
                WHERE table_name = 'cart' 
                AND column_name = 'variant_id'
                AND table_schema = DATABASE()
            """)).fetchone()
            
            if result.count > 0:
                print("variant_id column already exists in cart table")
                return
            
            # Add variant_id column
            print("Adding variant_id column to cart table...")
            db.session.execute(text("""
                ALTER TABLE cart 
                ADD COLUMN variant_id INT NULL,
                ADD INDEX idx_cart_variant_id (variant_id),
                ADD FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
            """))
            
            # Drop old unique constraint
            print("Dropping old unique constraint...")
            try:
                db.session.execute(text("""
                    ALTER TABLE cart DROP INDEX unique_user_product_cart
                """))
            except Exception as e:
                print(f"Note: Could not drop old constraint (may not exist): {e}")
            
            # Add new unique constraint including variant_id
            print("Adding new unique constraint...")
            db.session.execute(text("""
                ALTER TABLE cart 
                ADD CONSTRAINT unique_user_product_variant_cart 
                UNIQUE (user_id, product_id, variant_id)
            """))
            
            # Add composite index for performance
            print("Adding composite index...")
            try:
                db.session.execute(text("""
                    ALTER TABLE cart 
                    ADD INDEX idx_cart_user_product_variant (user_id, product_id, variant_id)
                """))
            except Exception as e:
                print(f"Note: Could not add composite index (may already exist): {e}")
            
            db.session.commit()
            print("✅ Cart table migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_cart_table()