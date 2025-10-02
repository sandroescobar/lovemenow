import os
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

import stripe
from flask import Flask, render_template, redirect, request, url_for, flash, jsonify, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask_talisman import Talisman  # ENABLED for CSP/Stripe
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
from routes.discount import discount_bp

# Load environment variables
load_dotenv()


# --- Final CSP middleware that runs AFTER everything else (wins last) ---
class FinalCSPMiddleware:
    """
    Ensures one final, permissive-enough CSP is applied for Stripe Elements.
    Also strips any CSP-Report-Only header to avoid additive intersections.
    """

    def __init__(self, app):
        self.app = app
        # Final/effective policy
        self.csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' "
            "https://js.stripe.com https://api.mapbox.com https://cdn.jsdelivr.net "
            "https://code.jquery.com https://cdnjs.cloudflare.com "
            "https://www.googletagmanager.com https://www.google-analytics.com "
            "https://www.googleadservices.com https://googleads.g.doubleclick.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com "
            "https://api.mapbox.com https://cdn.jsdelivr.net https://netdna.bootstrapcdn.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "media-src 'self'; "
            "frame-src 'self' https://js.stripe.com https://hooks.stripe.com https://m.stripe.com "
            "https://pay.google.com https://maps.google.com https://www.google.com "
            "https://www.googletagmanager.com https://www.googleadservices.com; "
            "child-src https://js.stripe.com https://hooks.stripe.com https://m.stripe.com "
            "https://pay.google.com https://maps.google.com https://www.google.com "
            "https://www.googletagmanager.com https://www.googleadservices.com; "
            "connect-src 'self' https://api.stripe.com https://r.stripe.com https://m.stripe.network "
            "https://api.mapbox.com https://www.google-analytics.com https://www.googletagmanager.com "
            "https://www.google.com https://www.googleadservices.com https://googleads.g.doubleclick.net; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'"
        )

    def __call__(self, environ, start_response):
        def sr(status, headers, exc_info=None):
            # Remove any prior CSP headers so we don't get additive intersection
            filtered = []
            for (k, v) in headers:
                kl = k.lower()
                if kl in ("content-security-policy", "content-security-policy-report-only"):
                    continue
                filtered.append((k, v))

            # Set our final CSP and a debug marker
            filtered.append(("Content-Security-Policy", self.csp))
            filtered.append(("X-Debug-CSP", "final_wsgi_mw_v2"))

            return start_response(status, filtered, exc_info)

        return self.app(environ, sr)


# -----------------------------------------------------------------------


