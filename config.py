"""
Configuration settings for LoveMeNow application
"""
import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class"""
    
    # Generate a secure secret key if not provided
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DB_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database connection settings for Railway MySQL
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0,
        'connect_args': {
            'connect_timeout': 30,
            'read_timeout': 30,
            'write_timeout': 30,
            'charset': 'utf8mb4'
        }
    }
    
    # Session configuration
    REMEMBER_COOKIE_DURATION = timedelta(days=1)
    REMEMBER_COOKIE_SECURE = True  # Only send over HTTPS
    REMEMBER_COOKIE_HTTPONLY = True  # Prevent XSS
    SESSION_COOKIE_SECURE = True  # Only send over HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent XSS
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    
    # Security headers
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(hours=1)
    
    # Stripe configuration
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # Domain configuration
    DOMAIN = os.getenv('DOMAIN', 'http://127.0.0.1:9000')
    
    # Email configuration
    SENDLAYER_API_KEY = os.getenv('SENDLAYER_API_KEY')
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL', 'memory://')
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    WTF_CSRF_SSL_STRICT = False  # Allow CSRF over HTTP in development
    
    # Uber Direct configuration
    UBER_CLIENT_ID = os.getenv('UBER_CLIENT_ID')
    UBER_CLIENT_SECRET = os.getenv('UBER_CLIENT_SECRET')
    UBER_CUSTOMER_ID = os.getenv('UBER_CUSTOMER_ID')
    UBER_SANDBOX = os.getenv('UBER_SANDBOX', 'true').lower() == 'true'
    
    # Store information
    STORE_NAME = os.getenv('STORE_NAME', 'LoveMeNow Miami')
    STORE_PHONE = os.getenv('STORE_PHONE', '+1234567890')
    STORE_ADDRESS = os.getenv('STORE_ADDRESS', '1234 Biscayne Blvd')
    STORE_SUITE = os.getenv('STORE_SUITE', 'Suite 100')
    STORE_CITY = os.getenv('STORE_CITY', 'Miami')
    STORE_STATE = os.getenv('STORE_STATE', 'FL')
    STORE_ZIP = os.getenv('STORE_ZIP', '33132')
    STORE_LATITUDE = float(os.getenv('STORE_LATITUDE', '25.7617'))
    STORE_LONGITUDE = float(os.getenv('STORE_LONGITUDE', '-80.1918'))
    
    # Slack integration
    SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
    
    @staticmethod
    def validate_config():
        """Validate that required environment variables are set"""
        required_vars = [
            'DB_URL',
            'SECRET_KEY',
            'STRIPE_SECRET_KEY',
            'STRIPE_PUBLISHABLE_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise RuntimeError(
                f"❌ Missing required environment variables: {', '.join(missing_vars)}\n"
                f"Please set these in your .env file or environment."
            )

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    REMEMBER_COOKIE_SECURE = False  # Allow HTTP in development
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    
    # Fallback database for development
    SQLALCHEMY_DATABASE_URI_FALLBACK = os.getenv('DB_URL_FALLBACK', 'sqlite:///lovemenow_local.db')

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Enhanced security for production
    PREFERRED_URL_SCHEME = 'https'
    WTF_CSRF_SSL_STRICT = True  # Enforce HTTPS for CSRF in production
    
    # Additional security headers
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://js.stripe.com https://api.mapbox.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://api.mapbox.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https:; media-src 'self'; connect-src 'self' https://api.stripe.com https://api.mapbox.com;"
    }

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}