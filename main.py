import os
from urllib.parse import urlencode
from datetime import timedelta
from flask import Flask, render_template, redirect, request, url_for, flash, session, current_app
from dotenv import load_dotenv
from flask_login import login_user, logout_user
from sqlalchemy import text
from routes import db, bcrypt, login_mgr, csrf
from models     import User
from flask_talisman import Talisman
import secrets
# ← import AFTER extensions declared

# ── env vars ─────────────────────────────────────────────────
load_dotenv()                        # reads .env in local dev

# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"]              = os.getenv("SECRET_KEY", "dev_key")
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=1)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Slack Configuration ─────────────────────────────
app.config["SLACK_WEBHOOK_URL"] = os.getenv("SLACK_WEBHOOK_URL")

# ── Performance optimizations ─────────────────────────────
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # 1 year cache for static files

# ── DISABLE CSP TEMPORARILY TO TEST STRIPE ─────────────────────────────
print("🚫 DISABLING CSP TEMPORARILY TO TEST STRIPE")
print("🚫 This will allow Stripe frames to load without CSP blocking")
# CSP disabled - no Talisman configuration applied

# ── plug extensions into this single app ─────────────────────
db.init_app(app)
bcrypt.init_app(app)
login_mgr.init_app(app)

# TEMPORARILY DISABLE CSRF FOR TESTING
# csrf.init_app(app)
print("🚫 CSRF PROTECTION TEMPORARILY DISABLED FOR CART TESTING")

login_mgr.login_view    = "login_modal"
login_mgr.login_message = "Please log in first."

# ── CSRF Token Function ─────────────────────────────────────────────
@app.context_processor
def inject_csrf_token():
    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return session['csrf_token']
    return dict(csrf_token=csrf_token)

# ── loader callback required by Flask‑Login ──────────────────
@login_mgr.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))

# ── routes (very trimmed) ─────────────────────────────────────
@app.route("/")
def index():
    """Optimized home page with performance improvements"""
    try:
        # Import performance utilities
        from performance_utils import (
            get_featured_products, 
            get_main_categories, 
            get_optimized_user_counts,
            get_fallback_data,
            test_database_connection
        )
        from flask_login import current_user
        
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
        
        # Get data using optimized cached functions
        featured_products = get_featured_products()
        categories = get_main_categories()
        
        # Get cart and wishlist counts using optimized cached function
        cart_count, wishlist_count = get_optimized_user_counts()
        
        return render_template('index.html',
                             featured_products=featured_products,
                             categories=categories,
                             cart_count=cart_count,
                             wishlist_count=wishlist_count,
                             show_age_verification=not age_verified)
        
    except Exception as e:
        current_app.logger.error(f"Error in index route: {e}")
        # If there's any error, return template with empty products
        return render_template("index.html", featured_products=[], show_age_verification=True)

# Products route moved to routes/main.py blueprint

@app.route("/cart")
def cart_page():
    return render_template("cart.html")

@app.route("/about")
def about():
    return "<h1>About Us</h1><p>Coming soon...</p>"

@app.route("/support")
def support():
    return "<h1>Support</h1><p>Coming soon...</p>"

