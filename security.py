"""
Security utilities and middleware for LoveMeNow application
"""
import re
from functools import wraps
from flask import request, jsonify, current_app, g
from flask_login import current_user
import time
from collections import defaultdict, deque

class SecurityMiddleware:
    """Security middleware for Flask application"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize security middleware with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Security checks before each request"""
        # Log request for monitoring
        self.log_request()
        
        # Check for suspicious patterns in request
        if self.check_suspicious_requests():
            return jsonify({'error': 'Suspicious request detected'}), 400
        
        # Rate limiting (basic implementation)
        if not self.check_rate_limit():
            return jsonify({'error': 'Rate limit exceeded'}), 429
    
    def after_request(self, response):
        """Add security headers after each request"""
        if current_app.config.get('DEBUG'):
            return response
            
        # Add security headers for production
        security_headers = current_app.config.get('SECURITY_HEADERS', {})
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    def log_request(self):
        """Log request for monitoring and analytics"""
        try:
            # Only log certain types of requests to avoid spam
            if request.method in ['POST', 'PUT', 'DELETE'] or request.endpoint in ['main.products', 'main.product_detail', 'main.checkout']:
                from models import AuditLog
                from flask_login import current_user
                
                # Determine action based on endpoint and method
                action = f"{request.method}_{request.endpoint}" if request.endpoint else f"{request.method}_{request.path}"
                
                AuditLog.log_action(
                    action=action,
                    user_id=current_user.id if current_user.is_authenticated else None,
                    details=f"Path: {request.path}, Args: {dict(request.args)}",
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    status='request'
                )
        except Exception as e:
            # Don't let logging errors break the request
            current_app.logger.warning(f"Failed to log request: {e}")
    
    def check_suspicious_requests(self):
        """Check for suspicious request patterns"""
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'eval\(',
            r'expression\(',
            r'url\(',
            r'import\(',
            r'\.\./',  # Path traversal
            r'union.*select',  # SQL injection
            r'drop.*table',  # SQL injection
        ]
        
        # Check URL and query parameters
        full_url = request.url
        request_data = str(request.get_data())
        
        for pattern in suspicious_patterns:
            if re.search(pattern, full_url, re.IGNORECASE) or re.search(pattern, request_data, re.IGNORECASE):
                current_app.logger.warning(f"Suspicious request detected: {request.remote_addr} - {full_url}")
                
                # Log to audit log
                try:
                    from models import AuditLog
                    from flask_login import current_user
                    
                    AuditLog.log_action(
                        action='suspicious_request',
                        user_id=current_user.id if current_user.is_authenticated else None,
                        details=f"Pattern: {pattern}, URL: {full_url}, Data: {request_data[:500]}",
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        status='warning'
                    )
                except Exception as e:
                    current_app.logger.error(f"Failed to log suspicious request: {e}")
                
                return True  # Suspicious request detected
        
        return False  # No suspicious patterns found
    
    def check_rate_limit(self):
        """Basic rate limiting implementation"""
        if not hasattr(g, 'rate_limiter'):
            g.rate_limiter = defaultdict(lambda: deque())
        
        client_ip = request.remote_addr
        now = time.time()
        
        # Clean old requests (older than 1 minute)
        while g.rate_limiter[client_ip] and g.rate_limiter[client_ip][0] < now - 60:
            g.rate_limiter[client_ip].popleft()
        
        # Check if rate limit exceeded (60 requests per minute)
        if len(g.rate_limiter[client_ip]) >= 60:
            # Log rate limit violation
            try:
                from models import AuditLog
                from flask_login import current_user
                
                AuditLog.log_action(
                    action='rate_limit_exceeded',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    details=f"IP: {client_ip}, Requests: {len(g.rate_limiter[client_ip])}, URL: {request.url}",
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    status='warning'
                )
            except Exception as e:
                current_app.logger.error(f"Failed to log rate limit violation: {e}")
            
            return False
        
        # Add current request
        g.rate_limiter[client_ip].append(now)
        return True

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # Log failed admin access attempt
            from models import AuditLog
            AuditLog.log_action(
                action='admin_access_denied',
                details='Unauthenticated user attempted admin access',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                status='failed'
            )
            return jsonify({'error': 'Authentication required'}), 401
        
        if not current_user.is_admin:
            # Log unauthorized admin access attempt
            from models import AuditLog
            AuditLog.log_action(
                action='admin_access_denied',
                user_id=current_user.id,
                details=f'Non-admin user {current_user.email} attempted admin access',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                status='failed'
            )
            return jsonify({'error': 'Admin privileges required'}), 403
        
        # Log successful admin access
        from models import AuditLog
        AuditLog.log_action(
            action='admin_access',
            user_id=current_user.id,
            details=f'Admin {current_user.email} accessed {request.endpoint}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            status='success'
        )
        
        return f(*args, **kwargs)
    return decorated_function

def validate_input(data, required_fields=None, max_lengths=None):
    """Validate input data"""
    if required_fields is None:
        required_fields = []
    if max_lengths is None:
        max_lengths = {}
    
    errors = []
    
    # Check required fields
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"{field} is required")
    
    # Check max lengths
    for field, max_length in max_lengths.items():
        if field in data and len(str(data[field])) > max_length:
            errors.append(f"{field} must be less than {max_length} characters")
    
    # Basic XSS prevention
    dangerous_patterns = ['<script', 'javascript:', 'vbscript:', 'onload=', 'onerror=']
    for field, value in data.items():
        if isinstance(value, str):
            for pattern in dangerous_patterns:
                if pattern.lower() in value.lower():
                    errors.append(f"Invalid characters detected in {field}")
                    break
    
    return errors

def sanitize_input(value):
    """Sanitize input value to prevent XSS and other attacks"""
    if value is None:
        return None
    
    # Convert to string
    value = str(value).strip()
    
    # Remove dangerous HTML/JS patterns
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',
        r'<iframe[^>]*>.*?</iframe>',
        r'javascript:',
        r'vbscript:',
        r'onload\s*=',
        r'onerror\s*=',
        r'onclick\s*=',
        r'onmouseover\s*=',
        r'eval\s*\(',
        r'expression\s*\(',
    ]
    
    for pattern in dangerous_patterns:
        value = re.sub(pattern, '', value, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove null bytes and control characters
    value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
    
    # Limit length to prevent DoS
    if len(value) > 10000:
        value = value[:10000]
    
    return value

def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    # Remove path traversal attempts
    filename = filename.replace('..', '').replace('/', '').replace('\\', '')
    
    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:255-len(ext)-1] + '.' + ext if ext else name[:255]
    
    return filename

def is_safe_url(target):
    """Check if a redirect URL is safe"""
    if not target:
        return False
    
    # Basic checks for safe URLs
    if target.startswith('//') or target.startswith('http://') or target.startswith('https://'):
        return False
    
    if target.startswith('/') and not target.startswith('//'):
        return True
    
    return False