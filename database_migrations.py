"""
Automatic database schema migrations that run on app startup.
Ensures all required columns exist without manual intervention.
"""

import logging
from sqlalchemy import text, inspect

logger = logging.getLogger(__name__)

def ensure_discount_usages_created_at(db):
    """
    Ensure discount_usages table has created_at column.
    This fixes the "Unknown column 'created_at'" error.
    """
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('discount_usages')]
        
        if 'created_at' not in columns:
            logger.warning("⚠️  Missing 'created_at' column in discount_usages table - FIXING...")
            db.session.execute(text("""
                ALTER TABLE discount_usages 
                ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            """))
            db.session.commit()
            logger.info("✅ Added 'created_at' column to discount_usages table")
            return True
        
        logger.debug("✓ discount_usages.created_at column exists")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error ensuring discount_usages.created_at: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return False


def ensure_products_features(db):
    """
    Ensure products table has features column.
    """
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('products')]
        
        if 'features' not in columns:
            logger.warning("⚠️  Missing 'features' column in products table - FIXING...")
            db.session.execute(text("""
                ALTER TABLE products
                ADD COLUMN features TEXT NULL COMMENT 'Primary bullet features (newline/semicolon separated)'
            """))
            db.session.commit()
            logger.info("✅ Added 'features' column to products table")
            return True
        
        logger.debug("✓ products.features column exists")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error ensuring products.features: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return False


def run_all_migrations(db, app):
    """
    Run all database migrations.
    This is called automatically on app startup.
    """
    logger.info("🔧 Running database migrations...")
    
    with app.app_context():
        migrations = [
            ('discount_usages.created_at', ensure_discount_usages_created_at),
            ('products.features', ensure_products_features),
        ]
        
        fixed_count = 0
        for name, migration_func in migrations:
            try:
                if migration_func(db):
                    fixed_count += 1
                    logger.info(f"  ✅ Fixed: {name}")
            except Exception as e:
                logger.error(f"  ❌ Error with {name}: {e}")
        
        if fixed_count > 0:
            logger.info(f"🎉 Database migrations complete - {fixed_count} schema issues fixed")
        else:
            logger.info("✓ All database schemas are up-to-date")