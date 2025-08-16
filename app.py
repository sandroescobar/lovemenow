"""
LoveMeNow - Secure E-commerce Application
Production-ready Flask application with comprehensive security measures
"""
import os
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

import stripe
from flask import Flask, render_template, redirect, request, url_for, flash, jsonify, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
# from flask_talisman import Talisman  # DISABLED FOR STRIPE TESTING
from sqlalchemy.orm import joinedload
from sqlalchemy import text, func
from dotenv import load_dotenv


# Import our modules
from config import config
from security import SecurityMiddleware, validate_input, sanitize_filename, is_safe_url
from routes import db, bcrypt, login_mgr, migrate
from models import User, UserAddress, Category, Product, Wishlist, Cart, Order, OrderItem, Color, UberDelivery, AuditLog
from email_utils import send_email_sendlayer
from email_marketing import EmailMarketing
from uber_service import init_uber_service

# Load environment variables
load_dotenv()

def create_app(config_name=None):
    """Application factory pattern for creating Flask app"""
    app = Flask(__name__)
    
    # Determine environment
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Configure session settings based on environment
    if config_name == 'development':
        app.config['SESSION_COOKIE_SECURE'] = False
        app.config['REMEMBER_COOKIE_SECURE'] = False
        app.config['SESSION_PERMANENT'] = False  # Sessions expire when browser closes
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.logger.info("Development mode: Session cookies set to non-secure and expire on browser close")
    elif config_name == 'production':
        # Production security settings
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['REMEMBER_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        app.logger.info("Production mode: Enhanced security settings applied")
    

    
    # Validate configuration
    try:
        config[config_name].validate_config()
    except RuntimeError as e:
        # Don't exit, but log the error
        app.logger.error(f"Configuration validation failed: {e}")
    
    # Configure Stripe with better error handling
    stripe_secret_key = app.config.get('STRIPE_SECRET_KEY')
    if stripe_secret_key:
        stripe.api_key = stripe_secret_key
    else:
        app.logger.warning("Stripe API key not configured")
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_mgr.init_app(app)
    
    # Add session validation for development
    if config_name == 'development':
        # Store server start time for session validation
        import time
        app.config['SERVER_START_TIME'] = time.time()
        
        @app.before_request
        def validate_session():
            """Validate session integrity - clear invalid sessions after server restart"""
            from flask import session, request
            import time
            
            # Skip validation for static files and API endpoints that don't need sessions
            if request.endpoint and (
                request.endpoint.startswith('static') or
                request.endpoint in ['api.health', 'webhooks.stripe_webhook']
            ):
                return
            
            # Check if session was created before server restart
            session_start_time = session.get('_server_start_time')
            current_server_start_time = app.config['SERVER_START_TIME']
            
            if session_start_time and session_start_time != current_server_start_time:
                app.logger.info("🔄 Session from previous server instance detected - clearing session")
                session.clear()
            
            # Set server start time in session for new sessions
            if '_server_start_time' not in session:
                session['_server_start_time'] = current_server_start_time
    login_mgr.login_view = "main.index"
    login_mgr.login_message = "Please log in to access this page."
    login_mgr.login_message_category = "info"
    
    # Initialize CSRF protection
    from routes import csrf
    csrf.init_app(app)
    
    # Exempt webhook endpoints from CSRF protection
    csrf.exempt('webhooks.stripe_webhook')
    
    # Add csrf_token function to templates
    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['csrf_token'] = generate_csrf
    
    # Initialize security middleware
    security = SecurityMiddleware()
    security.init_app(app)
    
    # Initialize Uber Direct service
    init_uber_service(app)
    
    # Security headers - Apply CSP for testing (temporarily for all environments)
    app.logger.info(f"Current config_name: {config_name}")
    app.logger.info(f"FLASK_ENV: {os.getenv('FLASK_ENV', 'NOT SET')}")
    
    # CSP COMPLETELY DISABLED FOR STRIPE TESTING
    app.logger.info("🚫 CSP COMPLETELY DISABLED - NO TALISMAN APPLIED")
    app.logger.info("🚫 This should allow Stripe frames to load without any CSP restrictions")
    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
        app.logger.info('LoveMeNow application started')
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    return app

def register_blueprints(app):
    """Register application blueprints"""
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.cart import cart_bp
    from routes.wishlist import wishlist_bp
    from routes.webhooks import webhooks_bp
    from routes.uber import uber_bp
    from routes.admin import admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(cart_bp, url_prefix='/api/cart')
    app.register_blueprint(wishlist_bp, url_prefix='/api/wishlist')
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
    app.register_blueprint(uber_bp, url_prefix='/api/uber')
    app.register_blueprint(admin_bp, url_prefix='/admin')

def register_error_handlers(app):
    """Register error handlers"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429

@login_mgr.user_loader
def load_user(user_id: str):
    """Load user for Flask-Login"""
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

# Create the application
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Skip database creation for now to avoid timeout
        # db.create_all()
        
        # Run the application
        port = int(os.getenv('PORT', 2100))
        debug = os.getenv('FLASK_ENV') == 'development'
        
        app.run(
            host='127.0.0.1',
            port=port,
            debug=debug,
            threaded=True
        )