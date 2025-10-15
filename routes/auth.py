"""
Authentication routes
"""
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, current_app, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy.exc import IntegrityError
from flask import make_response

from routes import db, bcrypt
from models import User, UserAddress, AuditLog
from security import validate_input, is_safe_url
from email_utils import send_email_sendlayer


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Combine first_name and last_name into full_name if they exist (for both JSON and form data)
        if 'first_name' in data and 'last_name' in data:
            data['full_name'] = f"{data['first_name'].strip()} {data['last_name'].strip()}"
        
        # Validate input
        required_fields = ['full_name', 'email', 'password']
        max_lengths = {
            'full_name': 100,
            'email': 120,
            'password': 128
        }
        
        errors = validate_input(data, required_fields, max_lengths)
        
        # Additional validation
        if len(data.get('password', '')) < 8:
            errors.append('Password must be at least 8 characters long')
        
        if '@' not in data.get('email', ''):
            errors.append('Please enter a valid email address')
        
        if errors:
            if request.is_json:
                return jsonify({'error': '; '.join(errors)}), 400
            else:
                flash('; '.join(errors), 'error')
                return redirect(url_for('main.index'))
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email'].lower().strip()).first()
        if existing_user:
            if request.is_json:
                return jsonify({'error': 'An account with this email already exists'}), 400
            else:
                flash('An account with this email already exists', 'error')
                return redirect(url_for('main.index'))
        
        # Create new user
        user = User(
            full_name=data['full_name'].strip(),
            email=data['email'].lower().strip()
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Log user registration
        try:
            AuditLog.log_action(
                action='user_registered',
                user_id=user.id,
                resource_type='user',
                resource_id=user.id,
                details=f'New user registered: {user.email}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                status='success'
            )
        except Exception as e:
            current_app.logger.error(f"Failed to log user registration: {e}")
        
        # Log the user in
        login_user(user, remember=True)
        
        # Update last login time
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log successful login after registration
        try:
            AuditLog.log_action(
                action='user_login',
                user_id=user.id,
                details=f'User logged in after registration: {user.email}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                status='success'
            )
        except Exception as e:
            current_app.logger.error(f"Failed to log user login after registration: {e}")
        
        # Send welcome email (optional)
        try:
            send_welcome_email(user)
        except Exception as e:
            current_app.logger.warning(f"Failed to send welcome email: {str(e)}")
        
        current_app.logger.info(f"New user registered: {user.email}")
        
        # Handle response based on request type
        if request.is_json:
            return jsonify({
                'message': 'Registration successful',
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'email': user.email
                }
            })
        else:
            flash('Registration successful! Welcome to LoveMeNow!', 'success')
            return redirect(url_for('main.index'))
    
    except IntegrityError:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': 'An account with this email already exists'}), 400
        else:
            flash('An account with this email already exists', 'error')
            return redirect(url_for('main.index'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        if request.is_json:
            return jsonify({'error': 'Registration failed. Please try again.'}), 500
        else:
            flash('Registration failed. Please try again.', 'error')
            return redirect(url_for('main.index'))

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Validate input
        required_fields = ['email', 'password']
        errors = validate_input(data, required_fields)
        
        if errors:
            if request.is_json:
                return jsonify({'error': '; '.join(errors)}), 400
            else:
                flash('; '.join(errors), 'error')
                return redirect(url_for('main.index'))
        
        # Find user
        user = User.query.filter_by(email=data['email'].lower().strip()).first()
        
        if not user or not user.check_password(data['password']):
            # Log failed login attempt
            try:
                AuditLog.log_action(
                    action='login_failed',
                    details=f'Failed login attempt for email: {data["email"]}',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    status='failed'
                )
            except Exception as e:
                current_app.logger.error(f"Failed to log failed login attempt: {e}")
            
            if request.is_json:
                return jsonify({'error': 'Invalid email or password'}), 401
            else:
                flash('Invalid email or password', 'error')
                return redirect(url_for('main.index'))
        
        # Log the user in
        remember = data.get('remember', False)
        login_user(user, remember=remember)
        
        # Update last login time
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log successful login
        try:
            AuditLog.log_action(
                action='user_login',
                user_id=user.id,
                details=f'User logged in: {user.email}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                status='success'
            )
        except Exception as e:
            current_app.logger.error(f"Failed to log successful login: {e}")
        
        # Merge guest cart/wishlist if exists
        merge_guest_data(user)
        
        current_app.logger.info(f"User logged in: {user.email}")
        
        # Get cart count after merge
        from models import Cart
        from sqlalchemy import func
        cart_count = (
            db.session.query(func.sum(Cart.quantity))
            .filter(Cart.user_id == user.id)
            .scalar() or 0
        )
        
        # Handle response based on request type
        if request.is_json:
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'email': user.email
                },
                'cart_count': int(cart_count)
            })
        else:
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('main.index'))
    
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        if request.is_json:
            return jsonify({'error': 'Login failed. Please try again.'}), 500
        else:
            flash('Login failed. Please try again.', 'error')
            return redirect(url_for('main.index'))

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    try:
        # Check if user is authenticated and log logout
        if current_user.is_authenticated:
            user_email = current_user.email
            user_id = current_user.id
            
            # Log successful logout
            try:
                AuditLog.log_action(
                    action='user_logout',
                    user_id=user_id,
                    details=f'User logged out: {user_email}',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    status='success'
                )
            except Exception as e:
                current_app.logger.error(f"Failed to log logout: {e}")
            
            current_app.logger.info(f"User logged out: {user_email}")
        else:
            current_app.logger.info("Logout called for non-authenticated user")
        
        # Preserve age verification after logout - user shouldn't need to verify age again
        # Age verification should persist for the browser session regardless of login status
        age_verified = session.get('age_verified', False)
        age_verification_date = session.get('age_verification_date')
        
        # Force logout and clear all session data
        logout_user()
        session.clear()
        
        # Restore age verification - once verified in this browser session, stay verified
        if age_verified:
            session['age_verified'] = True
            if age_verification_date:
                session['age_verification_date'] = age_verification_date
        
        # Create a new response with cleared cookies
        response = jsonify({'message': 'Logout successful'})
        
        # Clear Flask session cookie
        response.set_cookie('session', '', expires=0, path='/')
        
        # Clear any remember me cookies that Flask-Login might use
        response.set_cookie('remember_token', '', expires=0, path='/')
        
        # Also clear any custom cookies
        for cookie_name in ['user_id', 'auth_token', 'remember_me']:
            response.set_cookie(cookie_name, '', expires=0, path='/')
        
        return response
    
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@auth_bp.route('/status', methods=['GET'])
def auth_status():
    """Check current authentication status"""
    return jsonify({
        'authenticated': current_user.is_authenticated,
        'user_id': current_user.id if current_user.is_authenticated else None,
        'user_email': current_user.email if current_user.is_authenticated else None
    })

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['current_password', 'new_password']
        errors = validate_input(data, required_fields)
        
        if len(data.get('new_password', '')) < 8:
            errors.append('New password must be at least 8 characters long')
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        # Verify current password
        if not current_user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Update password
        current_user.set_password(data['new_password'])
        db.session.commit()
        
        current_app.logger.info(f"Password changed for user: {current_user.email}")
        
        return jsonify({'message': 'Password changed successfully'})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password change error: {str(e)}")
        return jsonify({'error': 'Failed to change password'}), 500

