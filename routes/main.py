"""
Main application routes
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash, \
    make_response
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload, selectinload, defer
from sqlalchemy import func, desc
from sqlalchemy.exc import OperationalError, DisconnectionError
import stripe
import stripe.checkout

from routes import db, csrf
from routes.auth import require_age_verification
from models import Product, ProductVariant, Category, Color, Wishlist, Cart, Order, OrderItem, UberDelivery, UserAddress
from security import validate_input
from database_utils import retry_db_operation, test_database_connection, get_fallback_data
from holiday_hours import get_today_closure_info

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
        cart_count = db.session.query(func.coalesce(func.sum(Cart.quantity), 0)).filter_by(
            user_id=current_user.id).scalar()
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



def is_age_verified():
    """Return True when visitor has completed the age gate (session or cookie)."""
    age_verified = session.get('age_verified', False)
    if not age_verified and request.cookies.get('age_verified') == '1':
        session['age_verified'] = True
        age_verified = True
    return age_verified


@main_bp.route('/')
def index():
    """
    Home page with featured products.
    Age gate is handled globally in app.py (before_request),
    so this view just renders the homepage.
    """
    age_verified = is_age_verified()
    try:
        # DB health check
        db_connected, db_message = test_database_connection()
        if not db_connected:
            current_app.logger.warning(f"DB down: {db_message}")
            fb = get_fallback_data()
            resp = make_response(render_template(
                "index.html",
                featured_products=fb["featured_products"],
                categories=fb["categories"],
                cart_count=fb["cart_count"],
                wishlist_count=fb["wishlist_count"],
                db_error=True,
                age_verified=age_verified,
            ))
            # Cache policy: always vary on Cookie so session changes bust caches
            resp.headers["Vary"] = "Cookie"
            if current_user.is_authenticated:
                resp.headers["Cache-Control"] = "private, max-age=30"
            else:
                resp.headers["Cache-Control"] = "private, max-age=60"
            return resp

        # Featured products + categories
        featured_products = (
            Product.query
            .filter(Product.in_stock.is_(True), Product.quantity_on_hand > 0, Product.in_active.is_(False))
            .options(
                joinedload(Product.variants),
                joinedload(Product.colors),
                defer(Product.description),
                defer(Product.specifications),
            )
            .order_by(Product.id.desc())
            .limit(3)
            .all()
        )
        categories = Category.query.filter(Category.parent_id.is_(None)).limit(8).all()

        cart_count, wishlist_count = get_cached_user_counts()

        # Use performance template if requested via query param
        template = "index_performance.html" if request.args.get('perf') else "index.html"

        resp = make_response(render_template(
            template,
            featured_products=featured_products,
            categories=categories,
            cart_count=cart_count,
            wishlist_count=wishlist_count,
            age_verified=age_verified,
        ))

        # Cache policy: avoid serving a stale "pre-AV" page; always vary on Cookie
        resp.headers["Vary"] = "Cookie"
        if current_user.is_authenticated:
            resp.headers["Cache-Control"] = "private, max-age=30"
        else:
            resp.headers["Cache-Control"] = "private, max-age=60"

        return resp

    except (OperationalError, DisconnectionError) as e:
        current_app.logger.error(f"DB error on home: {e}")
        fb = get_fallback_data()
        resp = make_response(render_template(
            "index.html",
            featured_products=fb["featured_products"],
            categories=fb["categories"],
            cart_count=fb["cart_count"],
            wishlist_count=fb["wishlist_count"],
            db_error=True,
            age_verified=age_verified,
        ))
        resp.headers["Vary"] = "Cookie"
        if current_user.is_authenticated:
            resp.headers["Cache-Control"] = "private, max-age=30"
        else:
            resp.headers["Cache-Control"] = "private, max-age=60"
        return resp

    except Exception as e:
        current_app.logger.error(f"Error loading home: {e}")
        return render_template("errors/500.html"), 500


@main_bp.route('/products')
def products():
    """Products listing page with filtering and pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 48  # Paginate for performance: 100x smaller initial load

        # Build query - show all products including out of stock
        query = Product.query.filter(Product.in_active.is_(False))

        # Apply filters
        category_param = request.args.get('category')
        category_id = None
        category = None
        
        # SPECIAL HANDLING for gender slugs (these are not database categories)
        # These map to specific product category IDs
        gender_mappings = {
            'men': [34, 60, 35, 33, 55, 56, 57, 4, 11, 37, 53, 38, 51, 61, 62],
            'women': [36, 39, 5, 33, 54, 1, 7, 10, 40, 50, 4, 55, 56, 57, 58, 11, 38, 61, 62]
        }
        
        if category_param:
            # Check if it's a special gender slug first
            if category_param in gender_mappings:
                # Gender filter: map to product category IDs
                all_category_ids = list(set(gender_mappings[category_param]))
                query = query.filter(Product.category_id.in_(all_category_ids))
                # Set category for display purposes
                category = type('obj', (object,), {
                    'slug': category_param,
                    'id': None,
                    'name': category_param.capitalize()
                })()
            elif category_param == 'gender':
                # "All Gender" - show products from both men AND women
                all_gender_ids = list(set(gender_mappings['men'] + gender_mappings['women']))
                query = query.filter(Product.category_id.in_(all_gender_ids))
                category = type('obj', (object,), {
                    'slug': 'gender',
                    'id': None,
                    'name': 'Gender'
                })()
            else:
                # Try to parse as integer first (numeric category ID)
                try:
                    category_id = int(category_param)
                    category = Category.query.get(category_id)
                except (ValueError, TypeError):
                    # If not an integer, try to find by slug
                    category = Category.query.filter_by(slug=category_param).first()
                
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

        # Apply sorting - Always prioritize in-stock products first
        sort_by = request.args.get('sort', 'name')
        if sort_by == 'low-high':
            query = query.order_by(Product.in_stock.desc(), Product.price.asc())
        elif sort_by == 'high-low':
            query = query.order_by(Product.in_stock.desc(), Product.price.desc())
        elif sort_by == 'newest':
            query = query.order_by(Product.in_stock.desc(), desc(Product.id))
        else:
            query = query.order_by(Product.in_stock.desc(), Product.name.asc())

        # Paginate results with optimized query loading
        # Use selectinload for collections (not joinedload) to avoid cartesian products
        products = query.options(
            selectinload(Product.variants).selectinload(ProductVariant.images),
            selectinload(Product.colors)
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Get filter options - only main categories (parent categories) with their children
        # Query fresh each time - no session caching of models
        categories = Category.query.filter(Category.parent_id.is_(None)).options(selectinload(Category.children)).all()
        colors = Color.query.join(Color.products).distinct().all()

        return render_template('products.html',
                               products=products,
                               categories=categories,
                               colors=colors,
                               current_filters={
                                   'category': category.id if category else None,
                                   'category_name': category.name if category else None,
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

    # Process Features (prefer DB field, fall back to computed from description)
    features = []
    # If DB-backed features provided, split into a clean list (supports newline or semicolon-separated)
    if getattr(product, 'features', None) and product.features and product.features.strip():
        parts = re.split(r'[\n;]+', product.features)
        features = [p.strip() for p in parts if p and p.strip()]
    elif product.description:
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
    material_in_features = any(
        'material' in feature.lower() or 'silicone' in feature.lower() or 'tpe' in feature.lower()
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
                        not any(spec.split(':')[0].strip() == line.split(':')[0].strip() for spec in specs if
                                ':' in spec and ':' in line)):

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
        features = features[:4] if features else ['Premium Formula', 'Body-Safe', 'Easy Application',
                                                  'Discreet Packaging']
        specs = specs[:4] if specs else ['Professional Grade', 'Quality Formula', 'Tested & Certified',
                                         'Satisfaction Guaranteed']
        dims = dims[:4] if dims else ['Standard Size', 'Portable Design', 'Easy Storage', 'Travel Friendly']
    else:
        # Standard defaults for other products
        features = features[:4] if features else ['Premium Quality', 'Body-Safe Design', 'Easy to Clean',
                                                  'Discreet Packaging']
        specs = specs[:4] if specs else ['Professional Grade', 'Quality Assured', 'Manufacturer Warranty',
                                         'Tested & Certified']
        dims = dims[:4] if dims else ['Standard Size', 'Ergonomic Design', 'Lightweight', 'Compact Storage']

    return features, specs, dims


@main_bp.route('/product/<int:product_id>')
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
            .filter(Product.id == product_id, Product.in_active.is_(False))
            .first_or_404()
        )

        # Process product details to extract features, specs, and dimensions
        features, specs, dims = process_product_details(product)

        # Get related products from same category that are in stock
        related_products = (
            Product.query
            .filter(Product.category_id == product.category_id)
            .filter(Product.id != product_id)
            .filter(Product.in_stock == True, Product.quantity_on_hand > 0, Product.in_active.is_(False))
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


@main_bp.route('/test-homepage-flash')
def test_homepage_flash():
    """Test route to flash a message and redirect to homepage"""
    from flask import flash, redirect, url_for
    flash('This is a test flash message on the homepage!', 'error')
    return redirect(url_for('main.index'))


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
    current_app.logger.info(
        f"Stripe secret key: {current_app.config.get('STRIPE_SECRET_KEY', 'NOT SET')[:10]}..." if current_app.config.get(
            'STRIPE_SECRET_KEY') else "NOT SET")

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
            quantity = int(cart_item.quantity or 0)
            if quantity <= 0:
                continue
            item_total = float(product.price) * quantity
            cart_data['subtotal'] += item_total

            variant = cart_item.variant if cart_item.variant_id else None
            variant_color = variant.color.name if variant and variant.color else None
            variant_name = variant.variant_name if variant else None
            display_name = product.variant_display_name(variant=variant) if variant else product.name

            cart_data['items'].append({
                'id': product.id,
                'variant_id': cart_item.variant_id,
                'name': display_name,
                'price': float(product.price),
                'quantity': quantity,
                'image_url': product.main_image_url,
                'description': product.description or '',
                'in_stock': product.is_available,
                'max_quantity': product.quantity_on_hand,
                'item_total': item_total,
                'variant_color': variant_color,
                'variant_name': variant_name,
                'variant_label': variant_color or variant_name
            })
    else:
        cart_session = session.get('cart', {})
        if cart_session:
            cart_entries = []
            product_ids = set()
            for cart_key, cart_quantity in cart_session.items():
                try:
                    key_str = str(cart_key)
                    if ':' in key_str:
                        product_part, variant_part = key_str.split(':', 1)
                    else:
                        product_part, variant_part = key_str, None
                    product_id = int(product_part)
                    variant_id = None
                    if variant_part not in (None, '', 'None', 'null'):
                        variant_id = int(variant_part)
                    quantity = int(cart_quantity or 0)
                except (ValueError, TypeError):
                    continue
                if quantity <= 0:
                    continue
                cart_entries.append((product_id, variant_id, quantity))
                product_ids.add(product_id)

            if cart_entries:
                cart_products = (
                    Product.query
                    .filter(Product.id.in_(list(product_ids)))
                    .options(joinedload(Product.variants).joinedload(ProductVariant.color))
                    .all()
                )
                product_lookup = {p.id: p for p in cart_products}

                for product_id, variant_id, quantity in cart_entries:
                    product = product_lookup.get(product_id)
                    if not product:
                        continue

                    variant = None
                    variant_color = None
                    variant_name = None
                    if variant_id:
                        variant = next((v for v in product.variants if v.id == variant_id), None)
                        if variant:
                            variant_color = variant.color.name if variant.color else None
                            variant_name = variant.variant_name

                    display_name = product.variant_display_name(variant=variant) if variant else product.name
                    item_total = float(product.price) * quantity
                    cart_data['subtotal'] += item_total

                    cart_data['items'].append({
                        'id': product.id,
                        'variant_id': variant_id,
                        'name': display_name,
                        'price': float(product.price),
                        'quantity': quantity,
                        'image_url': product.main_image_url,
                        'description': product.description or '',
                        'in_stock': product.is_available,
                        'max_quantity': product.quantity_on_hand,
                        'item_total': item_total,
                        'variant_color': variant_color,
                        'variant_name': variant_name,
                        'variant_label': variant_color or variant_name
                    })

    # Calculate shipping - will be determined at checkout based on delivery method
    cart_data['shipping'] = 0
    cart_data['total'] = cart_data['subtotal'] + cart_data['shipping']
    cart_data['count'] = sum(item['quantity'] for item in cart_data['items'])

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

    # Get holiday closure info if applicable
    holiday_info = get_today_closure_info()
    
    # Use enhanced checkout template with delivery options
    try:
        current_app.logger.info("Attempting to render checkout_enhanced.html template")
        current_app.logger.info(f"Cart data: {cart_data}")
        current_app.logger.info(f"Config keys: {list(current_app.config.keys())}")
        if holiday_info:
            current_app.logger.info(f"🕓 Holiday closure detected: {holiday_info['closing_time_str']}")
        return render_template('checkout_enhanced.html',
                               config=current_app.config,
                               cart_data=cart_data,
                               user_data=user_data,
                               user_addresses=user_addresses,
                               default_address=default_address,
                               holiday_info=holiday_info)
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
        'stripe_secret_key_preview': current_app.config.get('STRIPE_SECRET_KEY', 'NOT SET')[
                                     :10] + '...' if current_app.config.get('STRIPE_SECRET_KEY') else 'NOT SET',
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

        # Use optimized template for better performance - add ?perf=1 to URL to use optimized version
        template = 'checkout_success_optimized.html' if request.args.get('perf') == '1' else 'checkout_success.html'
        
        return render_template(template,
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
    """Create a Stripe PaymentIntent based on server-side totals and return its client secret."""
    try:
        stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not stripe_secret_key:
            return jsonify({'error': 'Payment system not configured'}), 500

        stripe.api_key = stripe_secret_key

        data = request.get_json(silent=True) or {}
        delivery_type = (data.get('delivery_type') or 'pickup').strip().lower()
        delivery_quote = data.get('delivery_quote') or None

        # 🧮 source of truth: compute totals on the server
        from routes.checkout_totals import compute_totals
        breakdown = compute_totals(delivery_type=delivery_type, delivery_quote=delivery_quote)

        if breakdown['amount_cents'] <= 0:
            return jsonify({'error': 'Cart is empty or total is zero'}), 400

        # Cancel stale PaymentIntent if one exists in session (to force fresh PI each time)
        try:
            old_pi = session.get("active_pi_id")
            if old_pi:
                stripe.PaymentIntent.cancel(old_pi)
        except Exception:
            pass

        # Create/renew a PaymentIntent with CARD ONLY (no Affirm/Amazon/Cash App/Klarna)
        intent = stripe.PaymentIntent.create(
            amount=breakdown['amount_cents'],
            currency='usd',
            automatic_payment_methods={'enabled': False},  # ✅ DISABLED
            payment_method_types=['card'],                 # ✅ CARD ONLY
            description='LoveMeNow order',
            metadata={
                'delivery_type': delivery_type,
                'delivery_fee': str(breakdown['delivery_fee']),
                'subtotal': str(breakdown['subtotal']),
                'discount_amount': str(breakdown['discount_amount']),
                'discount_code': breakdown['discount_code'] or '',
                'tax': str(breakdown['tax']),
                'total': str(breakdown['total']),
                'user_id': str(current_user.id) if current_user.is_authenticated else 'guest',
                'request_pin': '1' if data.get('request_pin') else '0',
            }
        )
        
        # Store PI id in session to avoid reusing stale ones
        session["active_pi_id"] = intent.id

        return jsonify({
            'clientSecret': intent.client_secret,
            # optional: handy for debugging in your console
            'amount': breakdown['amount_cents'],
            'total': breakdown['total'],
            'tax': breakdown['tax'],
            'delivery_fee': breakdown['delivery_fee'],
            'discount': breakdown['discount_amount'],
        })
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error creating intent: {str(e)}")
        return jsonify({'error': 'Payment service unavailable'}), 502
    except Exception as e:
        current_app.logger.error(f"Create PI error: {str(e)}")
        return jsonify({'error': 'Failed to initialize payment'}), 500


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
            location=[25.756, -80.26],  # roughly Doral / middle of the metro
            zoom_start=9,  # shows Homestead ↔ Fort Lauderdale in one view
            control_scale=True,  # little km / mi ruler bottom-left
            tiles="cartodbpositron"  # clean, grey OSM basemap
        )

        # Add coverage area markers
        cities = {
            # Miami-Dade
            "Downtown Miami": (25.7743, -80.1937),
            "Brickell": (25.7601, -80.1951),
            "Wynwood": (25.8005, -80.1990),
            "Little Haiti": (25.8259, -80.2003),
            "Coral Gables": (25.7215, -80.2684),
            "West Miami": (25.7587, -80.2978),
            "Sweetwater": (25.7631, -80.3720),
            "Doral": (25.8195, -80.3553),
            "Miami Beach": (25.7906, -80.1300),
            "North Miami": (25.8901, -80.1867),
            "Miami Gardens": (25.9420, -80.2456),
            "Hialeah": (25.8576, -80.2781),
            "Kendall": (25.6793, -80.3173),
            "South Miami": (25.7079, -80.2939),
            "Homestead": (25.4687, -80.4776),

            # Broward
            "Pembroke Pines": (26.0086, -80.3570),
            "Miramar": (25.9826, -80.3431),
            "Davie": (26.0814, -80.2806),
            "Hollywood": (26.0112, -80.1495),
            "Aventura": (25.9565, -80.1429),
            "Fort Lauderdale": (26.1224, -80.1373)
        }

        for name, (lat, lng) in cities.items():
            folium.Marker(
                location=(lat, lng),
                tooltip=name,
                popup=f"We deliver to {name}!"
            ).add_to(m)

        # Add store location
        store_lat, store_lng = 25.7617, -80.1918  # Bayfront Park area
        folium.Marker(
            location=(store_lat, store_lng),
            tooltip="🏬 LoveMeNow Store",
            popup="LoveMeNow - Your trusted adult wellness store",
            icon=folium.Icon(color="red", icon="heart", prefix="fa")
        ).add_to(m)

        # Get the map HTML and wrap it properly
        map_html = m._repr_html_()

        # Wrap in a proper HTML document with full height
        canonical_url = url_for('main.miami_map', _external=True)
        full_html = f"""
        <!DOCTYPE html>
        <html lang=\"en\" style=\"height: 100%; margin: 0; padding: 0;\">
        <head>
            <meta charset=\"utf-8\">
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
            <title>Miami Delivery Coverage · LoveMeNow</title>
            <meta name=\"description\" content=\"Interactive Miami-Dade and Broward delivery coverage map for LoveMeNow's same-day service.\">
            <link rel=\"canonical\" href=\"{canonical_url}\">
            <style>
                body {{
                    height: 100vh;
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    background: #f8f9fc;
                    color: #111;
                }}
                .map-shell {{
                    display: grid;
                    grid-template-columns: minmax(280px, 420px) 1fr;
                    height: 100vh;
                }}
                .map-copy {{
                    padding: 2rem;
                    overflow-y: auto;
                    background: #fff;
                    box-shadow: 2px 0 18px rgba(15,23,42,0.08);
                }}
                .map-copy h1 {{ font-size: 1.8rem; margin-bottom: 0.75rem; }}
                .map-copy ul {{ padding-left: 1.2rem; }}
                .map-copy li {{ margin-bottom: 0.35rem; }}
                .folium-panel {{ height: 100vh; }}
                .folium-map {{
                    height: 100vh !important;
                    width: 100% !important;
                }}
                @media (max-width: 900px) {{
                    .map-shell {{ grid-template-columns: 1fr; height: auto; }}
                    .folium-panel {{ height: 60vh; }}
                }}
            </style>
        </head>
        <body>
            <div class=\"map-shell\">
                <section class=\"map-copy\">
                    <h1>Miami Delivery & Pickup Map</h1>
                    <p>LoveMeNow serves every major neighborhood across Miami-Dade and Broward counties with discreet delivery plus in-store pickup from Miami Vape Smoke Shop, 351 NE 79th St.</p>
                    <h2>Featured Neighborhoods</h2>
                    <ul>
                        <li>Brickell, Wynwood, Downtown, and Miami Beach</li>
                        <li>Coral Gables, Kendall, Doral, West Miami</li>
                        <li>Pembroke Pines, Miramar, Hollywood, Fort Lauderdale</li>
                    </ul>
                    <p>Tap any map marker to confirm coverage or call us for bespoke delivery windows.</p>
                </section>
                <div class=\"folium-panel\">{map_html}</div>
            </div>
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

