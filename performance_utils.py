"""
Performance utilities for LoveMeNow application
Provides caching and optimization functions without affecting styling
"""

from functools import lru_cache
from flask import current_app
import time

# Cache for 5 minutes (300 seconds)
@lru_cache(maxsize=128)
def get_featured_products():
    """Get featured products with caching"""
    try:
        from models import Product
        
        # Get featured products (limit to 3) - products that are in stock
        # Exclude Sexual Enhancements (category_id=59) to avoid Google Ads policy flags
        featured_products = (
            Product.query
            .filter(Product.in_stock == True, Product.quantity_on_hand > 0, Product.category_id != 59)
            .limit(3)
            .all()
        )
        
        return featured_products
    except Exception as e:
        current_app.logger.error(f"Error getting featured products: {e}")
        return []

@lru_cache(maxsize=64)
def get_main_categories():
    """Get main categories with caching"""
    try:
        from models import Category
        
        # Get main categories (parent categories)
        categories = Category.query.filter(Category.parent_id.is_(None)).all()
        return categories
    except Exception as e:
        current_app.logger.error(f"Error getting categories: {e}")
        return []

def get_optimized_user_counts():
    """Get cart and wishlist counts - placeholder for now"""
    # For now, return default values since cart/wishlist are frontend-only
    return 0, 0

def get_fallback_data():
    """Fallback data when database is unavailable"""
    return {
        'featured_products': [],
        'categories': [],
        'cart_count': 0,
        'wishlist_count': 0
    }

def test_database_connection():
    """Test database connection"""
    try:
        from models import db
        from sqlalchemy import text
        # Simple query to test connection
        db.session.execute(text('SELECT 1'))
        return True, "Database connection successful"
    except Exception as e:
        return False, str(e)