@app.route('/api/verify-age', methods=['POST'])
def verify_age():
    """API endpoint for age verification"""
    from flask import jsonify
    try:
        data = request.get_json()
        if data and data.get('verified'):
            session['age_verified'] = True
            return jsonify({'success': True, 'message': 'Age verified successfully'})
        else:
            return jsonify({'success': False, 'message': 'Age verification failed'}), 400
    except Exception as e:
        current_app.logger.error(f"Error in age verification: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route("/register_modal", methods = ['GET', 'POST'])
def register_modal():

    if request.method == 'POST' and 'full_name' in request.form and 'email' in request.form and 'password' in request.form and 'passwordCon' in request.form:
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        password_confirmation = request.form['passwordCon']

        if password != password_confirmation:
            flash("Passwords do not match")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered", "warning")
            return redirect(url_for("register_modal"))

        user = User(email=email, full_name=full_name)
        user.password = password  # triggers the bcrypt‑hash setter
        db.session.add(user)
        db.session.commit()

    return redirect(url_for("main.index"))


@app.route("/login_modal", methods = ['GET', 'POST'])
def login_modal():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            remember_flag = "remember" in request.form  # True if box checked
            login_user(user, remember=remember_flag)
            flash("you've logged in successfully", "success")
            return redirect(url_for("main.index"))

        flash("Incorrect email or password!", "danger")

    qs = urlencode({"modal": "login"})
    return redirect(f"{url_for('main.index')}?{qs}")



@app.route("/logged_in_modal", methods = ['GET', 'POST'])
def logged_in_modal():
    return render_template("logged_in_modal.html",logged_in=User.is_authenticated)


@app.route("/user_profile", methods = ['GET', 'POST'])
def user_profile():
    return render_template("user_profile.html")

@app.route("/logout")
def logout():
    logout_user()              # clears the session
    flash("You’ve been logged out.", "success")
    return redirect(url_for("main.index"))

@app.route("/user_profile_button")
def user_profile_button():

    return redirect(url_for('user_profile'))

@app.route("/miami-map")
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
        
        # Add store location - Miami Vape Smoke Shop (pickup location)
        store_lat, store_lng = 25.70816, -80.407   # 351 NE 79th St, Miami FL 33138
        folium.Marker(
            location=(store_lat, store_lng),
            tooltip="🏬 Miami Vape Smoke Shop - LoveMeNow Pickup",
            popup="<b>Miami Vape Smoke Shop</b><br>351 NE 79th St<br>Miami, FL 33138<br><em>LoveMeNow Pickup Location</em>",
            icon=folium.Icon(color="red", icon="shopping-cart", prefix="fa")
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
                <div style="margin-top: 2rem; padding: 1.5rem; background: #667eea; color: white; border-radius: 8px;">
                    <h4>🏬 Pickup Location</h4>
                    <p><strong>Miami Vape Smoke Shop</strong></p>
                    <p>351 NE 79th St<br>Miami, FL 33138</p>
                    <p><em>LoveMeNow Pickup Location</em></p>
                </div>
                <p><em>Install folium to see the interactive map</em></p>
            </div>
        </div>
        """
    except Exception as e:
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
                <p><em>Error: {str(e)}</em></p>
            </div>
        </div>
        """

@app.route('/debug/product/<int:product_id>')
def debug_product_images(product_id):
    """Debug route to see raw image URLs"""
    from models import Product
    product = Product.query.get_or_404(product_id)
    
    debug_info = {
        'product_name': product.name,
        'variants': []
    }
    
    for variant in product.variants:
        variant_info = {
            'id': variant.id,
            'color': variant.color.name if variant.color else 'No color',
            'images': []
        }
        
        for img in variant.images:
            variant_info['images'].append({
                'raw_url': img.url,
                'starts_with_http': img.url.startswith('http'),
                'starts_with_static': img.url.startswith('/static/'),
                'starts_with_static_no_slash': img.url.startswith('static/'),
            })
        
        debug_info['variants'].append(variant_info)
    
    return f"<pre>{debug_info}</pre>"

# ── CART API ENDPOINTS ─────────────────────────────────────────────
@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    """Add item to cart (localStorage-based for now)"""
    from flask import jsonify, request
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        variant_id = data.get('variant_id')
        
        if not product_id:
            return jsonify({'error': 'Product ID is required'}), 400
            
        # Validate product exists
        from models import Product, ProductVariant
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
            
        # Validate variant if provided
        if variant_id:
            variant = ProductVariant.query.get(variant_id)
            if not variant or variant.product_id != product_id:
                return jsonify({'error': 'Invalid variant'}), 400
        
        # CRITICAL FIX: Use database Cart model for proper validation
        from models import Cart
        from flask import session
        
        # For now, use session ID for guest users (could be improved with proper guest cart handling)
        if current_user.is_authenticated:
            user_id = current_user.id
            # Get current cart quantity from database
            existing_cart_item = Cart.query.filter_by(
                user_id=user_id, 
                product_id=product_id, 
                variant_id=variant_id
            ).first()
            current_cart_quantity = existing_cart_item.quantity if existing_cart_item else 0
        else:
            # For guest users, use session-based cart (temporary solution)
            cart_key = f'guest_cart_{product_id}_{variant_id or "none"}'
            current_cart_quantity = session.get(cart_key, 0)
        
        # Use product's can_add_to_cart method for validation
        can_add, message = product.can_add_to_cart(quantity, current_cart_quantity)
        
        if not can_add:
            # Calculate how many more can be added
            max_additional = max(0, product.quantity_on_hand - current_cart_quantity)
            return jsonify({
                'error': message,
                'max_additional': max_additional,
                'current_in_cart': current_cart_quantity,
                'stock_available': product.quantity_on_hand
            }), 400
        
        # Update cart in database or session
        if current_user.is_authenticated:
            if existing_cart_item:
                # Update existing cart item
                existing_cart_item.quantity += quantity
            else:
                # Create new cart item
                new_cart_item = Cart(
                    user_id=user_id,
                    product_id=product_id,
                    variant_id=variant_id,
                    quantity=quantity
                )
                db.session.add(new_cart_item)
            
            db.session.commit()
            
            # Calculate total cart count from database
            total_count = db.session.query(db.func.sum(Cart.quantity)).filter_by(user_id=user_id).scalar() or 0
        else:
            # Update session cart for guest users
            session[cart_key] = current_cart_quantity + quantity
            # Calculate total cart count from session
            total_count = sum(session.get(key, 0) for key in session.keys() if key.startswith('guest_cart_'))
        
        # Get updated cart quantity for response
        if current_user.is_authenticated:
            updated_cart_item = Cart.query.filter_by(
                user_id=user_id, 
                product_id=product_id, 
                variant_id=variant_id
            ).first()
            updated_cart_quantity = updated_cart_item.quantity if updated_cart_item else 0
        else:
            updated_cart_quantity = session.get(cart_key, 0)
        
        return jsonify({
            'message': f'{product.name} added to cart!',
            'count': total_count,
            'success': True,
            'current_in_cart': updated_cart_quantity,
            'stock_available': product.quantity_on_hand
        })
        
    except Exception as e:
        print(f"Cart add error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/cart/clear', methods=['POST'])
def api_cart_clear():
    """Clear cart"""
    from flask import jsonify, session
    from models import Cart
    
    try:
        if current_user.is_authenticated:
            # Clear database cart for logged-in users
            Cart.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
        else:
            # Clear session cart for guest users
            cart_keys = [key for key in session.keys() if key.startswith('guest_cart_')]
            for key in cart_keys:
                session.pop(key, None)
        
        return jsonify({
            'message': 'Cart cleared',
            'count': 0,
            'success': True
        })
        
    except Exception as e:
        print(f"Cart clear error: {e}")
        return jsonify({'error': 'Error clearing cart'}), 500

@app.route('/api/cart/count', methods=['GET'])
def api_cart_count():
    """Get current cart count"""
    from flask import jsonify, session
    from models import Cart
    
    try:
        if current_user.is_authenticated:
            # Get count from database for logged-in users
            total_count = db.session.query(db.func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
        else:
            # Get count from session for guest users
            total_count = sum(session.get(key, 0) for key in session.keys() if key.startswith('guest_cart_'))
        
        return jsonify({
            'count': total_count,
            'success': True
        })
        
    except Exception as e:
        print(f"Cart count error: {e}")
        return jsonify({'count': 0, 'error': 'Error getting cart count'}), 500




# ── run & create tables once ─────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()                # <- now User is known, table created
        # quick sanity check
        db.session.execute(text("SELECT 1"))
        print("✅  DB connected and tables ensured.")

    app.run(debug=True, port=5001)
