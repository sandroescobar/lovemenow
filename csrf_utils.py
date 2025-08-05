"""
CSRF Protection Utilities
Provides smart CSRF handling that works with both JSON and form submissions
"""
from functools import wraps
from flask import request, jsonify, current_app
from flask_wtf.csrf import validate_csrf, ValidationError
import json


def smart_csrf_protect(f):
    """
    Smart CSRF protection decorator that:
    1. Automatically validates CSRF tokens for POST/PUT/DELETE requests
    2. Works with both JSON and form data
    3. Provides helpful error messages
    4. Allows exemptions for specific endpoints if needed
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip CSRF for GET, HEAD, OPTIONS requests
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return f(*args, **kwargs)
        
        # Skip CSRF for webhook endpoints (they should have their own validation)
        if request.endpoint and 'webhook' in request.endpoint:
            return f(*args, **kwargs)
        
        try:
            # For JSON requests, look for token in headers or JSON body
            if request.is_json:
                token = None
                
                # First try to get from X-CSRFToken header
                token = request.headers.get('X-CSRFToken')
                
                # If not in headers, try to get from JSON body
                if not token:
                    data = request.get_json()
                    if data and isinstance(data, dict):
                        token = data.get('csrf_token')
                
                if token:
                    validate_csrf(token)
                else:
                    raise ValidationError('CSRF token missing from JSON request')
            
            # For form requests, Flask-WTF will automatically validate
            else:
                # Let Flask-WTF handle form validation automatically
                # The token should be in the form data
                pass
            
        except ValidationError as e:
            current_app.logger.warning(f"CSRF validation failed for {request.endpoint}: {str(e)}")
            
            if request.is_json:
                return jsonify({
                    'error': 'CSRF token validation failed. Please refresh the page and try again.',
                    'csrf_error': True
                }), 400
            else:
                # For form requests, Flask-WTF will handle this automatically
                # But we can provide a custom response if needed
                from flask import flash, redirect, url_for
                flash('Security token expired. Please try again.', 'error')
                return redirect(request.referrer or url_for('main.index'))
        
        except Exception as e:
            current_app.logger.error(f"CSRF validation error for {request.endpoint}: {str(e)}")
            
            if request.is_json:
                return jsonify({
                    'error': 'Security validation failed. Please refresh the page and try again.',
                    'csrf_error': True
                }), 400
            else:
                from flask import flash, redirect, url_for
                flash('Security validation failed. Please try again.', 'error')
                return redirect(request.referrer or url_for('main.index'))
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_csrf_token():
    """
    Get a fresh CSRF token for use in JavaScript
    """
    from flask_wtf.csrf import generate_csrf
    return generate_csrf()


def csrf_exempt_routes():
    """
    List of routes that should be exempt from CSRF protection
    Add routes here that need to be exempt (like webhooks)
    """
    return [
        'webhooks.stripe_webhook',
        'api.health_check',  # If you have a health check endpoint
    ]