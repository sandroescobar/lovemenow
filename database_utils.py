"""
Database utility functions for handling connection issues
"""
import time
import logging
from functools import wraps
from sqlalchemy.exc import OperationalError, DisconnectionError
from flask import current_app

logger = logging.getLogger(__name__)

def retry_db_operation(max_retries=3, delay=1):
    """
    Decorator to retry database operations on connection failures
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DisconnectionError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Database operation failed after {max_retries} attempts: {str(e)}")
                        raise
                except Exception as e:
                    # For non-connection errors, don't retry
                    logger.error(f"Non-connection database error: {str(e)}")
                    raise
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator

def test_database_connection():
    """
    Test database connection and return status
    """
    try:
        from routes import db
        # Simple query to test connection
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"

def get_fallback_data():
    """
    Return fallback data when database is unavailable
    """
    return {
        'featured_products': [],
        'categories': [],
        'cart_count': 0,
        'wishlist_count': 0
    }