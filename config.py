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
    
    # Stripe configuration - use environment variables only
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
    
    # Google Maps API configuration
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    
    # Store information
    STORE_NAME = os.getenv('STORE_NAME', 'LoveMeNow Miami')
    STORE_DISPLAY_NAME = os.getenv('STORE_DISPLAY_NAME', 'Miami Vape Smoke Shop #2')  # Name for Uber drivers
    STORE_PHONE = os.getenv('STORE_PHONE', '+1234567890')
    STORE_ADDRESS = os.getenv('STORE_ADDRESS', '351 NE 79th St')
    STORE_SUITE = os.getenv('STORE_SUITE', 'Unit 101')
    STORE_CITY = os.getenv('STORE_CITY', 'Miami')
    STORE_STATE = os.getenv('STORE_STATE', 'FL')
    STORE_ZIP = os.getenv('STORE_ZIP', '33138')
    STORE_LATITUDE = float(os.getenv('STORE_LATITUDE', '25.8466'))
    STORE_LONGITUDE = float(os.getenv('STORE_LONGITUDE', '-80.1891'))
    
    # Slack integration
    SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
    
    @staticmethod
    def validate_config():
        """Validate that required environment variables are set"""
        required_vars = [
            'DB_URL',
            'SECRET_KEY'
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
        
        # Validate Stripe keys (but don't fail if they're using fallback)
        config_instance = Config()
        stripe_secret = config_instance.STRIPE_SECRET_KEY
        stripe_publishable = config_instance.STRIPE_PUBLISHABLE_KEY
        
        if not stripe_secret or not stripe_secret.startswith('sk_'):
            print(f"⚠️ Warning: Invalid or missing Stripe secret key")
        else:
            print(f"✅ Stripe secret key configured: {stripe_secret[:10]}...{stripe_secret[-4:]}")
            
        if not stripe_publishable or not stripe_publishable.startswith('pk_'):
            print(f"⚠️ Warning: Invalid or missing Stripe publishable key")
        else:
            print(f"✅ Stripe publishable key configured: {stripe_publishable[:10]}...{stripe_publishable[-4:]}")

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