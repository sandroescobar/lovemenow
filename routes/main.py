"""
Main application routes
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from sqlalchemy import func, desc
from sqlalchemy.exc import OperationalError, DisconnectionError
import stripe
import stripe.checkout

from routes import db, csrf
from models import Product, Category, Color, Wishlist, Cart, Order, OrderItem, UberDelivery
from security import validate_input
from database_utils import retry_db_operation, test_database_connection, get_fallback_data

main_bp = Blueprint('main', __name__)

# Health check endpoint for Render
@main_bp.route('/api/health')
def health_check():
    """Health check endpoint for deployment monitoring"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': db.func.now()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 503

# Age verification decorator
def require_age_verification(f):
    """Decorator to require age verification for routes"""
    from functools import wraps
    from flask import session, redirect, url_for, request
    from flask_login import current_user
    from datetime import datetime
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import current_app
        
        # Check age verification - ONLY check session, not user database record
        age_verified = session.get('age_verified', False)
        
        # Require verification if not in session (regardless of login status)
        if not age_verified:
            return redirect(url_for('auth.age_verification', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    """Home page with featured products"""
    try:
        # Check if age verification is needed
        age_verified = session.get('age_verified', False)
        
        # For logged-in users: check if they have age verification in their user record
        if current_user.is_authenticated and hasattr(current_user, 'age_verified') and current_user.age_verified:
            # User is logged in and has been age verified before - set session
            session['age_verified'] = True
            age_verified = True
        
        # Test database connection first
        db_connected, db_message = test_database_connection()
        
        if not db_connected:
            current_app.logger.warning(f"Database connection failed: {db_message}")
            # Use fallback data when database is unavailable
            fallback_data = get_fallback_data()
            return render_template('index.html',
                                 featured_products=fallback_data['featured_products'],
                                 categories=fallback_data['categories'],
                                 cart_count=fallback_data['cart_count'],
                                 wishlist_count=fallback_data['wishlist_count'],
                                 db_error=True,
                                 show_age_verification=not age_verified)
        
        # Get featured products (limit to 3)
        featured_products = (
            Product.query
            .filter(Product.in_stock == True, Product.quantity_on_hand > 0)
            .options(joinedload(Product.images))
            .limit(3)
            .all()
        )
        
        # Get categories for navigation
        categories = Category.query.filter(Category.parent_id.is_(None)).all()
        
        # Get cart and wishlist counts for logged-in users
        cart_count = 0
        wishlist_count = 0
        
        if current_user.is_authenticated:
            cart_count = db.session.query(func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
            wishlist_count = Wishlist.query.filter_by(user_id=current_user.id).count()
        else:
            # For guest users, get from session
            cart_count = sum(session.get('cart', {}).values())
            wishlist_count = len(session.get('wishlist', []))
        
        return render_template('index.html',
                             featured_products=featured_products,
                             categories=categories,
                             cart_count=cart_count,
                             wishlist_count=wishlist_count,
                             show_age_verification=not age_verified)
    
    except (OperationalError, DisconnectionError) as e:
        current_app.logger.error(f"Database connection error on home page: {str(e)}")
        # Check age verification for fallback case too
        age_verified = session.get('age_verified', False)
        
        # For logged-in users: check if they have age verification in their user record
        if current_user.is_authenticated and hasattr(current_user, 'age_verified') and current_user.age_verified:
            session['age_verified'] = True
            age_verified = True
        
        # Use fallback data when database connection fails
        fallback_data = get_fallback_data()
        return render_template('index.html',
                             featured_products=fallback_data['featured_products'],
                             categories=fallback_data['categories'],
                             cart_count=fallback_data['cart_count'],
                             wishlist_count=fallback_data['wishlist_count'],
                             db_error=True,
                             show_age_verification=not age_verified)
    
    except Exception as e:
        current_app.logger.error(f"Error loading home page: {str(e)}")
        return render_template('errors/500.html'), 500

@main_bp.route('/products')
@require_age_verification
def products():
    """Products listing page with filtering and pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50  # Show more products per page
        
        # Build query - show all products including out of stock
        query = Product.query
        
        # Apply filters
        category_id = request.args.get('category', type=int)
        if category_id:
            # Get the category and check if it has children
            category = Category.query.get(category_id)
            if category:
                if category.children:
                    # If it's a parent category, include products from all subcategories
                    subcategory_ids = [child.id for child in category.children]
                    subcategory_ids.append(category_id)  # Include parent category itself
                    query = query.filter(Product.category_id.in_(subcategory_ids))
                else:
                    # If it's a subcategory, just filter by that category
                    query = query.filter(Product.category_id == category_id)
        
        color_id = request.args.get('color', type=int)
        if color_id:
            query = query.join(Product.colors).filter(Color.id == color_id)
        
        min_price = request.args.get('min_price', type=float)
        if min_price:
            query = query.filter(Product.price >= min_price)
        
        max_price = request.args.get('max_price', type=float)
        if max_price:
            query = query.filter(Product.price <= max_price)
        
        search = request.args.get('search', '').strip()
        if search:
            # Validate search input
            errors = validate_input({'search': search}, max_lengths={'search': 100})
            if not errors:
                query = query.filter(Product.name.contains(search))
        
        # In stock filter
        in_stock_only = request.args.get('in_stock', '').lower() == 'true'
        if in_stock_only:
            query = query.filter(Product.in_stock == True, Product.quantity_on_hand > 0)
        
        # Brand filter (extract from product name)
        brand = request.args.get('brand', '').strip()
        if brand:
            query = query.filter(Product.name.ilike(f'{brand}%'))
        
        # Apply sorting
        sort_by = request.args.get('sort', 'name')
        if sort_by == 'low-high':
            query = query.order_by(Product.price.asc())
        elif sort_by == 'high-low':
            query = query.order_by(Product.price.desc())
        elif sort_by == 'newest':
            query = query.order_by(desc(Product.id))
        else:
            query = query.order_by(Product.name.asc())
        
        # Paginate results
        products = query.options(joinedload(Product.images)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Get filter options - only main categories (parent categories) with their children
        categories = Category.query.filter(Category.parent_id.is_(None)).options(joinedload(Category.children)).all()
        colors = Color.query.join(Color.products).distinct().all()
        
        return render_template('products.html',
                             products=products,
                             categories=categories,
                             colors=colors,
                             current_filters={
                                 'category': category_id,
                                 'color': color_id,
                                 'min_price': min_price,
                                 'max_price': max_price,
                                 'search': search,
                                 'sort': sort_by,
                                 'in_stock': in_stock_only,
                                 'brand': brand
                             })
    
    except Exception as e:
        current_app.logger.error(f"Error loading products page: {str(e)}")
        return render_template('errors/500.html'), 500

@main_bp.route('/product/<int:product_id>')
@require_age_verification
def product_detail(product_id):
    """Product detail page"""
    try:
        product = (
            Product.query
            .options(joinedload(Product.images), joinedload(Product.colors))
            .get_or_404(product_id)
        )
        
        # Get related products from same category
        related_products = (
            Product.query
            .filter(Product.category_id == product.category_id)
            .filter(Product.id != product_id)
            .filter(Product.in_stock == True, Product.quantity_on_hand > 0)
            .limit(4)
            .all()
        )
        
        return render_template('product_detail.html',
                             product=product,
                             related_products=related_products)
    
    except Exception as e:
        current_app.logger.error(f"Error loading product detail: {str(e)}")
        return render_template('errors/404.html'), 404

@main_bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@main_bp.route('/support')
def support():
    """Support page"""
    return render_template('support.html')

@main_bp.route('/return')
def return_policy():
    """Return policy page"""
    return render_template('return.html')

@main_bp.route('/test-age-verification')
@require_age_verification
def test_age_verification():
    """Test route to verify age verification is working"""
    from flask import session
    return f"""
    <h1>Age Verification Working!</h1>
    <p>If you can see this page, age verification is working correctly.</p>
    <p>Session age_verified: {session.get('age_verified', 'Not set')}</p>
    <p>User authenticated: {current_user.is_authenticated}</p>
    {f'<p>User age_verified: {current_user.age_verified}</p>' if current_user.is_authenticated and hasattr(current_user, 'age_verified') else ''}
    <a href="{url_for('main.index')}">Back to Home</a> | 
    <a href="{url_for('main.clear_age_verification')}">Clear Age Verification (for testing)</a>
    """

@main_bp.route('/clear-age-verification')
def clear_age_verification():
    """Clear age verification for testing purposes ONLY"""
    from flask import session
    
    # Clear the entire session to simulate fresh browser visit
    session.clear()
    
    # If user is logged in, also clear their age verification in database
    if current_user.is_authenticated:
        current_user.age_verified = False
        current_user.age_verification_date = None
        db.session.commit()
    
    current_app.logger.info("🧹 Complete session cleared for testing (simulates fresh browser)")
    return f"""
    <h1>Session Completely Cleared (Testing Only)</h1>
    <p><strong>⚠️ This simulates a fresh browser visit!</strong></p>
    <p>Your entire session has been cleared - this simulates closing and reopening your browser.</p>
    <p><strong>What should happen next:</strong></p>
    <ol>
        <li>Click the link below</li>
        <li>You should immediately see the age verification modal</li>
        <li>The page should be blocked (no scrolling)</li>
        <li>Click "I am 18+" to proceed</li>
        <li>After verification, you can browse freely until you clear session again</li>
    </ol>
    <a href="{url_for('main.index')}" style="font-size: 18px; color: blue;">Go to Home (should show age verification)</a>
    """

@main_bp.route('/debug-session')
def debug_session():
    """Debug route to check session state"""
    from flask import session
    return f"""
    <h1>Session Debug</h1>
    <p><strong>Session contents:</strong> {dict(session)}</p>
    <p><strong>Age verified in session:</strong> {session.get('age_verified', 'Not set')}</p>
    <p><strong>User authenticated:</strong> {current_user.is_authenticated}</p>
    {f'<p><strong>User age_verified:</strong> {getattr(current_user, "age_verified", "No attribute")}</p>' if current_user.is_authenticated else ''}
    <hr>
    <a href="{url_for('main.test_age_verification')}">Test Age Verification</a> | 
    <a href="{url_for('main.clear_age_verification')}">Clear Age Verification</a> | 
    <a href="{url_for('main.simple_redirect_test')}">Simple Redirect Test</a> | 
    <a href="{url_for('main.index')}">Back to Home</a>
    """

@main_bp.route('/simple-redirect-test')
def simple_redirect_test():
    """Simple test to see if redirect to age verification works"""
    from flask import session
    if not session.get('age_verified'):
        return redirect(url_for('auth.age_verification', next=request.url))
    return "<h1>Redirect Test Passed!</h1><p>You are age verified.</p>"

@main_bp.route('/test-session')
def test_session():
    """Test if sessions are working at all"""
    from flask import session
    
    # Try to set and read a test session value
    if 'test_counter' not in session:
        session['test_counter'] = 1
    else:
        session['test_counter'] += 1
    
    return f"""
    <h1>Session Test</h1>
    <p><strong>Session working:</strong> {'✅ YES' if 'test_counter' in session else '❌ NO'}</p>
    <p><strong>Test counter:</strong> {session.get('test_counter', 'Not set')}</p>
    <p><strong>Session ID:</strong> {request.cookies.get('session', 'No session cookie')}</p>
    <p><strong>All cookies:</strong> {dict(request.cookies)}</p>
    <p><strong>Age verified:</strong> {session.get('age_verified', 'Not set')}</p>
    <hr>
    <a href="{url_for('main.test_session')}">Refresh (increment counter)</a> | 
    <a href="{url_for('main.debug_session')}">Debug Session</a> | 
    <a href="{url_for('main.clear_age_verification')}">Clear Session</a> | 
    <a href="{url_for('main.index')}">Go to Home</a>
    """

@main_bp.route('/force-age-verification')
def force_age_verification():
    """Force redirect to age verification"""
    return redirect(url_for('auth.age_verification', next=url_for('main.index')))

@main_bp.route('/checkout')
@require_age_verification
def checkout():
    """Enhanced checkout page with Uber Direct integration"""
    # Simple checkout - no complex redirect logic
    
    # Check if cart has items
    cart_items = []
    if current_user.is_authenticated:
        # Get cart from database for logged-in users
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    else:
        # Get cart from session for guest users
        cart_data = session.get('cart', {})
        if cart_data:
            for product_id, quantity in cart_data.items():
                try:
                    product = Product.query.get(int(product_id))
                    if product:
                        cart_items.append({
                            'product': product,
                            'quantity': quantity
                        })
                except (ValueError, TypeError):
                    continue
    
    # If cart is empty, redirect to cart page - simple and predictable
    if not cart_items:
        return redirect(url_for('main.cart_page'))
    
    # Debug configuration
    current_app.logger.info(f"Stripe publishable key: {current_app.config.get('STRIPE_PUBLISHABLE_KEY', 'NOT SET')}")
    current_app.logger.info(f"Stripe secret key: {current_app.config.get('STRIPE_SECRET_KEY', 'NOT SET')[:10]}..." if current_app.config.get('STRIPE_SECRET_KEY') else "NOT SET")
    
    # Prepare cart data for template
    cart_data = {
        'items': [],
        'subtotal': 0,
        'shipping': 0,
        'total': 0,
        'count': 0
    }
    
    if current_user.is_authenticated:
        # Get cart from database for logged-in users
        from sqlalchemy.orm import joinedload
        cart_items_db = (
            db.session.query(Cart, Product)
            .join(Product)
            .filter(Cart.user_id == current_user.id)
            .options(joinedload(Cart.product))
            .all()
        )
        
        for cart_item, product in cart_items_db:
            item_total = float(product.price) * cart_item.quantity
            cart_data['subtotal'] += item_total
            
            cart_data['items'].append({
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'quantity': cart_item.quantity,
                'image_url': product.main_image_url,
                'description': product.description or '',
                'in_stock': product.is_available,
                'max_quantity': product.quantity_on_hand,
                'item_total': item_total
            })
    else:
        # Get cart from session for guest users
        cart_session = session.get('cart', {})
        if cart_session:
            cart_products = Product.query.filter(Product.id.in_(cart_session.keys())).all()
            for product in cart_products:
                quantity = cart_session[str(product.id)]
                item_total = float(product.price) * quantity
                cart_data['subtotal'] += item_total
                
                cart_data['items'].append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price),
                    'quantity': quantity,
                    'image_url': product.main_image_url,
                    'description': product.description or '',
                    'in_stock': product.is_available,
                    'max_quantity': product.quantity_on_hand,
                    'item_total': item_total
                })
    
    # Calculate shipping
    cart_data['shipping'] = 9.99 if cart_data['subtotal'] > 0 and cart_data['subtotal'] < 50 else 0
    cart_data['total'] = cart_data['subtotal'] + cart_data['shipping']
    cart_data['count'] = len(cart_data['items'])
    
    # Use enhanced checkout template with delivery options
    try:
        current_app.logger.info("Attempting to render checkout_enhanced.html template")
        current_app.logger.info(f"Cart data: {cart_data}")
        current_app.logger.info(f"Config keys: {list(current_app.config.keys())}")
        return render_template('checkout_enhanced.html', config=current_app.config, cart_data=cart_data)
    except Exception as e:
        current_app.logger.error(f"Error rendering checkout template: {str(e)}")
        # Fallback to a simple error page
        return f"""
        <h1>Checkout Template Error</h1>
        <p>Error: {str(e)}</p>
        <p>Template folder: {current_app.template_folder}</p>
        <p><a href="/template-debug">Check Available Templates</a></p>
        <p><a href="/checkout-simple">Try Simple Checkout</a></p>
        """

@main_bp.route('/checkout-simple')
def checkout_simple():
    """Simple checkout page for debugging"""
    return render_template('checkout_simple.html', config=current_app.config)

@main_bp.route('/stripe-debug')
def stripe_debug():
    """Stripe configuration debug page"""
    return render_template('stripe_debug.html', config=current_app.config)

@main_bp.route('/template-debug')
def template_debug():
    """Debug which templates are available"""
    import os
    from flask import current_app
    
    template_folder = current_app.template_folder
    templates = []
    
    if os.path.exists(template_folder):
        for root, dirs, files in os.walk(template_folder):
            for file in files:
                if file.endswith('.html'):
                    rel_path = os.path.relpath(os.path.join(root, file), template_folder)
                    templates.append(rel_path)
    
    return f"""
    <h1>Template Debug</h1>
    <h2>Template Folder: {template_folder}</h2>
    <h2>Available Templates:</h2>
    <ul>
        {''.join([f'<li>{template}</li>' for template in sorted(templates)])}
    </ul>
    <h2>Looking for:</h2>
    <ul>
        <li>checkout_enhanced.html - {'✅ Found' if 'checkout_enhanced.html' in templates else '❌ Missing'}</li>
        <li>stripe_debug.html - {'✅ Found' if 'stripe_debug.html' in templates else '❌ Missing'}</li>
        <li>checkout_simple.html - {'✅ Found' if 'checkout_simple.html' in templates else '❌ Missing'}</li>
    </ul>
    <p><a href="/checkout">Test Checkout</a> | <a href="/stripe-debug">Stripe Debug</a> | <a href="/checkout-simple">Simple Checkout</a></p>
    """

@main_bp.route('/test-config')
def test_config():
    """Test configuration endpoint"""
    return jsonify({
        'stripe_publishable_key': current_app.config.get('STRIPE_PUBLISHABLE_KEY', 'NOT SET'),
        'stripe_secret_key_set': bool(current_app.config.get('STRIPE_SECRET_KEY')),
        'stripe_secret_key_preview': current_app.config.get('STRIPE_SECRET_KEY', 'NOT SET')[:10] + '...' if current_app.config.get('STRIPE_SECRET_KEY') else 'NOT SET',
        'flask_env': current_app.config.get('FLASK_ENV', 'NOT SET'),
        'debug_mode': current_app.debug,
        'config_keys': list(current_app.config.keys())
    })

@main_bp.route('/test-stripe')
def test_stripe():
    """Test Stripe integration endpoint"""
    try:
        # Set Stripe API key
        stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not stripe_secret_key:
            return jsonify({'error': 'Stripe secret key not configured'}), 500
        
        stripe.api_key = stripe_secret_key
        
        # Create a test session
        test_session = stripe.checkout.Session.create(
            ui_mode='embedded',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Test Product',
                        'description': 'Test product for debugging',
                    },
                    'unit_amount': 2999,  # $29.99 in cents
                },
                'quantity': 1,
            }],
            mode='payment',
            return_url=request.host_url + 'checkout-success?session_id={CHECKOUT_SESSION_ID}',
        )
        
        return jsonify({
            'success': True,
            'session_id': test_session.id,
            'client_secret': test_session.client_secret[:20] + '...',
            'session_type': str(type(test_session))
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@main_bp.route('/checkout-success')
def checkout_success():
    """Checkout success page - shows when user returns from Uber tracking"""
    order_id = request.args.get('order_id')
    session_id = request.args.get('session_id')
    
    if not order_id and not session_id:
        return redirect(url_for('main.index'))
    
    try:
        # Get the actual order from database with all related data
        order = None
        
        if order_id:
            order = Order.query.options(
                joinedload(Order.items).joinedload(OrderItem.product).joinedload(Product.images)
            ).get(order_id)
        
        if not order:
            current_app.logger.warning(f"Order {order_id} not found, redirecting to home")
            return redirect(url_for('main.index'))
        
        # Get order items with product details
        order_items = []
        for item in order.items:
            product = item.product
            if product:
                # Get product image
                product_image = None
                if product.image_url:
                    product_image = product.image_url
                elif product.images:
                    product_image = product.images[0].url
                
                order_items.append({
                    'product': product,
                    'quantity': item.quantity,
                    'unit_price': item.price,
                    'total_price': item.total,
                    'product_image': product_image
                })
        
        # Check if this order has Uber tracking
        uber_delivery = UberDelivery.query.filter_by(order_id=order.id).first()
        
        # Clear the recent order from session for all users
        if session.get('recent_order_id') == int(order_id):
            session.pop('recent_order_id', None)
        

        
        return render_template('checkout_success.html', 
                             order=order, 
                             order_items=order_items,
                             uber_delivery=uber_delivery)
        
    except Exception as e:
        current_app.logger.error(f"Error loading order: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return redirect(url_for('main.index'))

# Removed custom uber-tracking route - we only use REAL Uber tracking URLs

@main_bp.route('/track-orders', methods=['GET', 'POST'])
def track_orders():
    """Track ongoing orders - accessible to all users"""
    try:
        # Handle POST request for guest order tracking
        if request.method == 'POST':
            order_number = request.form.get('order_number', '').strip()
            if order_number:
                from models import Order, UberDelivery
                order = Order.query.filter_by(order_number=order_number).first()
                if order:
                    uber_delivery = UberDelivery.query.filter_by(order_id=order.id).first()
                    return render_template('track_orders.html', 
                                         orders_with_tracking=[{
                                             'order': order,
                                             'uber_delivery': uber_delivery
                                         }],
                                         searched_order=order_number)
                else:
                    return render_template('track_orders.html', 
                                         orders_with_tracking=None,
                                         error_message=f"Order {order_number} not found")
        
        # For logged-in users, show their orders
        if current_user.is_authenticated:
            from models import Order, UberDelivery
            orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(10).all()
            
            # Get Uber delivery info for each order
            orders_with_tracking = []
            for order in orders:
                try:
                    uber_delivery = UberDelivery.query.filter_by(order_id=order.id).first()
                    orders_with_tracking.append({
                        'order': order,
                        'uber_delivery': uber_delivery
                    })
                except:
                    orders_with_tracking.append({
                        'order': order,
                        'uber_delivery': None
                    })
            
            return render_template('track_orders.html', orders_with_tracking=orders_with_tracking)
        else:
            # For guest users, show a form to track by order number
            return render_template('track_orders.html', orders_with_tracking=None)
        
    except Exception as e:
        current_app.logger.error(f"Error loading track orders: {str(e)}")
        return render_template('track_orders.html', orders_with_tracking=[])

@main_bp.route('/my-orders')
@login_required
def my_orders():
    """Display user's order history and status"""
    from models import Order
    
    # Get user's orders with delivery information
    orders = (Order.query
              .filter_by(user_id=current_user.id)
              .order_by(Order.created_at.desc())
              .all())
    
    return render_template('order_status.html', orders=orders)

@main_bp.route('/create-checkout-session', methods=['POST'])
@csrf.exempt
def create_checkout_session():
    """Create Stripe checkout session"""
    try:
        # Get Stripe API key from config with better error handling
        stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
        
        # Debug logging
        current_app.logger.info(f"Config keys available: {list(current_app.config.keys())}")
        current_app.logger.info(f"Stripe secret key from config: {stripe_secret_key[:10] if stripe_secret_key else 'None'}...")
        
        # Verify Stripe is properly configured
        if not stripe_secret_key:
            current_app.logger.error("Stripe API key is not set in configuration")
            return jsonify({'error': 'Payment system not configured - missing API key'}), 500
            
        # Set Stripe API key
        stripe.api_key = stripe_secret_key
        
        # Verify the key was set correctly
        if not stripe.api_key:
            current_app.logger.error("Stripe API key is still not set after assignment")
            return jsonify({'error': 'Payment system not configured'}), 500
            
        # Verify Stripe is properly imported
        try:
            current_app.logger.info("Testing Stripe import...")
            test_session = stripe.checkout.Session
            current_app.logger.info("Stripe checkout.Session is available")
        except Exception as e:
            current_app.logger.error(f"Stripe import error: {e}")
            return jsonify({'error': f'Payment system not available: {str(e)}'}), 500
        
        # Get cart data - simplified approach
        current_app.logger.info("Loading cart data...")
        cart_items = []
        
        try:
            if current_user.is_authenticated:
                # Get cart from database
                db_cart_items = Cart.query.filter_by(user_id=current_user.id).all()
                cart_items = db_cart_items
                current_app.logger.info(f"Found {len(cart_items)} items in user cart")
            else:
                # Get cart from session
                cart_data = session.get('cart', {})
                current_app.logger.info(f"Session cart data: {cart_data}")
                for product_id, quantity in cart_data.items():
                    product = Product.query.get(int(product_id))
                    if product:
                        # Create a simple cart item object
                        cart_item = type('CartItem', (), {
                            'product': product,
                            'quantity': quantity
                        })()
                        cart_items.append(cart_item)
                current_app.logger.info(f"Found {len(cart_items)} items in session cart")
                    
        except Exception as e:
            current_app.logger.error(f"Error getting cart data: {e}")
            # Create fallback mock product
            current_app.logger.info("Using fallback mock product due to cart error")
            mock_product = type('Product', (), {
                'id': 1,
                'name': 'Test Product',
                'description': 'Test product for checkout',
                'price': 29.99
            })()
            cart_item = type('CartItem', (), {
                'product': mock_product,
                'quantity': 1
            })()
            cart_items = [cart_item]
        
        # If cart is empty, create a test item for checkout testing
        if not cart_items:
            current_app.logger.info("Cart is empty, creating test product for checkout")
            # Create mock product for testing
            mock_product = type('Product', (), {
                'id': 1,
                'name': 'Test Product',
                'description': 'Test product for checkout',
                'price': 29.99
            })()
            cart_item = type('CartItem', (), {
                'product': mock_product,
                'quantity': 1
            })()
            cart_items = [cart_item]
            current_app.logger.info("Created test product for checkout")
        
        # Calculate totals
        current_app.logger.info("Calculating totals and creating line items...")
        line_items = []
        subtotal = 0
        
        for item in cart_items:
            if hasattr(item, 'product'):
                # Database cart item
                product = item.product
                quantity = item.quantity
            else:
                # Session cart item
                product = item['product']
                quantity = item['quantity']
            
            price_cents = int(product.price * 100)  # Convert to cents
            subtotal += product.price * quantity
            
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name,
                        'description': product.description[:100] if product.description else '',
                    },
                    'unit_amount': price_cents,
                },
                'quantity': quantity,
            })
        
        # Add shipping if needed
        if subtotal < 100:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Shipping',
                        'description': 'Standard shipping',
                    },
                    'unit_amount': 999,  # $9.99 in cents
                },
                'quantity': 1,
            })
        
        # Create Stripe checkout session for embedded checkout
        current_app.logger.info("Creating Stripe checkout session...")
        current_app.logger.info(f"Line items: {line_items}")
        
        # Prepare metadata with cart information for webhook processing
        cart_metadata = {}
        for i, item in enumerate(cart_items):
            if hasattr(item, 'product'):
                # Database cart item
                product = item.product
                quantity = item.quantity
            else:
                # Session cart item
                product = item['product']
                quantity = item['quantity']
            
            cart_metadata[f'item_{i}_product_id'] = str(product.id)
            cart_metadata[f'item_{i}_quantity'] = str(quantity)
        
        cart_metadata['item_count'] = str(len(cart_items))
        if current_user.is_authenticated:
            cart_metadata['user_id'] = str(current_user.id)
        
        # Calculate total amount in cents
        total_amount = 0
        for item in line_items:
            total_amount += item['price_data']['unit_amount'] * item['quantity']
        
        current_app.logger.info(f"Total amount in cents: {total_amount}")
        
        try:
            # Create Stripe Checkout Session for Embedded Checkout
            current_app.logger.info("Creating Stripe Checkout Session for Embedded Checkout...")
            
            checkout_session = stripe.checkout.Session.create(
                ui_mode='embedded',
                line_items=line_items,
                mode='payment',
                return_url=request.url_root + 'checkout/return?session_id={CHECKOUT_SESSION_ID}',
                metadata=cart_metadata,
                automatic_tax={'enabled': True},
                shipping_address_collection={'allowed_countries': ['US']},
                billing_address_collection='required',
            )
            
            current_app.logger.info(f"Checkout Session created successfully: {checkout_session.id}")
            
            # Return the client secret
            client_secret = checkout_session.client_secret
            if client_secret:
                current_app.logger.info(f"Client secret obtained successfully: {client_secret[:20]}...")
                
                # Debug: Log the full client secret to check for encoding issues
                current_app.logger.info(f"Full client secret (first 50 chars): {client_secret[:50]}")
                current_app.logger.info(f"Client secret type: {type(client_secret)}")
                
                # Aggressively decode the client secret (it's getting encoded somewhere)
                import urllib.parse
                import json
                
                current_app.logger.info(f"🔍 Raw client secret from Stripe: {repr(client_secret)}")
                
                # Try multiple decoding attempts
                decoded_secret = client_secret
                decode_attempts = 0
                max_attempts = 3
                
                while decode_attempts < max_attempts:
                    try:
                        before_decode = decoded_secret
                        decoded_secret = urllib.parse.unquote(decoded_secret)
                        decode_attempts += 1
                        
                        current_app.logger.info(f"🔄 Decode attempt {decode_attempts}:")
                        current_app.logger.info(f"   Before: {before_decode[:50]}...")
                        current_app.logger.info(f"   After:  {decoded_secret[:50]}...")
                        
                        # If no change, we're done
                        if before_decode == decoded_secret:
                            current_app.logger.info("✅ No more decoding needed")
                            break
                            
                        # If it looks valid and has no encoding, we're done
                        if decoded_secret.startswith('cs_') and '_secret_' in decoded_secret and '%' not in decoded_secret:
                            current_app.logger.info("✅ Valid client secret format achieved")
                            break
                            
                    except Exception as decode_error:
                        current_app.logger.error(f"❌ Decode attempt {decode_attempts + 1} failed: {decode_error}")
                        break
                
                client_secret = decoded_secret
                current_app.logger.info(f"🎯 Final client secret: {client_secret[:50]}...")
                
                # Validate client secret format
                if not (client_secret.startswith('cs_') and '_secret_' in client_secret):
                    current_app.logger.error(f"❌ Invalid client secret format: {client_secret[:50]}...")
                    return jsonify({'error': 'Invalid client secret format'}), 500
                
                current_app.logger.info("✅ Client secret format is valid")
                
                # Create response with explicit JSON encoding to prevent further encoding
                response_data = {'clientSecret': client_secret}
                
                # Use explicit JSON response to avoid any middleware encoding
                from flask import Response
                response = Response(
                    json.dumps(response_data, ensure_ascii=False),
                    mimetype='application/json',
                    headers={
                        'Content-Type': 'application/json; charset=utf-8',
                        'Cache-Control': 'no-cache, no-store, must-revalidate'
                    }
                )
                
                current_app.logger.info(f"📤 Sending response: {json.dumps(response_data)[:100]}...")
                return response
            else:
                current_app.logger.error("No client secret found in Checkout Session")
                return jsonify({'error': 'No client secret found in Checkout Session'}), 500
            
        except Exception as checkout_error:
            current_app.logger.error(f"Error creating Checkout Session: {checkout_error}")
            import traceback
            current_app.logger.error(f"Checkout Session error traceback: {traceback.format_exc()}")
            return jsonify({'error': f'Failed to create Checkout Session: {str(checkout_error)}'}), 500
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Error creating checkout session: {str(e)}")
        current_app.logger.error(f"Full traceback: {error_details}")

        
        # Check if the error is related to the client_secret access
        if "'NoneType' object has no attribute 'Secret'" in str(e):
            current_app.logger.error("Error seems to be related to client_secret access")
            current_app.logger.error(f"Full error: {str(e)}")
            current_app.logger.error(f"Error type: {type(e)}")
            # Don't return here, let it fall through to see the actual error
        
        return jsonify({'error': f'Failed to create checkout session: {str(e)}'}), 500

