"""
Application factory for LoveMeNow - Production ready setup
"""
import os
import logging
from flask import Flask
from flask_talisman import Talisman
import stripe

def create_app(config_name=None):
    """Create and configure the Flask application"""
    
    app = Flask(__name__)
    
    # Determine environment
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    # Basic configuration
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or os.urandom(32).hex(),
        SQLALCHEMY_DATABASE_URI=os.getenv("DB_URL"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Security settings
        SESSION_COOKIE_SECURE=config_name == 'production',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        REMEMBER_COOKIE_SECURE=config_name == 'production',
        REMEMBER_COOKIE_HTTPONLY=True,
    )
    
    # Validate required environment variables
    required_vars = ['DB_URL', 'SECRET_KEY', 'STRIPE_SECRET_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise RuntimeError(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
    
    # Configure Stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    
    # Production security headers
    if config_name == 'production':
        # Security headers for production
        csp = {
            'default-src': "'self'",
            'script-src': [
                "'self'",
                "'unsafe-inline'",  # Required for some inline scripts
                'https://js.stripe.com',
                'https://checkout.stripe.com'
            ],
            'style-src': [
                "'self'",
                "'unsafe-inline'",  # Required for inline styles
                'https://fonts.googleapis.com'
            ],
            'font-src': [
                "'self'",
                'https://fonts.gstatic.com'
            ],
            'img-src': [
                "'self'",
                'data:',
                'https:'
            ],
            'connect-src': [
                "'self'",
                'https://api.stripe.com'
            ]
        }
        
        Talisman(app, 
                content_security_policy=csp,
                force_https=True,
                strict_transport_security=True,
                content_security_policy_nonce_in=['script-src', 'style-src'])
    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
        app.logger.info('LoveMeNow startup')
    
    return app