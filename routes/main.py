"""
Main application routes
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash, make_response
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload, defer
from sqlalchemy import func, desc
from sqlalchemy.exc import OperationalError, DisconnectionError
import stripe
import stripe.checkout

from routes import db, csrf
from models import Product, ProductVariant, Category, Color, Wishlist, Cart, Order, OrderItem, UberDelivery, UserAddress
from security import validate_input
from database_utils import retry_db_operation, test_database_connection, get_fallback_data

main_bp = Blueprint('main', __name__)

def get_cached_user_counts():
    """Get cached cart and wishlist counts for performance optimization"""
    if not current_user.is_authenticated:
        # For guest users, get from session
        cart_count = sum(session.get('cart', {}).values())
        wishlist_count = len(session.get('wishlist', []))
        return cart_count, wishlist_count
    
    # Check if we have cached counts in session
    cache_key = f'user_counts_{current_user.id}'
    cached_counts = session.get(cache_key)
    
    # Cache for 90 seconds for better performance
    import time
    current_time = time.time()
    
    if cached_counts and (current_time - cached_counts.get('timestamp', 0)) < 90:
        return cached_counts['cart_count'], cached_counts['wishlist_count']
    
    # Optimized database queries
    try:
        # Use more efficient queries with explicit scalar operations
        cart_count = db.session.query(func.coalesce(func.sum(Cart.quantity), 0)).filter_by(user_id=current_user.id).scalar()
        wishlist_count = db.session.query(func.count(Wishlist.id)).filter_by(user_id=current_user.id).scalar()
        
        # Cache the results with proper type conversion
        session[cache_key] = {
            'cart_count': int(cart_count or 0),
            'wishlist_count': int(wishlist_count or 0),
            'timestamp': current_time
        }
        
        return int(cart_count or 0), int(wishlist_count or 0)
    except Exception as e:
        current_app.logger.error(f"Error getting user counts: {str(e)}")
        return 0, 0

def invalidate_user_counts_cache():
    """Invalidate cached user counts when cart/wishlist changes"""
    if current_user.is_authenticated:
        cache_key = f'user_counts_{current_user.id}'
        session.pop(cache_key, None)

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
        
        # Get featured products (limit to 3) - optimized query with deferred loading
        # Using product-level inventory checking
        featured_products = (
            Product.query
            .filter(Product.in_stock == True, Product.quantity_on_hand > 0)
            .options(
                joinedload(Product.variants),  # Load variants for color display
                joinedload(Product.colors),    # Load colors for display
                defer(Product.description),    # Defer heavy text fields
                defer(Product.specifications)  # Defer additional heavy fields
            )
            .order_by(Product.id.desc())  # Add ordering for consistent results
            .limit(3)
            .all()
        )
        
        # Get categories for navigation - optimized with limit and defer loading
        categories = Category.query.filter(Category.parent_id.is_(None)).limit(8).all()
        
        # Get cart and wishlist counts using cached function
        cart_count, wishlist_count = get_cached_user_counts()
        
        response = make_response(render_template('index.html',
                             featured_products=featured_products,
                             categories=categories,
                             cart_count=cart_count,
                             wishlist_count=wishlist_count,
                             show_age_verification=not age_verified))
        
        # Add optimized caching headers for better performance
        if not current_user.is_authenticated:
            # Cache for anonymous users for 5 minutes
            response.headers['Cache-Control'] = 'public, max-age=300'
        else:
            # Short cache for logged-in users to improve performance while keeping data fresh
            response.headers['Cache-Control'] = 'private, max-age=30'  # 30 second cache
            response.headers['Vary'] = 'Cookie'
        
        return response
    
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
        per_page = 100  # Show all products on one page
        
        # Build query - show all products including out of stock
        query = Product.query
        
        # Apply filters
        category_id = request.args.get('category', type=int)
        if category_id:
            # Get the category and all its descendants recursively
            category = Category.query.get(category_id)
            if category:
                def get_all_subcategory_ids(cat):
                    ids = [cat.id]
                    for child in cat.children:
                        ids.extend(get_all_subcategory_ids(child))
                    return ids
                
                all_category_ids = get_all_subcategory_ids(category)
                query = query.filter(Product.category_id.in_(all_category_ids))
        
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
        
        # In stock filter - check product-level inventory
        in_stock_only = request.args.get('in_stock', '').lower() == 'true'
        if in_stock_only:
            query = query.filter(
                Product.in_stock == True, 
                Product.quantity_on_hand > 0
            )
        
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
        
        # Paginate results with variant, image, and color loading
        products = query.options(
            joinedload(Product.variants).joinedload(ProductVariant.images),
            joinedload(Product.colors)
        ).paginate(
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

def process_product_details(product):
    """Process product data to extract the most important features, specifications, and dimensions"""
    import re
    
    # Check if this is a lubricant product
    lubricant_categories = [4, 55, 56, 57]  # lubricant, water-based, oil-based, massage oil
    is_lubricant = product.category_id in lubricant_categories
    
    def smart_shorten_text(text, max_length=35):
        """Intelligently shorten text by summarizing instead of just truncating"""
        if len(text) <= max_length:
            return text
            
        # If it has a colon, preserve the key and create a meaningful summary
        if ':' in text:
            key, value = text.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Special handling for lubricants - avoid "waterproof" and focus on relevant info
            if is_lubricant:
                if 'water resistance' in key.lower() or 'waterproof' in key.lower():
                    # For lubricants, show formula type instead of water resistance
                    if 'not water resistant' in value.lower():
                        return f"{key}: Formula-based"
                    else:
                        return f"{key}: Specialty formula"
                elif 'type' in key.lower():
                    # Show lubricant type clearly
                    if 'water' in value.lower():
                        return f"{key}: Water-based"
                    elif 'silicone' in value.lower():
                        return f"{key}: Silicone-based"
                    elif 'hybrid' in value.lower():
                        return f"{key}: Hybrid formula"
                    elif 'oil' in value.lower():
                        return f"{key}: Oil-based"
                    else:
                        return f"{key}: {value[:15]}"
                elif 'size' in key.lower() or 'fluid' in key.lower():
                    return f"{key}: {value}"
                elif 'collection' in key.lower() or 'category' in key.lower():
                    # Simplify collection/category info
                    if 'lubricant' in value.lower():
                        return f"{key}: Premium line"
                    else:
                        return f"{key}: {value[:15]}"
            
            # Create intelligent summaries based on content (for non-lubricants)
            if 'dual-density' in key.lower():
                return "Dual-density construction"
            elif 'material' in value.lower():
                # Extract material type
                if 'silicone' in value.lower():
                    return f"{key}: Silicone"
                elif 'tpe' in value.lower() or 'elastomer' in value.lower():
                    return f"{key}: TPE elastomer"
                else:
                    return f"{key}: Premium material"
            elif 'soft' in value.lower() and 'firm' in value.lower():
                return f"{key}: Soft & firm design"
            elif not is_lubricant and ('waterproof' in value.lower() or 'water' in value.lower()):
                return f"{key}: Waterproof"
            elif 'rechargeable' in value.lower() or 'usb' in value.lower():
                return f"{key}: USB rechargeable"
            else:
                # Keep key and first meaningful words
                words = [w for w in value.split() if len(w) > 2]
                if len(words) >= 2:
                    return f"{key}: {' '.join(words[:2])}"
                else:
                    return f"{key}: {value[:15]}"
        else:
            # For regular text without colon, create meaningful summaries
            text_lower = text.lower()
            if 'dual-density' in text_lower:
                return "Dual-density design"
            elif 'soft' in text_lower and 'firm' in text_lower:
                return "Soft exterior, firm core"
            elif not is_lubricant and 'waterproof' in text_lower:
                return "Waterproof design"
            elif 'rechargeable' in text_lower:
                return "Rechargeable battery"
            elif 'silicone' in text_lower:
                return "Premium silicone material"
            else:
                # Keep first meaningful words
                words = [w for w in text.split() if len(w) > 2]
                if len(words) >= 3:
                    return ' '.join(words[:3])
                elif len(words) >= 2:
                    return ' '.join(words[:2])
                else:
                    return text[:max_length]
    
    # Process Features (from description field)
    features = []
    if product.description:
        desc_text = product.description.lower()
        
        # Different feature keywords for lubricants vs other products
        if is_lubricant:
            # Lubricant-specific features - focus on formula, safety, and benefits
            feature_keywords = {
                'long-lasting': 'Long-Lasting Formula',
                'glycerin-free': 'Glycerin-Free',
                'paraben-free': 'Paraben-Free',
                'toy-safe': 'Toy-Safe',
                'latex-safe': 'Latex Compatible',
                'water-based': 'Water-Based Formula',
                'silicone-based': 'Silicone-Based',
                'hybrid': 'Hybrid Formula',
                'oil-based': 'Oil-Based',
                'natural': 'Natural Ingredients',
                'flavored': 'Flavored',
                'warming': 'Warming Sensation',
                'cooling': 'Cooling Effect',
                'edible': 'Edible Formula',
                'massage': 'Massage Oil',
                'premium': 'Premium Quality',
                'smooth': 'Smooth Glide',
                'slippery': 'Silky Feel',
                'non-sticky': 'Non-Sticky',
                'easy cleanup': 'Easy Cleanup',
                'body-safe': 'Body-Safe',
                'usa': 'Made in USA'
            }
        else:
            # Standard features for non-lubricant products
            feature_keywords = {
                'rechargeable': 'USB Rechargeable',
                'waterproof': 'Waterproof Design',
                'quiet': 'Quiet Operation',
                'body-safe': 'Body-Safe Materials',
                'silicone': 'Premium Silicone',
                'multiple': 'Multiple Settings',
                'remote': 'Remote Control',
                'suction': 'Suction Cup Base',
                'harness': 'Harness Compatible',
                'flexible': 'Flexible Design',
                'realistic': 'Lifelike Feel',
                'textured': 'Textured Surface',
                'vibrating': 'Vibrating Function',
                'adjustable': 'Adjustable Fit',
                'beginner': 'Beginner Friendly',
                'comfortable': 'Comfortable Fit',
                'elegant': 'Elegant Design',
                'beautiful': 'Beautiful Aesthetics',
                'soft': 'Soft Touch',
                'silk': 'Silk Material',
                'metal': 'Metal Accents',
                'lined': 'Lined Interior',
                'wire': 'Structured Support',
                'light': 'Light Control',
                'senses': 'Sensory Enhancement'
            }
        
        for keyword, feature in feature_keywords.items():
            if keyword in desc_text and feature not in features:
                features.append(feature)
                if len(features) >= 4:
                    break
        
        # Extract key phrases from description if we don't have enough features
        if len(features) < 4:
            # Look for descriptive phrases that could be features
            desc_sentences = product.description.split('.')
            for sentence in desc_sentences:
                sentence = sentence.strip()
                if sentence and len(sentence) < 50:  # Keep it concise
                    # Clean up the sentence to make it feature-like
                    if 'allow' in sentence.lower():
                        feature = sentence.replace('allow women to', '').replace('allows', '').strip()
                        if feature and len(feature) < 40:
                            features.append(feature.capitalize())
                    elif any(word in sentence.lower() for word in ['made from', 'material', 'fabric']):
                        features.append(sentence.strip().capitalize())
                    elif any(word in sentence.lower() for word in ['comfortable', 'elegant', 'beautiful', 'soft']):
                        features.append(sentence.strip().capitalize())
                    
                    if len(features) >= 4:
                        break
        
        # If we still don't have enough features, add some generic ones
        if len(features) < 4:
            if is_lubricant:
                # Lubricant-specific generic features
                generic_features = ['Premium Formula', 'Body-Safe', 'Easy Application', 'Discreet Packaging']
            else:
                # Standard generic features
                generic_features = ['Premium Quality', 'Easy to Clean', 'Discreet Packaging', 'Body-Safe Design']
            
            for feature in generic_features:
                if feature not in features:
                    features.append(feature)
                    if len(features) >= 4:
                        break
    
    # Check if material is already mentioned in features
    material_in_features = any('material' in feature.lower() or 'silicone' in feature.lower() or 'tpe' in feature.lower() 
                             for feature in (features if features else []))
    
    # Check if this is a dildo product (category ID 33)
    is_dildo_product = product.category_id == 33
    
    # Process Specifications
    specs = []
    dimensions_keywords = ['insertable', 'length', 'width', 'height', 'diameter', 'weight', 'total']
    
    if product.specifications:
        spec_lines = product.specifications.split('\n')
        
        # Priority specifications - NEVER include dimensions in specs for ANY product
        if is_lubricant:
            # Lubricant-specific priority specs - avoid "Water Resistance" which is misleading
            priority_specs = ['Type:', 'Brand:', 'Size:', 'Collection:', 'Category:', 'Manufacturer:']
        else:
            # Standard priority specs for other products
            priority_specs = ['Brand:', 'Power:', 'Water Resistance:', 'Collection:', 'Color:', 'Warranty:']
        
        # Don't add material to specs if it's already in features
        if not material_in_features:
            priority_specs.insert(1, 'Material:')
        
        for line in spec_lines:
            line = line.strip()
            if line and any(priority in line for priority in priority_specs):
                # ALWAYS skip ALL dimensions for ALL products (including width for dildos)
                if any(dim_word in line.lower() for dim_word in dimensions_keywords):
                    continue
                
                # Skip material if it's already mentioned in features
                if material_in_features and line.lower().startswith('material:'):
                    continue
                    
                # Clean up the line and keep it concise using smart shortening
                specs.append(smart_shorten_text(line, 35))
                
                if len(specs) >= 4:
                    break
        
        # If we don't have enough specs, add remaining non-dimension lines
        if len(specs) < 4:
            for line in spec_lines:
                line = line.strip()
                if (line and line not in specs and 
                    not any(spec.split(':')[0].strip() == line.split(':')[0].strip() for spec in specs if ':' in spec and ':' in line)):
                    
                    # NEVER allow dimensions in specs for ANY product
                    if not any(dim_word in line.lower() for dim_word in dimensions_keywords):
                        # Skip material if already in features
                        if material_in_features and line.lower().startswith('material:'):
                            continue
                        specs.append(smart_shorten_text(line, 35))
                    
                    if len(specs) >= 4:
                        break
    
    # Process Dimensions - Extract ALL dimensional data from specifications first
    dims = []
    
    if product.specifications:
        spec_lines = product.specifications.split('\n')
        dimension_patterns = [
            r'Insertable.*?:\s*([^;,\n]+)',
            r'Total.*?length:\s*([^;,\n]+)',
            r'Length:\s*([^;,\n]+)',
            r'Width:\s*([^;,\n]+)',
            r'Diameter:\s*([^;,\n]+)',
            r'Height:\s*([^;,\n]+)',
            r'Weight:\s*([^;,\n]+)'
        ]
        
        for line in spec_lines:
            line = line.strip()
            for pattern in dimension_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match and len(dims) < 4:
                    dim_value = match.group(0).strip()
                    # Avoid duplicates by checking if similar dimension already exists
                    is_duplicate = False
                    for existing_dim in dims:
                        if (dim_value.lower().replace(' ', '') in existing_dim.lower().replace(' ', '') or
                            existing_dim.lower().replace(' ', '') in dim_value.lower().replace(' ', '')):
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        dims.append(dim_value)
    
    # Then check dimensions field for additional info
    if product.dimensions and len(dims) < 4:
        dim_text = product.dimensions
        
        # If dimensions field contains descriptive text, intelligently shorten it
        separators = ['\n\n', '\n', ';', ',']
        for sep in separators:
            if sep in dim_text:
                parts = dim_text.split(sep)
                for part in parts:
                    part = part.strip()
                    if part and len(dims) < 4:
                        dims.append(smart_shorten_text(part, 35))
                break
        
        # If still no dimensions from descriptive text, use the whole string (but shorten intelligently)
        if len(dims) < 4 and not any(sep in dim_text for sep in separators) and dim_text.strip():
            dims.append(smart_shorten_text(dim_text.strip(), 35))
    
    # Ensure we have exactly 4 items in each list (or whatever is available)
    if is_lubricant:
        # Lubricant-specific defaults
        features = features[:4] if features else ['Premium Formula', 'Body-Safe', 'Easy Application', 'Discreet Packaging']
        specs = specs[:4] if specs else ['Professional Grade', 'Quality Formula', 'Tested & Certified', 'Satisfaction Guaranteed']
        dims = dims[:4] if dims else ['Standard Size', 'Portable Design', 'Easy Storage', 'Travel Friendly']
    else:
        # Standard defaults for other products
        features = features[:4] if features else ['Premium Quality', 'Body-Safe Design', 'Easy to Clean', 'Discreet Packaging']
        specs = specs[:4] if specs else ['Professional Grade', 'Quality Assured', 'Manufacturer Warranty', 'Tested & Certified']
        dims = dims[:4] if dims else ['Standard Size', 'Ergonomic Design', 'Lightweight', 'Compact Storage']
    
    return features, specs, dims

@main_bp.route('/product/<int:product_id>')
@require_age_verification
def product_detail(product_id):
    """Product detail page"""
    try:
        product = (
            Product.query
            .options(
                joinedload(Product.variants).joinedload(ProductVariant.images),
                joinedload(Product.variants).joinedload(ProductVariant.color),
                joinedload(Product.colors)
            )
            .get_or_404(product_id)
        )
        
        # Process product details to extract features, specs, and dimensions
        features, specs, dims = process_product_details(product)
        
        # Get related products from same category that are in stock
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
                             features=features,
                             specs=specs,
                             dims=dims,
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

@main_bp.route('/track')
def track_order():
    """Order tracking page"""
    return render_template('track_order.html')

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

@main_bp.route('/test-slack-notification')
def test_slack_notification():
    """Test route to verify Slack notifications are working"""
    from services.slack_notifications import send_test_notification
    
    try:
        success = send_test_notification()
        if success:
            return """
            <h1>✅ Slack Test Notification Sent!</h1>
            <p>Check your Slack channel to see if the test message was received.</p>
            <p><a href="/">Return to Home</a></p>
            """
        else:
            return """
            <h1>❌ Slack Test Notification Failed</h1>
            <p>The test notification could not be sent. Check the server logs for details.</p>
            <p><a href="/">Return to Home</a></p>
            """, 500
    except Exception as e:
        current_app.logger.error(f"Error in test Slack notification: {str(e)}")
        return f"""
        <h1>❌ Slack Test Error</h1>
        <p>An error occurred: {str(e)}</p>
        <p><a href="/">Return to Home</a></p>
        """, 500

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
        current_app.logger.info(f"Authenticated user cart items: {len(cart_items)}")
    else:
        # Get cart from session for guest users
        cart_data = session.get('cart', {})
        current_app.logger.info(f"Guest user cart data: {cart_data}")
        if cart_data:
            for cart_key, quantity in cart_data.items():
                try:
                    # Handle both formats: "product_id" and "product_id:variant_id"
                    if ':' in str(cart_key):
                        product_id = int(cart_key.split(':')[0])
                    else:
                        product_id = int(cart_key)
                    
                    product = Product.query.get(product_id)
                    if product:
                        cart_items.append({
                            'product': product,
                            'quantity': quantity
                        })
                except (ValueError, TypeError):
                    continue
    
    # If cart is empty, redirect to cart page - simple and predictable
    if not cart_items:
        current_app.logger.warning("Cart is empty, redirecting to cart page")
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
            # Extract product IDs from cart keys (handle both "product_id" and "product_id:variant_id" formats)
            product_ids = []
            for cart_key in cart_session.keys():
                try:
                    if ':' in str(cart_key):
                        product_id = int(cart_key.split(':')[0])
                    else:
                        product_id = int(cart_key)
                    product_ids.append(product_id)
                except (ValueError, TypeError):
                    continue
            
            cart_products = Product.query.filter(Product.id.in_(product_ids)).all()
            for product in cart_products:
                # Find the cart entry for this product (could be "product_id" or "product_id:variant_id")
                quantity = 0
                for cart_key, cart_quantity in cart_session.items():
                    try:
                        if ':' in str(cart_key):
                            key_product_id = int(cart_key.split(':')[0])
                        else:
                            key_product_id = int(cart_key)
                        
                        if key_product_id == product.id:
                            quantity += cart_quantity  # Sum quantities if multiple variants
                    except (ValueError, TypeError):
                        continue
                
                if quantity > 0:
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
    
    # Calculate shipping - will be determined at checkout based on delivery method
    cart_data['shipping'] = 0  # No shipping fee in cart, will be calculated at checkout
    cart_data['total'] = cart_data['subtotal'] + cart_data['shipping']
    cart_data['count'] = len(cart_data['items'])
    
    # Prepare user data and addresses for logged-in users
    user_data = None
    user_addresses = []
    default_address = None
    
    if current_user.is_authenticated:
        user_data = {
            'email': current_user.email,
            'full_name': current_user.full_name
        }
        
        # Get user addresses
        user_addresses = UserAddress.query.filter_by(user_id=current_user.id).all()
        default_address = UserAddress.query.filter_by(user_id=current_user.id, is_default=True).first()
    
    # Use enhanced checkout template with delivery options
    try:
        current_app.logger.info("Attempting to render checkout_enhanced.html template")
        current_app.logger.info(f"Cart data: {cart_data}")
        current_app.logger.info(f"Config keys: {list(current_app.config.keys())}")
        return render_template('checkout_enhanced.html', 
                             config=current_app.config, 
                             cart_data=cart_data,
                             user_data=user_data,
                             user_addresses=user_addresses,
                             default_address=default_address)
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
                joinedload(Order.items)
            ).get(order_id)
        
        if not order:
            current_app.logger.warning(f"Order {order_id} not found, redirecting to home")
            return redirect(url_for('main.index'))
        
        # Get order items with product details (NO VARIANTS)
        order_items = []
        for item in order.items:
            # Get product directly (no variants)
            product = Product.query.get(item.product_id)
            if product:
                order_items.append({
                    'product': product,
                    'quantity': item.quantity,
                    'unit_price': item.price,
                    'total_price': item.total,
                    'product_image': product.image_url
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
    from models import Order, OrderItem, Product
    from sqlalchemy.orm import joinedload
    
    # Get user's orders with delivery information and eagerly load product data
    orders = (Order.query
              .filter_by(user_id=current_user.id)
              .options(joinedload(Order.items).joinedload(OrderItem.product))
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
        
        # Enhanced debug logging for Render deployment
        import os
        current_app.logger.info(f"🔍 STRIPE DEBUG - Environment STRIPE_SECRET_KEY: {os.getenv('STRIPE_SECRET_KEY')[:10] if os.getenv('STRIPE_SECRET_KEY') else 'NOT SET'}...")
        current_app.logger.info(f"🔍 STRIPE DEBUG - Config STRIPE_SECRET_KEY: {stripe_secret_key[:10] if stripe_secret_key else 'NOT SET'}...")
        current_app.logger.info(f"🔍 STRIPE DEBUG - Full key ending: ...{stripe_secret_key[-10:] if stripe_secret_key else 'NO KEY'}")
        current_app.logger.info(f"🔍 STRIPE DEBUG - Key length: {len(stripe_secret_key) if stripe_secret_key else 0}")
        
        # Verify Stripe is properly configured
        if not stripe_secret_key:
            current_app.logger.error("❌ Stripe API key is not set in configuration")
            return jsonify({'error': 'Payment system not configured - missing API key'}), 500
            
        # Set Stripe API key
        stripe.api_key = stripe_secret_key
        
        # Verify the key was actually set
        current_app.logger.info(f"🔍 STRIPE DEBUG - stripe.api_key after setting: {stripe.api_key[:10] if stripe.api_key else 'NOT SET'}...{stripe.api_key[-10:] if stripe.api_key else ''}")
        
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
                for cart_key, quantity in cart_data.items():
                    # Handle both formats: "product_id" and "product_id:variant_id"
                    if ':' in str(cart_key):
                        product_id = int(cart_key.split(':')[0])
                    else:
                        product_id = int(cart_key)
                    product = Product.query.get(product_id)
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
        
        # Add delivery fee if needed - get from request JSON
        request_data = request.get_json() or {}
        delivery_type = request_data.get('delivery_type', 'pickup')
        delivery_quote = request_data.get('delivery_quote', {})
        
        current_app.logger.info(f"🚚 DELIVERY DEBUG:")
        current_app.logger.info(f"   Request data: {request_data}")
        current_app.logger.info(f"   Delivery type: {delivery_type}")
        current_app.logger.info(f"   Delivery quote: {delivery_quote}")
        current_app.logger.info(f"   Quote has fee_dollars: {'fee_dollars' in delivery_quote if delivery_quote else False}")
        
        if delivery_type == 'delivery':
            # Use actual Uber delivery fee from quote
            if delivery_quote and 'fee_dollars' in delivery_quote:
                delivery_fee_dollars = float(delivery_quote['fee_dollars'])
                delivery_fee_cents = int(delivery_fee_dollars * 100)
                current_app.logger.info(f"Using Uber delivery fee: ${delivery_fee_dollars:.2f}")
                
                line_items.append({
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': 'Uber Direct Delivery',
                            'description': f'Same-day delivery via Uber Direct',
                        },
                        'unit_amount': delivery_fee_cents,
                    },
                    'quantity': 1,
                })
            else:
                # Fallback delivery fee if no quote available
                current_app.logger.warning("No delivery quote provided, using fallback fee")
                line_items.append({
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': 'Delivery Fee',
                            'description': 'Standard delivery',
                        },
                        'unit_amount': 999,  # $9.99 in cents
                    },
                    'quantity': 1,
                })
        
        # Create Stripe checkout session for embedded checkout
        current_app.logger.info("Creating Stripe checkout session...")
        current_app.logger.info(f"Line items count: {len(line_items)}")
        for i, item in enumerate(line_items):
            current_app.logger.info(f"Line item {i}: {item['price_data']['product_data']['name']} - ${item['price_data']['unit_amount']/100:.2f} x {item['quantity']}")
        current_app.logger.info(f"Full line items: {line_items}")
        
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
        
        # Calculate subtotal amount in cents
        subtotal_amount = 0
        for item in line_items:
            subtotal_amount += item['price_data']['unit_amount'] * item['quantity']
        
        # Add Miami-Dade County sales tax (8.75%)
        tax_rate = 0.0875
        tax_amount = int(subtotal_amount * tax_rate)
        
        # Add tax as a separate line item
        if tax_amount > 0:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Sales Tax',
                        'description': 'Miami-Dade County Tax (8.75%)',
                    },
                    'unit_amount': tax_amount,
                },
                'quantity': 1,
            })
        
        # Calculate total amount in cents (including tax)
        total_amount = subtotal_amount + tax_amount
        
        current_app.logger.info(f"Subtotal amount in cents: {subtotal_amount}")
        current_app.logger.info(f"Tax amount in cents: {tax_amount}")
        current_app.logger.info(f"Total amount in cents: {total_amount}")
        
        try:
            # Create Stripe Payment Intent for Elements integration (NOT Checkout Session!)
            current_app.logger.info("🚀 CREATING PAYMENT INTENT (NOT CHECKOUT SESSION) FOR ELEMENTS INTEGRATION...")
            
            # Calculate total amount in cents
            total_amount_cents = int(total_amount)
            
            payment_intent = stripe.PaymentIntent.create(
                amount=total_amount_cents,
                currency='usd',
                metadata=cart_metadata,
                payment_method_types=['card'],  # Only allow card payments (no CashApp, Klarna, Apple Pay)
                # Add shipping and billing info if available
                description=f"LoveMeNow order - {len(line_items)} items"
            )
            
            current_app.logger.info(f"🎉 PAYMENT INTENT CREATED SUCCESSFULLY: {payment_intent.id} (NOT CHECKOUT SESSION!)")
            
            # Return the client secret
            client_secret = payment_intent.client_secret
            if client_secret:
                current_app.logger.info(f"🔑 PAYMENT INTENT CLIENT SECRET OBTAINED: {client_secret[:20]}... (SHOULD START WITH 'pi_')")
                
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
                
                # Validate client secret format (Payment Intent client secrets start with 'pi_')
                if not (client_secret.startswith('pi_') and '_secret_' in client_secret):
                    current_app.logger.error(f"❌ Invalid Payment Intent client secret format: {client_secret[:50]}...")
                    return jsonify({'error': 'Invalid Payment Intent client secret format'}), 500
                
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
                current_app.logger.error("No client secret found in Payment Intent")
                return jsonify({'error': 'No client secret found in Payment Intent'}), 500
            
        except Exception as payment_error:
            current_app.logger.error(f"Error creating Payment Intent: {payment_error}")
            import traceback
            current_app.logger.error(f"Payment Intent error traceback: {traceback.format_exc()}")
            return jsonify({'error': f'Failed to create Payment Intent: {str(payment_error)}'}), 500
    
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
@login_required
def settings():
    """User settings page"""
    return render_template('settings.html')

@main_bp.route('/user-profile')
@login_required
def user_profile():
    """User profile page"""
    return render_template('user_profile.html')

# ============================================================================
# STRIPE EMBEDDED CHECKOUT TEST ROUTES
# ============================================================================

@main_bp.route('/checkout-test')
@require_age_verification
def checkout_test():
    """Test Stripe Embedded Checkout"""
    # Get cart data (same logic as regular checkout)
    cart_items = []
    if current_user.is_authenticated:
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    else:
        cart_data = session.get('cart', {})
        if cart_data:
            for cart_key, quantity in cart_data.items():
                try:
                    if ':' in str(cart_key):
                        product_id = int(cart_key.split(':')[0])
                    else:
                        product_id = int(cart_key)
                    
                    product = Product.query.get(product_id)
                    if product:
                        cart_items.append({
                            'product': product,
                            'quantity': quantity
                        })
                except (ValueError, TypeError):
                    continue

    # Calculate totals
    subtotal = 0
    items = []
    for item in cart_items:
        if hasattr(item, 'product'):
            product = item.product
            quantity = item.quantity
        else:
            product = item['product']
            quantity = item['quantity']
        
        subtotal += product.price * quantity
        items.append({
            'product': product,
            'quantity': quantity
        })

    cart_data = {
        'items': items,
        'subtotal': subtotal,
        'total': subtotal  # No shipping for now
    }

    return render_template('checkout_stripe_embedded.html', 
                         config=current_app.config,
                         cart_data=cart_data)

@main_bp.route('/create-checkout-session-embedded', methods=['POST'])
@csrf.exempt
def create_checkout_session_embedded():
    """Create Stripe Checkout Session for embedded checkout"""
    try:
        # Set Stripe API key
        stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not stripe_secret_key:
            return jsonify({'error': 'Payment system not configured'}), 500
        
        stripe.api_key = stripe_secret_key

        # Get cart data (same logic as regular checkout)
        cart_items = []
        if current_user.is_authenticated:
            cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        else:
            # Handle session cart
            cart_data = session.get('cart', {})
            if cart_data:
                for cart_key, quantity in cart_data.items():
                    try:
                        if ':' in str(cart_key):
                            product_id = int(cart_key.split(':')[0])
                        else:
                            product_id = int(cart_key)
                        
                        product = Product.query.get(product_id)
                        if product:
                            cart_items.append({
                                'product': product,
                                'quantity': quantity
                            })
                    except (ValueError, TypeError):
                        continue

        # Create line items from cart
        line_items = []
        if cart_items:
            for item in cart_items:
                if hasattr(item, 'product'):
                    product = item.product
                    quantity = item.quantity
                else:
                    product = item['product']
                    quantity = item['quantity']
                
                line_items.append({
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': product.name,
                            'description': product.description[:100] if product.description else '',
                        },
                        'unit_amount': int(product.price * 100),
                    },
                    'quantity': quantity,
                })
        
        # If no cart items, create test item
        if not line_items:
            line_items = [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Test Product',
                        'description': 'Test product for Stripe Embedded Checkout',
                    },
                    'unit_amount': 2999,  # $29.99
                },
                'quantity': 1,
            }]

        # Create Stripe Checkout Session (NOT Payment Intent!)
        checkout_session = stripe.checkout.Session.create(
            ui_mode='embedded',  # This makes it embeddable
            payment_method_types=['card'],  # Only cards for now
            line_items=line_items,
            mode='payment',
            return_url=request.host_url + 'checkout-success?session_id={CHECKOUT_SESSION_ID}',
            
            # Collect customer information
            customer_email=current_user.email if current_user.is_authenticated else None,
            billing_address_collection='required',  # Collect billing address
            phone_number_collection={'enabled': True},  # Collect phone number
            
            # Shipping (if needed)
            shipping_address_collection={
                'allowed_countries': ['US'],  # Restrict to US for now
            },
            
            # Custom fields for additional info
            custom_fields=[
                {
                    'key': 'full_name',
                    'label': {'type': 'custom', 'custom': 'Full Name'},
                    'type': 'text',
                    'optional': False,
                }
            ],
            
            # Enable saved payment methods for returning customers
            customer_creation='if_required',
        )

        return jsonify({
            'client_secret': checkout_session.client_secret
        })

    except Exception as e:
        current_app.logger.error(f"Error creating embedded checkout session: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        
        # Get the map HTML and wrap it properly
        map_html = m._repr_html_()
        
        # Wrap in a proper HTML document with full height
        full_html = f"""
        <!DOCTYPE html>
        <html style="height: 100%; margin: 0; padding: 0;">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Miami Coverage Map</title>
            <style>
                body {{
                    height: 100vh;
                    margin: 0;
                    padding: 0;
                    font-family: Arial, sans-serif;
                }}
                .folium-map {{
                    height: 100vh !important;
                    width: 100% !important;
                }}
            </style>
        </head>
        <body>
            {map_html}
        </body>
        </html>
        """
        
        # Return the map as HTML
        from flask import Response
        response = Response(full_html, mimetype='text/html')
        # Allow this route to be embedded in iframes from same origin
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        return response
        
    except ImportError:
        # If folium is not installed, return a simple message
        return """
        <!DOCTYPE html>
        <html style="height: 100%; margin: 0; padding: 0;">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Miami Coverage Map</title>
        </head>
        <body style="height: 100vh; margin: 0; padding: 0; display: flex; align-items: center; justify-content: center; font-family: Arial, sans-serif; background: #f8f9fa;">
            <div style="text-align: center; padding: 2rem;">
                <h3 style="color: #667eea; margin-bottom: 1rem;">Miami Coverage Map</h3>
                <p style="margin-bottom: 1rem;">We deliver throughout Miami-Dade and Broward counties!</p>
                <p style="color: #666; font-style: italic;">Install folium to see the interactive map</p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        current_app.logger.error(f"Error generating Miami map: {str(e)}")
        return f"""
        <!DOCTYPE html>
        <html style="height: 100%; margin: 0; padding: 0;">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Miami Coverage Map</title>
        </head>
        <body style="height: 100vh; margin: 0; padding: 0; display: flex; align-items: center; justify-content: center; font-family: Arial, sans-serif; background: #f8f9fa;">
            <div style="text-align: center; padding: 2rem;">
                <h3 style="color: #667eea; margin-bottom: 1rem;">Miami Coverage Map</h3>
                <p style="margin-bottom: 1rem;">We deliver throughout Miami-Dade and Broward counties!</p>
                <div style="margin-top: 2rem; padding: 1.5rem; background: #667eea; color: white; border-radius: 8px;">
                    <h4>🏬 Pickup Location</h4>
                    <p><strong>Miami Vape Smoke Shop</strong></p>
                    <p>351 NE 79th St<br>Miami, FL 33138</p>
                    <p><em>LoveMeNow Pickup Location</em></p>
                </div>
                <p style="color: #666; font-size: 0.9em; margin-top: 1rem;"><em>Error: {str(e)}</em></p>
            </div>
        </body>
        </html>
        """

@main_bp.route('/test-auth')
def test_auth():
    """Test page for authentication modal"""
    return render_template('test_auth.html')