@main_bp.route('/checkout/return')
def checkout_return():
    """Handle return from Stripe embedded checkout"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        flash('Invalid checkout session', 'error')
        return redirect(url_for('main.index'))
    
    try:
        # Retrieve the checkout session
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == 'paid':
            # Payment successful
            flash('Payment successful! Your order has been confirmed.', 'success')
            
            # Clear the cart
            if current_user.is_authenticated:
                Cart.query.filter_by(user_id=current_user.id).delete()
                db.session.commit()
            else:
                session.pop('cart', None)
            
            return render_template('checkout_success.html', 
                                 session_id=session_id,
                                 checkout_session=checkout_session)
        else:
            flash('Payment was not completed. Please try again.', 'error')
            return redirect(url_for('main.checkout'))
            
    except Exception as e:
        current_app.logger.error(f"Error handling checkout return: {str(e)}")
        flash('An error occurred processing your payment. Please contact support.', 'error')
        return redirect(url_for('main.index'))

@main_bp.route('/process-payment-success', methods=['POST'])
def process_payment_success():
    """Process successful payment and update inventory (for development)"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'Session ID required'}), 400
        
        # Retrieve the Stripe session
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        
        if stripe_session.payment_status != 'paid':
            return jsonify({'error': 'Payment not completed'}), 400
        
        # Import the webhook processing function
        from routes.webhooks import process_successful_payment
        
        # Process the payment (this will decrement inventory)
        success = process_successful_payment(stripe_session)
        
        if success:
            return jsonify({'success': True, 'message': 'Payment processed successfully'})
        else:
            return jsonify({'error': 'Failed to process payment'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error processing payment success: {str(e)}")
        return jsonify({'error': f'Failed to process payment: {str(e)}'}), 500



@main_bp.route('/settings')
def settings():
    """User settings page"""
    return render_template('settings.html')

@main_bp.route('/user-profile')
def user_profile():
    """User profile page"""
    return render_template('user_profile.html')

@main_bp.route('/cart')
def cart_page():
    """Shopping cart page"""
    return render_template('cart.html')

@main_bp.route('/cart-debug')
def cart_debug_page():
    """Cart debug page"""
    return render_template('cart_debug.html')

@main_bp.route('/wishlist')
def wishlist_page():
    """Wishlist page"""
    return render_template('wishlist.html')

@main_bp.route('/miami-map')
def miami_map():
    """Generate and serve Miami coverage map"""
    try:
        import folium
        
        # Create map centered on Miami
        m = folium.Map(
            location=[25.756, -80.26],      # roughly Doral / middle of the metro
            zoom_start=9,                   # shows Homestead ↔ Fort Lauderdale in one view
            control_scale=True,             # little km / mi ruler bottom-left
            tiles="cartodbpositron"         # clean, grey OSM basemap
        )
        
        # Add coverage area markers
        cities = {
            # Miami-Dade
            "Downtown Miami":   (25.7743, -80.1937),
            "Brickell":        (25.7601, -80.1951),
            "Wynwood":         (25.8005, -80.1990),
            "Little Haiti":    (25.8259, -80.2003),
            "Coral Gables":    (25.7215, -80.2684),
            "West Miami":      (25.7587, -80.2978),
            "Sweetwater":      (25.7631, -80.3720),
            "Doral":           (25.8195, -80.3553),
            "Miami Beach":     (25.7906, -80.1300),
            "North Miami":     (25.8901, -80.1867),
            "Miami Gardens":   (25.9420, -80.2456),
            "Hialeah":         (25.8576, -80.2781),
            "Kendall":         (25.6793, -80.3173),
            "South Miami":     (25.7079, -80.2939),
            "Homestead":       (25.4687, -80.4776),
            
            # Broward
            "Pembroke Pines":  (26.0086, -80.3570),
            "Miramar":         (25.9826, -80.3431),
            "Davie":           (26.0814, -80.2806),
            "Hollywood":       (26.0112, -80.1495),
            "Aventura":        (25.9565, -80.1429),
            "Fort Lauderdale": (26.1224, -80.1373)
        }
        
        for name, (lat, lng) in cities.items():
            folium.Marker(
                location=(lat, lng),
                tooltip=name,
                popup=f"We deliver to {name}!"
            ).add_to(m)
        
        # Add store location
        store_lat, store_lng = 25.7617, -80.1918   # Bayfront Park area
        folium.Marker(
            location=(store_lat, store_lng),
            tooltip="🏬 LoveMeNow Store",
            popup="LoveMeNow - Your trusted adult wellness store",
            icon=folium.Icon(color="red", icon="heart", prefix="fa")
        ).add_to(m)
        
        # Return the map as HTML
        from flask import Response
        response = Response(m._repr_html_(), mimetype='text/html')
        # Allow this route to be embedded in iframes from same origin
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response
        
    except ImportError:
        # If folium is not installed, return a simple message
        return """
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; font-family: Arial, sans-serif;">
            <div style="text-align: center;">
                <h3>Miami Coverage Map</h3>
                <p>We deliver throughout Miami-Dade and Broward counties!</p>
                <p><em>Install folium to see the interactive map</em></p>
            </div>
        </div>
        """
    except Exception as e:
        current_app.logger.error(f"Error generating Miami map: {str(e)}")
        return f"""
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; font-family: Arial, sans-serif;">
            <div style="text-align: center;">
                <h3>Miami Coverage Map</h3>
                <p>We deliver throughout Miami-Dade and Broward counties!</p>
                <div style="margin-top: 2rem; padding: 1.5rem; background: #667eea; color: white; border-radius: 8px;">
                    <h4>🏬 Pickup Location</h4>
                    <p><strong>Miami Vape Smoke Shop</strong></p>
                    <p>351 NE 79th St<br>Miami, FL 33138</p>
                    <p><em>LoveMeNow Pickup Location</em></p>
                </div>
                <p style="color: #666; font-size: 0.9em; margin-top: 1rem;"><em>Error: {str(e)}</em></p>
            </div>
        </div>
        """

@main_bp.route('/test-auth')
def test_auth():
    """Test page for authentication modal"""
    return render_template('test_auth.html')

