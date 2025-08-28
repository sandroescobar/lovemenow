"""
API routes for AJAX requests
"""
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, url_for, current_app, request, session
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from routes import db
from models import Product, Color, User, Cart, Wishlist, UserAddress, Order, OrderItem, UberDelivery
from security import sanitize_input, validate_input
from sqlalchemy import func

api_bp = Blueprint('api', __name__)

@api_bp.route('/csrf-token')
def get_csrf_token():
    """Get a fresh CSRF token for JavaScript requests"""
    from flask_wtf.csrf import generate_csrf
    return jsonify({'csrf_token': generate_csrf()})

@api_bp.route('/product/<int:product_id>')
def single_product_json(product_id: int):
    """Get single product data as JSON"""
    try:
        product = (
            Product.query
            .options(joinedload(Product.images))
            .get_or_404(product_id)
        )
        
        return jsonify({
            "id": product.id,
            "name": product.name,
            "price": float(product.price),
            "description": product.description,
            "specifications": product.specifications or "",
            "in_stock": product.in_stock,
            "quantity_on_hand": product.quantity_on_hand,
            "images": [
                {"url": url_for("static", filename=img.url.lstrip("/"))}
                for img in sorted(product.images, key=lambda i: i.sort_order)
            ],
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching product {product_id}: {str(e)}")
        return jsonify({'error': 'Product not found'}), 404

@api_bp.route('/deferred-content')
def get_deferred_content():
    """Get deferred content for performance optimization"""
    from flask import render_template_string
    from models import Product, Category
    
    try:
        # Get featured products (limit for performance)
        featured_products = (
            Product.query
            .options(joinedload(Product.images), joinedload(Product.category), joinedload(Product.colors))
            .filter(Product.in_stock == True)
            .order_by(Product.created_at.desc())
            .limit(8)
            .all()
        )
        
        # Render the deferred content template
        deferred_html = render_template_string('''
        <!-- Miami Delivery & Pickup Section -->
        <section class="miami-service-section">
            <div class="container">
                <div class="miami-content">
                    <div class="miami-info">
                        <div class="service-badge">
                            <i class="fas fa-map-marker-alt"></i>
                            <span>Miami Exclusive</span>
                        </div>
                        <h2>Premium Service Across the Magic City</h2>
                        <p class="miami-description">Experience unparalleled convenience with our discreet delivery and pickup services covering all of Miami-Dade County.</p>

                        <div class="service-features">
                            <div class="service-feature">
                                <div class="feature-icon">
                                    <i class="fas fa-truck"></i>
                                </div>
                                <div class="feature-content">
                                    <h3>Same-Day Delivery</h3>
                                    <p>Order before 2 PM for same-day delivery across Miami</p>
                                </div>
                            </div>

                            <div class="service-feature">
                                <div class="feature-icon">
                                    <i class="fas fa-store"></i>
                                </div>
                                <div class="feature-content">
                                    <h3>Discreet Pickup Points</h3>
                                    <p>Convenient pickup locations in Brickell, Wynwood & Coral Gables</p>
                                </div>
                            </div>

                            <div class="service-feature">
                                <div class="feature-icon">
                                    <i class="fas fa-clock"></i>
                                </div>
                                <div class="feature-content">
                                    <h3>24/7 Service</h3>
                                    <p>Round-the-clock availability for your convenience</p>
                                </div>
                            </div>
                        </div>

                        <div class="miami-cta">
                            <a href="/products" class="btn btn-primary btn-lg">
                                <i class="fas fa-shopping-bag"></i>
                                Shop Miami Collection
                            </a>
                        </div>
                    </div>

                    <div class="miami-visual">
                        <div class="miami-map-container" id="map-container">
                            <iframe src="/miami-map"
                                    class="folium-map"
                                    frameborder="0"
                                    loading="lazy"
                                    title="Miami Coverage Map">
                            </iframe>
                            
                            <div class="coverage-stats">
                                <div class="stat-item">
                                    <div class="stat-number">100+</div>
                                    <div class="stat-label">Areas Covered</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-number">1 Hour</div>
                                    <div class="stat-label">Avg Delivery</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-number">10AM-10PM</div>
                                    <div class="stat-label">Mon-Sun</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Featured Products -->
        <section class="container" style="padding: 4rem 1rem;">
            <div class="text-center mb-4">
                <h2 style="font-size: 2.5rem; margin-bottom: 1rem; background: linear-gradient(135deg, hsl(var(--primary-color)), hsl(var(--accent-color))); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Featured Products</h2>
                <p style="font-size: 1.125rem; opacity: 0.8; max-width: 600px; margin: 0 auto;">Carefully curated selection of our most popular intimate products</p>
            </div>

            <div class="product-grid">
                {% for product in featured_products %}
                <div class="product-card fade-in-up" data-product-id="{{ product.id }}" data-in-stock="{{ product.in_stock|lower }}">
                    <div class="product-image">
                        {% set all_images = [] %}
                        {% if product.image_url %}
                            {% set _ = all_images.append(product.image_url) %}
                        {% endif %}
                        {% for img in product.images %}
                            {% if img.url not in all_images %}
                                {% set _ = all_images.append(img.url) %}
                            {% endif %}
                        {% endfor %}

                        {% if all_images %}
                            <img class="lazy" 
                                 data-src="{{ all_images[0] if all_images[0].startswith('http') else url_for('static', filename=all_images[0].lstrip('/')) }}"
                                 alt="{{ product.name|e }}" 
                                 style="width: 100%; height: 250px; object-fit: cover;">
                        {% else %}
                            <div class="placeholder-image">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                    <circle cx="9" cy="9" r="2"></circle>
                                    <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"></path>
                                </svg>
                            </div>
                        {% endif %}
                        <div class="product-actions">
                            <button class="btn-quick-view" data-product-id="{{ product.id }}">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                    <circle cx="12" cy="12" r="3"></circle>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="product-info">
                        <div class="product-category">{{ product.category.name if product.category else 'Featured' }}</div>
                        <h3 class="product-title">
                            <a href="/product/{{ product.id }}">{{ product.name }}</a>
                        </h3>
                        <div class="product-price">${{ '%.2f'|format(product.price) }}</div>
                        <div class="product-buttons">
                            <button class="btn-add-cart" 
                                    data-product-id="{{ product.id }}"
                                    data-product-name="{{ product.name|e }}"
                                    data-product-price="{{ product.price }}"
                                    {% if not product.is_available %}disabled{% endif %}>
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <circle cx="9" cy="21" r="1"></circle>
                                    <circle cx="20" cy="21" r="1"></circle>
                                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
                                </svg>
                                {{ 'Add to Cart' if product.is_available else 'Out of Stock' }}
                            </button>
                            <button class="btn-wishlist" data-product-id="{{ product.id }}" data-product-name="{{ product.name|e }}">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
        ''', featured_products=featured_products)
        
        return deferred_html
        
    except Exception as e:
        current_app.logger.error(f"Error loading deferred content: {str(e)}")
        return jsonify({'error': 'Failed to load content'}), 500

@api_bp.route('/colors')
def get_colors():
    """Get available colors"""
    try:
        # Get unique colors that are actually used by products
        colors = db.session.query(Color).join(Color.products).distinct().all()
        
        return jsonify([
            {
                "id": color.id,
                "name": color.name,
                "hex": color.hex,
                "slug": color.slug
            }
            for color in colors
        ])
    
    except Exception as e:
        current_app.logger.error(f"Error fetching colors: {str(e)}")
        return jsonify({'error': 'Failed to fetch colors'}), 500

# Cart API endpoints are handled by the cart blueprint at /api/cart/*

# Wishlist API endpoints are handled by the wishlist blueprint at /api/wishlist/*

# Checkout API endpoints
@api_bp.route('/checkout/process', methods=['POST'])
def process_checkout():
    """Process checkout - redirect to proper create_order endpoint"""
    try:
        # Get the request data
        data = request.get_json()
        
        # Call the actual create_order function
        return create_order()
    
    except Exception as e:
        current_app.logger.error(f"Error processing checkout: {str(e)}")
        return jsonify({'error': 'Failed to process checkout'}), 500



@api_bp.route('/user/address', methods=['GET', 'POST'])
@login_required
def user_address():
    """Get or save user's default address"""
    if request.method == 'GET':
        try:
            address = UserAddress.query.filter_by(user_id=current_user.id, is_default=True).first()
            
            if address:
                return jsonify({
                    'address': {
                        'address': address.address,
                        'suite': address.suite,
                        'city': address.city,
                        'state': address.state,
                        'zip': address.zip,
                        'country': address.country
                    }
                })
            else:
                return jsonify({'address': None})
        
        except Exception as e:
            current_app.logger.error(f"Error fetching user address: {str(e)}")
            return jsonify({'address': None})
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Validate input
            required_fields = ['address', 'city', 'state', 'zip', 'country']
            errors = validate_input(data, required_fields)
            
            if errors:
                return jsonify({'error': '; '.join(errors)}), 400
            
            # Remove existing default address
            UserAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
            
            # Create new address
            address = UserAddress(
                user_id=current_user.id,
                address=data['address'],
                suite=data.get('suite', ''),
                city=data['city'],
                state=data['state'],
                zip=data['zip'],
                country=data['country'],
                is_default=True
            )
            
            db.session.add(address)
            db.session.commit()
            
            return jsonify({'message': 'Address saved successfully'})
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving user address: {str(e)}")
            return jsonify({'error': 'Failed to save address'}), 500

@api_bp.route('/user/address')
@login_required
def get_user_address():
    """Get user's default address"""
    try:
        address = UserAddress.query.filter_by(user_id=current_user.id, is_default=True).first()
        
        if address:
            return jsonify({
                'address': {
                    'address': address.address,
                    'suite': address.suite,
                    'city': address.city,
                    'state': address.state,
                    'zip': address.zip,
                    'country': address.country
                }
            })
        else:
            return jsonify({'address': None})
    
    except Exception as e:
        current_app.logger.error(f"Error fetching user address: {str(e)}")
        return jsonify({'address': None})

@api_bp.route('/create-order', methods=['POST'])
def create_order():
    """Create order after successful payment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['delivery_type', 'customer_info', 'payment_intent_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Verify payment with Stripe
        import stripe
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        
        try:
            payment_intent = stripe.PaymentIntent.retrieve(data['payment_intent_id'])
            if payment_intent.status != 'succeeded':
                return jsonify({'error': f'Payment not completed. Status: {payment_intent.status}'}), 400
            current_app.logger.info(f"Payment verified: {payment_intent.id} - Status: {payment_intent.status}")
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe verification failed: {str(e)}")
            return jsonify({'error': 'Payment verification failed'}), 400
        
        # Get cart data
        if current_user.is_authenticated:
            cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        else:
            # Handle session cart
            cart_data = session.get('cart', {})
            cart_items = []
            for product_id, quantity in cart_data.items():
                product = Product.query.get(int(product_id))
                if product:
                    cart_item = type('CartItem', (), {
                        'product': product,
                        'quantity': quantity,
                        'product_id': product.id
                    })()
                    cart_items.append(cart_item)
        
        if not cart_items:
            return jsonify({'error': 'Cart is empty'}), 400
        
        # Calculate totals (convert to float to avoid Decimal + float issues)
        subtotal = float(sum(float(item.product.price) * item.quantity for item in cart_items))
        delivery_fee = 0.0
        
        if data['delivery_type'] == 'delivery':
            if 'delivery_quote' in data and data['delivery_quote']:
                delivery_fee = float(data['delivery_quote'].get('fee_dollars', 0))
            elif subtotal < 100:
                delivery_fee = 9.99
        
        total = subtotal + delivery_fee
        
        # Create order
        order = Order(
            user_id=current_user.id if current_user.is_authenticated else None,
            order_number=f"LMN{datetime.now().strftime('%Y%m%d%H%M%S')}",
            email=data['customer_info']['email'],
            full_name=f"{data['customer_info']['first_name']} {data['customer_info']['last_name']}",
            delivery_type=data['delivery_type'],
            subtotal=subtotal,
            shipping_amount=delivery_fee,
            total_amount=total,
            payment_method='card',
            payment_status='paid',
            stripe_session_id=data.get('payment_intent_id'),  # Optional Stripe session ID
            status='confirmed'
        )
        
        # Add delivery address if delivery type, otherwise use store address for pickup
        if data['delivery_type'] == 'delivery' and 'delivery_address' in data:
            addr = data['delivery_address']
            order.shipping_address = addr['address']
            order.shipping_suite = addr.get('suite', '')
            order.shipping_city = addr['city']
            order.shipping_state = addr['state']
            order.shipping_zip = addr['zip']
            order.shipping_country = addr.get('country', 'US')
            # Set delivery coordinates if available
            order.delivery_latitude = addr.get('latitude')
            order.delivery_longitude = addr.get('longitude')
        else:
            # For pickup orders, use store address
            order.shipping_address = current_app.config.get('STORE_ADDRESS', '1234 Biscayne Blvd')
            order.shipping_suite = current_app.config.get('STORE_SUITE', 'Suite 100')
            order.shipping_city = current_app.config.get('STORE_CITY', 'Miami')
            order.shipping_state = current_app.config.get('STORE_STATE', 'FL')
            order.shipping_zip = current_app.config.get('STORE_ZIP', '33132')
            order.shipping_country = 'US'
            # For pickup orders, coordinates are not needed (will remain NULL)
        
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Create order items and update inventory (only after payment verification)
        for item in cart_items:
            unit_price = float(item.product.price)
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                product_name=item.product.name,
                quantity=item.quantity,
                price=unit_price,
                total=unit_price * item.quantity
            )
            db.session.add(order_item)
            
            # Update product inventory using the model's method
            product = item.product
            success = product.decrement_inventory(item.quantity)
            if success:
                current_app.logger.info(f"Updated inventory for product {product.id}: {product.name}, new quantity: {product.quantity_on_hand}")
            else:
                current_app.logger.warning(f"Insufficient inventory for product {product.id}: {product.name}, requested: {item.quantity}, available: {product.quantity_on_hand}")
                # Still process the order but set product as out of stock
                product.quantity_on_hand = 0
                product.in_stock = False
        
        # Initialize response data early
        response_data = {}
        
        # Create Uber delivery if needed
        if data['delivery_type'] == 'delivery':
            current_app.logger.info("Processing delivery order - attempting Uber Direct creation")
            
            # For testing: create a mock quote if none provided
            if not ('delivery_quote' in data and data['delivery_quote']):
                current_app.logger.info("No delivery quote provided - creating mock quote for testing")
                data['delivery_quote'] = {
                    'id': f'dqt_test_{datetime.now().strftime("%Y%m%d%H%M%S")}',
                    'fee': 799,  # $7.99 in cents
                    'currency': 'usd'
                }
            try:
                from routes.uber import uber_bp
                # Import the uber service
                from uber_service import uber_service, get_miami_store_address, get_miami_store_coordinates, format_address_for_uber, create_manifest_items
                
                # Prepare delivery creation
                quote_id = data['delivery_quote']['id']
                
                # Prepare pickup information (store)
                store_coords = get_miami_store_coordinates()
                pickup_info = {
                    'address': get_miami_store_address(),
                    'name': current_app.config.get('STORE_NAME', 'LoveMeNow Miami'),
                    'phone': current_app.config.get('STORE_PHONE', '+1234567890'),
                    'latitude': store_coords['latitude'],
                    'longitude': store_coords['longitude']
                }
                
                # Prepare dropoff information (customer)
                dropoff_address = data['delivery_address']
                
                # Format customer phone number properly (E.164 format)
                customer_phone = data['customer_info'].get('phone', '+13055550199')
                # Clean and format phone number
                import re
                cleaned_phone = re.sub(r'[^\d+]', '', customer_phone)
                if not cleaned_phone.startswith('+1'):
                    if cleaned_phone.startswith('1'):
                        cleaned_phone = '+' + cleaned_phone
                    else:
                        cleaned_phone = '+1' + cleaned_phone
                customer_phone = cleaned_phone
                
                dropoff_info = {
                    'address': format_address_for_uber(dropoff_address),
                    'name': order.full_name,
                    'phone': customer_phone,
                    'latitude': None,  # Will be geocoded by Uber
                    'longitude': None
                }
                
                # Create manifest items from cart
                cart_items_for_manifest = []
                for item in cart_items:
                    cart_items_for_manifest.append({
                        'product': {
                            'id': item.product_id,
                            'name': item.product.name
                        },
                        'quantity': item.quantity
                    })
                
                manifest_items = create_manifest_items(cart_items_for_manifest)
                
                # Create delivery with Uber Direct API using Robocourier for testing
                current_app.logger.info("Creating Uber Direct delivery with Robocourier testing")
                
                delivery_response = uber_service.create_delivery(
                    quote_id, pickup_info, dropoff_info, manifest_items, use_robocourier=True
                )
                
                current_app.logger.info(f"Uber Direct delivery created with tracking URL: {delivery_response.get('tracking_url')}")
                
                # Save delivery information to database
                uber_delivery = UberDelivery(
                    order_id=order.id,
                    quote_id=quote_id,
                    delivery_id=delivery_response['id'],
                    tracking_url=delivery_response.get('tracking_url'),
                    status=delivery_response.get('status', 'pending'),
                    fee=delivery_response.get('fee'),
                    currency=delivery_response.get('currency', 'usd'),
                    pickup_eta=datetime.fromisoformat(delivery_response['pickup_eta'].replace('Z', '+00:00')) if delivery_response.get('pickup_eta') else None,
                    dropoff_eta=datetime.fromisoformat(delivery_response['dropoff_eta'].replace('Z', '+00:00')) if delivery_response.get('dropoff_eta') else None
                )
                
                db.session.add(uber_delivery)
                
                # Immediately add tracking URL to response if available
                if delivery_response.get('tracking_url'):
                    response_data['tracking_url'] = delivery_response['tracking_url']
                    response_data['message'] = 'Order created successfully! You can track your delivery using the provided tracking URL.'
                    current_app.logger.info(f"Added tracking URL to response immediately: {delivery_response['tracking_url']}")
                
            except Exception as delivery_error:
                current_app.logger.error(f"Error creating Uber delivery: {str(delivery_error)}")
                # Log the error but don't fail the order creation
                # The order will be created without delivery tracking
                current_app.logger.error(f"Uber delivery creation failed, order will be created without tracking")
        
        # Clear cart and store recent order ID for redirect handling
        if current_user.is_authenticated:
            Cart.query.filter_by(user_id=current_user.id).delete()
            # Store recent order ID in session for authenticated users too
            session['recent_order_id'] = order.id
        else:
            session.pop('cart', None)
            # Store recent order ID in session for guest users
            session['recent_order_id'] = order.id
        
        db.session.commit()
        
        # Update response data with order information, preserving any existing data (like tracking_url)
        response_data.update({
            'success': True,
            'order_id': order.id,
            'order_number': order.order_number,
            'message': response_data.get('message', 'Order created successfully')
        })
        
        current_app.logger.info(f"Preparing response for order {order.id}, delivery_type: {data.get('delivery_type')}")
        current_app.logger.info(f"Final response data: {response_data}")
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating order: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Failed to create order: {str(e)}'}), 500

@api_bp.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected'
        })
    
    except Exception as e:
        current_app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected'
        }), 500