def create_app(config_name=None):
    """Application factory pattern for creating Flask app"""
    app = Flask(__name__)

    @app.context_processor
    def inject_age_verified():
        av = bool(session.get('age_verified') or (request.cookies.get('age_verified') == '1'))
        return {'age_verified': av}

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

    # Configure Stripe with better error handling and debugging
    stripe_secret_key = app.config.get('STRIPE_SECRET_KEY')

    # Enhanced debugging for Render deployment
    app.logger.info(
        f"🔍 APP INIT - Environment STRIPE_SECRET_KEY: {os.getenv('STRIPE_SECRET_KEY')[:10] if os.getenv('STRIPE_SECRET_KEY') else 'NOT SET'}...")
    app.logger.info(
        f"🔍 APP INIT - Config STRIPE_SECRET_KEY: {stripe_secret_key[:10] if stripe_secret_key else 'NOT SET'}...")
    app.logger.info(f"🔍 APP INIT - Key ending: ...{stripe_secret_key[-10:] if stripe_secret_key else 'NO KEY'}")
    app.logger.info(f"🔍 APP INIT - Key length: {len(stripe_secret_key) if stripe_secret_key else 0}")

    if stripe_secret_key:
        stripe.api_key = stripe_secret_key
        app.logger.info(f"✅ Stripe API key configured successfully: {stripe.api_key[:10]}...{stripe.api_key[-4:]}")
    else:
        app.logger.error("❌ Stripe API key not configured - check STRIPE_SECRET_KEY environment variable")

    # Database performance optimizations
    if config_name == 'production':
        # Production database optimizations
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 20,
            'pool_timeout': 30,
            'pool_recycle': 1800,  # 30 minutes
            'max_overflow': 30,
            'pool_pre_ping': True,
            'connect_args': {
                'connect_timeout': 10,
                'read_timeout': 30,
                'write_timeout': 30
            }
        }
    else:
        # Development database optimizations
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'pool_timeout': 20,
            'pool_recycle': 3600,
            'max_overflow': 10,
            'pool_pre_ping': True
        }

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_mgr.init_app(app)

    # Add response compression for better performance
    try:
        from flask_compress import Compress

        # Configure compression settings
        app.config['COMPRESS_MIMETYPES'] = [
            'text/html',
            'text/css',
            'text/xml',
            'application/json',
            'application/javascript',
            'text/javascript',
            'application/xml',
            'text/plain'
        ]
        app.config['COMPRESS_LEVEL'] = 6  # Good balance between compression and speed
        app.config['COMPRESS_MIN_SIZE'] = 500  # Only compress files larger than 500 bytes



        Compress(app)
        app.logger.info("Response compression enabled with optimized settings")
    except ImportError:
        app.logger.warning("Flask-Compress not available, skipping compression")

    # Add static file caching for better performance
    @app.after_request
    def add_performance_headers(response):
        # Cache static files for 1 year
        if request.endpoint == 'static':
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response

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

    # Add csrf_token function to templates
    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['csrf_token'] = generate_csrf

    # Initialize security middleware
    security = SecurityMiddleware()
    security.init_app(app)

    # Initialize Uber Direct service
    init_uber_service(app)

    # Security headers / CSP for Stripe Elements
    app.logger.info(f"Current config_name: {config_name}")
    app.logger.info(f"FLASK_ENV: {os.getenv('FLASK_ENV', 'NOT SET')}")

    # ── Stripe-friendly CSP via Flask-Talisman (ok if SecurityMiddleware also sets CSP;
    # our FinalCSPMiddleware below will override everything at the very end) ──
    STRIPE_JS = "https://js.stripe.com"
    STRIPE_API = "https://api.stripe.com"
    STRIPE_HOOKS = "https://hooks.stripe.com"
    STRIPE_R = "https://r.stripe.com"

    csp = {
        "default-src": ["'self'"],
        "script-src": [
            "'self'",
            STRIPE_JS,
            "https://www.googletagmanager.com",
            "https://www.google-analytics.com",
            "https://www.googleadservices.com",
            "https://googleads.g.doubleclick.net",
        ],
        "style-src": ["'self'", "'unsafe-inline'"],
        "frame-src": [
            STRIPE_JS, STRIPE_HOOKS,
            "https://maps.google.com", "https://www.google.com",
            "https://www.googletagmanager.com",
            "https://www.googleadservices.com",
        ],
        "connect-src": [
            "'self'",
            STRIPE_API, STRIPE_R,
            "https://www.google-analytics.com",
            "https://www.googletagmanager.com",
            "https://www.google.com",  # for /ccm/collect
            "https://www.googleadservices.com",
            "https://googleads.g.doubleclick.net",
        ],
        "img-src": ["'self'", "data:", "*.stripe.com", "*.googleapis.com", "*.gstatic.com"],
        "font-src": ["'self'", "data:"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'self'"],
    }

    talisman = Talisman(
        app,
        content_security_policy=csp,
        force_https=True,
        content_security_policy_nonce_in=['script-src']  # expose csp_nonce() to templates
    )
    app.logger.info("✅ CSP enabled via Flask-Talisman with Stripe + GTM/GA allowances")

    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
        app.logger.info('LoveMeNow application started')

    # Register blueprints
    register_blueprints(app)

    # Exempt webhook endpoints from CSRF protection (must be after blueprint registration)
    from routes import csrf
    csrf.exempt(app.view_functions['webhooks.stripe_webhook'])

    EXEMPT_PATH_PREFIXES = (
        '/static/',  # assets
        '/api/',  # your APIs
        '/webhooks/',  # webhooks
    )
    EXEMPT_PATHS = {
        '/auth/age-verification',
        '/auth/verify-age',
        '/robots.txt',
        '/sitemap.xml',
        '/favicon.ico',
    }

    @app.before_request
    def enforce_age_gate_everywhere():
        # allow exempt
        path = request.path or '/'
        if path in EXEMPT_PATHS or any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
            return

        # already verified?
        if session.get('age_verified') or request.cookies.get('age_verified') == '1':
            return

        # block everything else
        current_app.logger.info(f"[AGE-GATE] redirecting {path} -> /auth/age-verification")
        return redirect(url_for('auth.age_verification', next=request.url))

    # Register error handlers
    register_error_handlers(app)

    # SEO Routes - Add these directly to the app
    @app.route('/sitemap.xml')
    def sitemap():
        """Serve sitemap.xml for search engines"""
        from flask import send_from_directory
        return send_from_directory('.', 'sitemap.xml', mimetype='application/xml')

    @app.route('/robots.txt')
    def robots():
        """Serve robots.txt for search engines"""
        from flask import send_from_directory
        return send_from_directory('.', 'robots.txt', mimetype='text/plain')

    # Install the final CSP middleware LAST so it wins over everything else
    app.wsgi_app = FinalCSPMiddleware(app.wsgi_app)

    return app




def register_blueprints(app):
    from routes.auth import auth_bp  # if auth_bp already has a url_prefix in its file, drop the one here
    from routes.main import main_bp
    from routes.api import api_bp  # already has url_prefix='/api'
    from routes.cart import cart_bp  # keep only if cart_bp has no prefix in its file
    from routes.wishlist import wishlist_bp  # same note as cart
    from routes.webhooks import webhooks_bp
    from routes.uber import uber_bp
    from routes.admin import admin_bp
    from routes.discount import discount_bp  # our discount endpoints use absolute paths like /api/cart/...

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')  # remove if auth_bp already sets one
    app.register_blueprint(api_bp)  # ✅ no extra prefix here
    app.register_blueprint(cart_bp, url_prefix='/api/cart')  # only if cart_bp has no prefix in its file
    app.register_blueprint(wishlist_bp, url_prefix='/api/wishlist')  # only if wishlist_bp has no prefix in its file
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
    app.register_blueprint(uber_bp, url_prefix='/api/uber')
    app.register_blueprint(discount_bp)  # our routes start with /api/...


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