@auth_bp.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    """Delete user account"""
    try:
        # If POST, support JSON or form and require password
        if request.method == 'POST':
            data = request.get_json() or request.form.to_dict()
            if not data.get('password') or not current_user.check_password(data['password']):
                if request.is_json:
                    return jsonify({'error': 'Password is required to delete account'}), 400
                flash('Password is required to delete account', 'error')
                return redirect(url_for('main.settings'))
        
        user_email = current_user.email
        user_id = current_user.id
        
        # Delete user data (cascade should handle related records)
        db.session.delete(current_user)
        db.session.commit()
        
        # Logout user
        logout_user()
        session.clear()
        
        current_app.logger.info(f"Account deleted: {user_email}")
        
        # Respond appropriately based on request type
        if request.is_json:
            return jsonify({'message': 'Account deleted successfully'})
        else:
            return redirect(url_for('main.index'))
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Account deletion error: {str(e)}")
        if request.is_json:
            return jsonify({'error': 'Failed to delete account'}), 500
        else:
            flash('Failed to delete account', 'error')
            return redirect(url_for('main.settings'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Get or update user profile"""
    if request.method == 'GET':
        return jsonify({
            'user': {
                'id': current_user.id,
                'full_name': current_user.full_name,
                'email': current_user.email,
                'created_at': current_user.created_at.isoformat() if current_user.created_at else None
            }
        })
    
    try:
        data = request.get_json()
        
        # Validate input
        max_lengths = {'full_name': 100}
        errors = validate_input(data, max_lengths=max_lengths)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        # Update profile
        if 'full_name' in data:
            current_user.full_name = data['full_name'].strip()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': current_user.id,
                'full_name': current_user.full_name,
                'email': current_user.email
            }
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Profile update error: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

def merge_guest_data(user):
    """Merge guest cart and wishlist data with user account"""
    try:
        from models import Cart, Wishlist, Product
        
        # Merge cart data
        guest_cart = session.get('cart', {})
        for product_id_str, quantity in guest_cart.items():
            try:
                product_id = int(product_id_str)
                product = Product.query.get(product_id)
                
                if product:  # Allow merging regardless of stock status
                    existing_cart = Cart.query.filter_by(
                        user_id=user.id, 
                        product_id=product_id
                    ).first()
                    
                    if existing_cart:
                        existing_cart.quantity = min(
                            existing_cart.quantity + quantity,
                            product.quantity_on_hand
                        )
                    else:
                        cart_item = Cart(
                            user_id=user.id,
                            product_id=product_id,
                            quantity=min(quantity, product.quantity_on_hand)
                        )
                        db.session.add(cart_item)
            except (ValueError, TypeError):
                continue
        
        # Merge wishlist data
        guest_wishlist = session.get('wishlist', [])
        for product_id in guest_wishlist:
            try:
                product_id = int(product_id)
                existing_wishlist = Wishlist.query.filter_by(
                    user_id=user.id,
                    product_id=product_id
                ).first()
                
                if not existing_wishlist:
                    wishlist_item = Wishlist(
                        user_id=user.id,
                        product_id=product_id
                    )
                    db.session.add(wishlist_item)
            except (ValueError, TypeError):
                continue
        
        db.session.commit()
        
        # Clear guest data
        session.pop('cart', None)
        session.pop('wishlist', None)
        
    except Exception as e:
        current_app.logger.error(f"Error merging guest data: {str(e)}")
        db.session.rollback()

def send_welcome_email(user):
    """Send welcome email to new user"""
    try:
        current_app.logger.info(f"Attempting to send welcome email to {user.email}")

        subject = "Welcome to LoveMeNow!"
        html_content = f"""
        <h2>Welcome to LoveMeNow, {user.full_name}!</h2>
        <p>Thank you for joining our community. We're excited to have you!</p>
        <p>Start exploring our products and find something special for yourself or your loved ones.</p>
        <p>If you have any questions, feel free to contact our support team.</p>
        <p>Happy shopping!</p>
        <p>The LoveMeNow Team</p>
        """

        result = send_email_sendlayer(
            user.full_name or user.email,
            user.email,
            subject,
            html_content
        )
        current_app.logger.info(f"Welcome email queued/sent via SendLayer for {user.email}: {result}")

    except Exception as e:
        current_app.logger.warning(f"Failed to send welcome email: {str(e)}")

# Modal routes for backward compatibility
@auth_bp.route('/login_modal', methods=['GET', 'POST'])
def login_modal():
    """Login modal route"""
    if request.method == 'GET':
        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            session['next_page'] = next_page
        return redirect(url_for('main.index'))
    
    # Handle POST request (form submission)
    return login()

@auth_bp.route('/register_modal', methods=['GET', 'POST'])
def register_modal():
    """Register modal route"""
    if request.method == 'GET':
        return redirect(url_for('main.index'))
    
    # Handle POST request (form submission)
    return register()

@auth_bp.route('/settings')
@login_required
def settings():
    """User settings page"""
    return redirect(url_for('main.settings'))

@auth_bp.route('/save-address', methods=['POST'])
@login_required
def save_address():
    """Save user address"""
    try:
        data = request.get_json() or request.form.to_dict()
        
        # Validate input
        required_fields = ['street', 'city', 'state', 'zip']
        max_lengths = {
            'street': 200,
            'city': 100,
            'state': 50,
            'zip': 20
        }
        
        errors = validate_input(data, required_fields, max_lengths)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        # Create or update address
        address = UserAddress(
            user_id=current_user.id,
            street=data['street'].strip(),
            city=data['city'].strip(),
            state=data['state'].strip(),
            zip_code=data['zip'].strip(),
            is_default=data.get('is_default', False)
        )
        
        # If this is set as default, unset other defaults
        if address.is_default:
            UserAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        
        db.session.add(address)
        db.session.commit()
        
        return jsonify({'message': 'Address saved successfully'})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Save address error: {str(e)}")
        return jsonify({'error': 'Failed to save address'}), 500

@auth_bp.route('/add-address', methods=['POST'])
@login_required
def add_address():
    """Add new user address"""
    try:
        data = request.get_json() or request.form.to_dict()
        
        # Validate input
        required_fields = ['addr1', 'city', 'state', 'zip']
        max_lengths = {
            'addr1': 200,
            'addr2': 100,
            'city': 100,
            'state': 50,
            'zip': 20,
            'country': 50
        }
        
        errors = validate_input(data, required_fields, max_lengths)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        # Create new address
        address = UserAddress(
            user_id=current_user.id,
            address=data['addr1'].strip(),
            suite=data.get('addr2', '').strip() if data.get('addr2') else None,
            city=data['city'].strip(),
            state=data['state'].strip(),
            zip=data['zip'].strip(),
            country=data.get('country', 'US').strip(),
            is_default=data.get('is_default', False)
        )
        
        # If this is set as default, unset other defaults
        if address.is_default:
            UserAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        
        db.session.add(address)
        db.session.commit()
        
        current_app.logger.info(f"Address added for user: {current_user.email}")
        
        return jsonify({'success': True, 'message': 'Address added successfully'})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Add address error: {str(e)}")
        return jsonify({'error': 'Failed to add address'}), 500

@auth_bp.route('/age-verification')
def age_verification():
    """Show age verification page"""
    from flask import render_template
    
    current_app.logger.info(f"Age verification page accessed. Session: {dict(session)}")
    
    # If user is already age verified, redirect to intended page
    if 'age_verified' in session and session['age_verified']:
        next_page = request.args.get('next', url_for('main.index'))
        current_app.logger.info(f"User already verified, redirecting to: {next_page}")
        if is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for('main.index'))
    
    current_app.logger.info("Showing age verification template")
    return render_template('age_verification.html')

# routes/auth.py


@auth_bp.route('/verify-age', methods=['POST'])
def verify_age():
    try:
        # Read from form, but also accept ?next=... from the query as fallback
        form = request.form
        verified = (form.get('verified') == 'true')
        next_page = form.get('next') or request.args.get('next') or url_for('main.index')
        if not is_safe_url(next_page):
            next_page = url_for('main.index')

        if verified:
            # Mark session
            session['age_verified'] = True
            session['age_verification_date'] = datetime.utcnow().isoformat()
            session.modified = True

            # Persist on user if logged in
            if current_user.is_authenticated:
                current_user.age_verified = True
                current_user.age_verification_date = datetime.utcnow()
                db.session.commit()

            # Build redirect response
            resp = make_response(redirect(next_page))

            # Long-lived "age verified" cookie (read by server if you need it)
            resp.set_cookie(
                'age_verified',
                '1',
                max_age=60 * 60 * 24 * 365,  # 1 year
                path='/',
                samesite='Lax',
                secure=request.is_secure,     # True on HTTPS
                httponly=False                # keep False so client code can read if desired
            )

            # 🔑 Short-lived ONE-TIME promo trigger cookie (read by promo_modal.js)
            # promo_modal.js will erase this cookie after showing the modal once.
            resp.set_cookie(
                'lmn_show_promo',
                '1',
                max_age=300,                  # 5 minutes is plenty
                path='/',
                samesite='Lax',
                secure=request.is_secure,
                httponly=False                # must be readable by JS
            )

            return resp

        # Not verified (under age path)
        return redirect('https://www.google.com')

    except Exception as e:
        current_app.logger.error(f"Age verification error: {e}")
        # Preserve ?next on error so user can complete flow
        fallback_next = request.args.get('next') or url_for('main.index')
        return redirect(url_for('auth.age_verification', next=fallback_next))



def require_age_verification(f):
    """Decorator to require age verification for routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if age verification is required - ONLY check session
        if not session.get('age_verified'):
            # Redirect to age verification (regardless of login status)
            return redirect(url_for('auth.age_verification', next=request.url))
        
        return f(*args, **kwargs)
    return decorated_function