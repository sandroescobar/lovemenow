#!/usr/bin/env python3
"""
Database migration script to add indexes for cart performance optimization.
Run this once to improve cart query performance.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def add_cart_indexes():
    """Add database indexes to improve cart query performance"""
    
    # Get database URL from environment
    db_url = os.getenv('DB_URL')
    if not db_url:
        return False
    
    try:
        # Create database engine
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Check if indexes already exist
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.statistics 
                WHERE table_name = 'cart' 
                AND index_name = 'idx_cart_user_product'
            """))
            
            index_exists = result.fetchone()[0] > 0
            
            if index_exists:
                return True
            
            # Add composite index for cart queries
            
            # Check and add indexes one by one
            try:
                conn.execute(text("CREATE INDEX idx_cart_user_product ON cart (user_id, product_id)"))
            except Exception as e:
                if "Duplicate key name" in str(e):
                    pass
                else:
                    raise e
            
            try:
                conn.execute(text("CREATE INDEX idx_cart_user_id ON cart (user_id)"))
            except Exception as e:
                if "Duplicate key name" in str(e):
                    pass
                else:
                    raise e
            
            try:
                conn.execute(text("CREATE INDEX idx_cart_product_id ON cart (product_id)"))
            except Exception as e:
                if "Duplicate key name" in str(e):
                    pass
                else:
                    raise e
            
            conn.commit()
            return True
            
    except Exception as e:
        return False

if __name__ == "__main__":
    success = add_cart_indexes()