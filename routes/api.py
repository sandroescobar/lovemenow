# routes/api.py
"""
API routes for AJAX requests
"""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import stripe
from flask import Blueprint, jsonify, url_for, current_app, request, session
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func, text
from flask import render_template
from types import SimpleNamespace
from email_utils import send_email_sendlayer as send_email_sendlayer_console

from routes import db
from models import (
    Product, ProductVariant, Color, User, Cart, Wishlist, UserAddress,
    Order, OrderItem, UberDelivery, DiscountCode, DiscountUsage
)
from .discount_utils import record_discount_redemption
from security import sanitize_input, validate_input
from routes.discount import discount_bp
from .discount_utils import get_redemptions_for

# IMPORTANT: mount all routes under /api
api_bp = Blueprint('api', __name__, url_prefix='/api')


# -------------------------
# Helpers
# -------------------------
def _to_money(val) -> float:
    if val is None:
        return 0.0
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _cart_items_for_request():
    """
    Return a list of simple items {product, product_id, quantity} for either
    a logged-in user's DB cart or a guest cart stored in session['cart'].
    """
    items = []
    if current_user.is_authenticated:
        db_items = (
            Cart.query.options(joinedload(Cart.product))
            .filter(Cart.user_id == current_user.id)
            .all()
        )
        for it in db_items:
            if it.product:
                items.append({
                    "product": it.product,
                    "product_id": it.product.id,
                    "quantity": int(it.quantity or 0),
                })
    else:
        cart_map = session.get('cart', {}) or {}
        for key, qty in cart_map.items():
            try:
                product_id = int(key.split(':', 1)[0]) if ':' in str(key) else int(key)
            except (TypeError, ValueError):
                continue
            prod = Product.query.get(product_id)
            if prod:
                items.append({"product": prod, "product_id": prod.id, "quantity": int(qty or 0)})
    return items


# -------------------------
# CSRF helper
# -------------------------
@api_bp.route('/csrf-token')
def get_csrf_token():
    """Get a fresh CSRF token for JavaScript requests"""
    from flask_wtf.csrf import generate_csrf
    return jsonify({'csrf_token': generate_csrf()})


# -------------------------
# Product / Variant JSON
# -------------------------
@api_bp.route('/product/<int:product_id>')
def single_product_json(product_id: int):
    """Get single product data as JSON with variant information"""
    try:
        product = (
            Product.query
            .options(
                joinedload(Product.variants).joinedload(ProductVariant.images),
                joinedload(Product.variants).joinedload(ProductVariant.color)
            )
            .get_or_404(product_id)
        )

        default_variant = product.default_variant

        variants = []
        for variant in product.variants:
            variant_data = {
                "id": variant.id,
                "color_id": variant.color_id,
                "color_name": variant.color.name if variant.color else "Default",
                "color_hex": variant.color.hex if variant.color else "#808080",
                "variant_name": variant.variant_name,
                "display_name": variant.display_name,
                # product-level inventory:
                "is_available": product.is_available,
                "quantity_on_hand": product.quantity_on_hand,
                "images": [
                    {
                        "url": (
                            img.url if (img.url.startswith('http') or img.url.startswith('/static/'))
                            else url_for("static", filename=img.url.lstrip("/"))
                        ),
                        "is_primary": img.is_primary,
                        "sort_order": img.sort_order,
                        "alt_text": img.alt_text
                    }
                    for img in sorted(variant.images, key=lambda i: i.sort_order)
                ]
            }
            variants.append(variant_data)

        return jsonify({
            "id": product.id,
            "name": product.name,
            "price": float(product.price),
            "description": product.description,
            "features": (product.features or ""),
            "specifications": product.specifications or "",
            "dimensions": product.dimensions or "",
            "is_available": product.is_available,
            "total_quantity_on_hand": product.total_quantity_on_hand,
            "main_image_url": product.main_image_url,
            "all_image_urls": product.all_image_urls,
            "available_colors": [
                {"id": c.id, "name": c.name, "hex": c.hex, "slug": c.slug}
                for c in product.available_colors
            ],
            "variants": variants,
            "default_variant_id": default_variant.id if default_variant else None
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching product {product_id}: {str(e)}")
        return jsonify({'error': 'Product not found'}), 404


@api_bp.route('/variant/<int:variant_id>')
def single_variant_json(variant_id: int):
    """Get single variant data as JSON"""
    try:
        variant = (
            ProductVariant.query
            .options(
                joinedload(ProductVariant.images),
                joinedload(ProductVariant.color),
                joinedload(ProductVariant.product)
            )
            .get_or_404(variant_id)
        )

        product = variant.product
        return jsonify({
            "id": variant.id,
            "product_id": variant.product_id,
            "product_name": product.name if product else "",
            "color_id": variant.color_id,
            "color_name": variant.color.name if variant.color else "Default",
            "color_hex": variant.color.hex if variant.color else "#808080",
            "variant_name": variant.variant_name,
            "display_name": variant.display_name,
            # product-level inventory:
            "is_available": product.is_available if product else False,
            "quantity_on_hand": product.quantity_on_hand if product else 0,
            "price": float(product.price) if product else 0.0,
            "images": [
                {
                    "url": (
                        img.url if (img.url.startswith('http') or img.url.startswith('/static/'))
                        else url_for("static", filename=img.url.lstrip("/"))
                    ),
                    "is_primary": img.is_primary,
                    "sort_order": img.sort_order,
                    "alt_text": img.alt_text
                }
                for img in sorted(variant.images, key=lambda i: i.sort_order)
            ]
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching variant {variant_id}: {str(e)}")
        return jsonify({'error': 'Variant not found'}), 404


@api_bp.route('/variant/<int:variant_id>/images')
def variant_images(variant_id: int):
    """Get images for a specific product variant based on UPC"""
    try:
        variant = ProductVariant.query.get_or_404(variant_id)
        upc = variant.upc
        if upc:
            images = [
                f"/static/IMG/imagesForLovMeNow/{upc}/{upc}_Main_Photo.png",
                f"/static/IMG/imagesForLovMeNow/{upc}/{upc}_2nd_Photo.png"
            ]
        else:
            images = []

        return jsonify({'success': True, 'images': images, 'variant_id': variant_id, 'upc': upc})

    except Exception as e:
        current_app.logger.error(f"Error fetching variant images {variant_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Error fetching variant images'}), 500


# -------------------------
# Deferred / Colors
# -------------------------
@api_bp.route('/deferred-content')
def get_deferred_content():
    """Get deferred content for performance optimization"""
    from flask import render_template_string

    try:
        featured_products = (
            Product.query
            .options(joinedload(Product.variants), joinedload(Product.category), joinedload(Product.colors))
            .filter(Product.in_stock.is_(True), Product.quantity_on_hand > 0)
            .order_by(Product.created_at.desc())
            .limit(8)
            .all()
        )

        deferred_html = render_template_string('''
        <!-- Featured Products (trimmed) -->
        <section class="container" style="padding: 4rem 1rem;">
          <div class="text-center mb-4">
            <h2 style="font-size: 2.5rem; margin-bottom: 1rem; background: linear-gradient(135deg, hsl(var(--primary-color)), hsl(var(--accent-color))); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Featured Products</h2>
            <p style="font-size: 1.125rem; opacity: 0.8; max-width: 600px; margin: 0 auto;">Carefully curated selection of our most popular intimate products</p>
          </div>
          <div class="product-grid">
            {% for product in featured_products %}
              <div class="product-card fade-in-up" data-product-id="{{ product.id }}" data-in-stock="{{ product.in_stock|lower }}">
                <div class="product-image">
                  {% set imgs = product.all_image_urls %}
                  {% if product.image_url and product.image_url not in imgs %}{% set _ = imgs.append(product.image_url) %}{% endif %}
                  {% if imgs %}
                    <img class="lazy"
                         data-src="{{ imgs[0] if imgs[0].startswith('http') or imgs[0].startswith('/static/') else url_for('static', filename=imgs[0].lstrip('/')) }}"
                         alt="{{ product.name|e }}"
                         style="width:100%;height:250px;object-fit:cover;">
                  {% else %}
                    <div class="placeholder-image"></div>
                  {% endif %}
                </div>
                <div class="product-info">
                  <div class="product-category">{{ product.category.name if product.category else 'Featured' }}</div>
                  <h3 class="product-title"><a href="/product/{{ product.id }}">{{ product.name }}</a></h3>
                  <div class="product-price">${{ '%.2f'|format(product.price) }}</div>
                  <div class="product-buttons">
                    <button class="btn-add-cart"
                            data-product-id="{{ product.id }}"
                            data-product-name="{{ product.name|e }}"
                            data-product-price="{{ product.price }}"
                            {% if not product.is_available %}disabled{% endif %}>
                      {{ 'Add to Cart' if product.is_available else 'Out of Stock' }}
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
    """Get available colors actually used by products"""
    try:
        colors = db.session.query(Color).join(Color.products).distinct().all()
        return jsonify([{"id": c.id, "name": c.name, "hex": c.hex, "slug": c.slug} for c in colors])
    except Exception as e:
        current_app.logger.error(f"Error fetching colors: {str(e)}")
        return jsonify({'error': 'Failed to fetch colors'}), 500


# -------------------------
# Discount endpoints (NEW)
# -------------------------





# -------------------------
# Checkout / Order
# -------------------------
@api_bp.route('/checkout/process', methods=['POST'])
def process_checkout():
    """Process checkout - redirect to proper create_order endpoint"""
    try:
        _ = request.get_json()  # not used here, but keeps parity with your code
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

    # POST
    try:
        data = request.get_json() or {}
        required_fields = ['address', 'city', 'state', 'zip', 'country']
        errors = validate_input(data, required_fields)
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400

        # Remove existing default address
        UserAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})

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



# api.py
@api_bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """
    Create a PaymentIntent for the current cart with server-trusted totals.
    Restrict to CARD only (so Affirm/Amazon/Klarna/CashApp disappear).
    Apple Pay/Google Pay will still work via the card rails.
    """
    try:
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')

        data = request.get_json() or {}
        delivery_type = (data.get('delivery_type') or 'pickup').strip().lower()
        delivery_quote = data.get('delivery_quote') or None

        # Your existing totals function:
        from routes.checkout_totals import compute_totals
        totals = compute_totals(delivery_type=delivery_type, delivery_quote=delivery_quote)

        intent = stripe.PaymentIntent.create(
            amount=int(totals['amount_cents']),
            currency='usd',
            automatic_payment_methods={'enabled': False},  # <-- turn off auto
            payment_method_types=['card'],                 # <-- only card
            metadata={
                'delivery_type': delivery_type,
                'has_quote': '1' if delivery_quote else '0'
            }
        )
        return jsonify({'clientSecret': intent.client_secret})

    except Exception as e:
        current_app.logger.error(f'PI create error: {str(e)}')
        return jsonify({'error': 'Failed to create checkout session'}), 400

@api_bp.route('/create-order', methods=['POST'])
def create_order():
    """Create order after successful payment (server-trusted totals) and send confirmation email (guest or signed-in)."""
    try:
        data = request.get_json() or {}
        required = ['delivery_type', 'customer_info', 'payment_intent_id']
        for f in required:
            if f not in data:
                return jsonify({'error': f'Missing required field: {f}'}), 400

        # 1) Verify PaymentIntent
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        intent = stripe.PaymentIntent.retrieve(data['payment_intent_id'])
        if intent.status != 'succeeded':
            return jsonify({'error': f'Payment not completed. Status: {intent.status}'}), 400

        # 2) Recompute server totals (MUST match the PI amount)
        from routes.checkout_totals import compute_totals
        delivery_type = (data.get('delivery_type') or 'pickup').strip().lower()
        delivery_quote = data.get('delivery_quote') or None
        totals = compute_totals(delivery_type=delivery_type, delivery_quote=delivery_quote)

        if int(intent.amount) != int(totals['amount_cents']):
            current_app.logger.error(
                f"Amount mismatch: PI={intent.amount} vs computed={totals['amount_cents']}"
            )
            return jsonify({'error': 'Order total mismatch. Please refresh and try again.'}), 400

        # 3) Build and save the order
        cust = data['customer_info'] or {}
        order = Order(
            user_id=current_user.id if current_user.is_authenticated else None,
            order_number=f"LMN{datetime.now().strftime('%Y%m%d%H%M%S')}",
            email=cust.get('email', '').strip(),
            full_name=f"{cust.get('first_name','').strip()} {cust.get('last_name','').strip()}".strip(),
            phone=cust.get('phone', '').strip(),
            delivery_type=delivery_type,
            subtotal=totals['subtotal'],
            shipping_amount=totals['delivery_fee'],
            total_amount=totals['total'],
            payment_method='card',
            payment_status='paid',
            stripe_session_id=data.get('payment_intent_id'),  # store PI id
            status='confirmed'
        )

        # shipping / pickup address
        if delivery_type == 'delivery' and 'delivery_address' in data:
            addr = data['delivery_address'] or {}
            order.shipping_address = addr.get('address')
            order.shipping_suite = addr.get('suite', '')
            order.shipping_city = addr.get('city')
            order.shipping_state = addr.get('state')
            order.shipping_zip = addr.get('zip')
            order.shipping_country = addr.get('country', 'US')
            order.delivery_latitude = addr.get('latitude')
            order.delivery_longitude = addr.get('longitude')
        else:
            order.shipping_address = current_app.config.get('STORE_ADDRESS', '1234 Biscayne Blvd')
            order.shipping_suite = current_app.config.get('STORE_SUITE', 'Suite 100')
            order.shipping_city = current_app.config.get('STORE_CITY', 'Miami')
            order.shipping_state = current_app.config.get('STORE_STATE', 'FL')
            order.shipping_zip = current_app.config.get('STORE_ZIP', '33132')
            order.shipping_country = 'US'

        db.session.add(order)
        db.session.flush()  # get order.id

        # Items + inventory updates (same as before)
        if current_user.is_authenticated:
            items_for_inv = Cart.query.filter_by(user_id=current_user.id).all()
        else:
            # reconstruct from session the same way totals did
            from routes.checkout_totals import get_cart_items_for_request
            items_for_inv = get_cart_items_for_request()

        for it in items_for_inv:
            prod = it.product if hasattr(it, 'product') else it["product"]
            qty = int(it.quantity if hasattr(it, 'quantity') else it["quantity"])
            unit_price = float(prod.price)

            db.session.add(OrderItem(
                order_id=order.id,
                product_id=prod.id,
                product_name=prod.name,
                quantity=qty,
                price=unit_price,
                total=unit_price * qty
            ))

            # decrement product-level inventory
            if (prod.quantity_on_hand or 0) >= qty:
                prod.quantity_on_hand = (prod.quantity_on_hand or 0) - qty
                if prod.quantity_on_hand <= 0:
                    prod.in_stock = False
            else:
                prod.quantity_on_hand = 0
                prod.in_stock = False

        # Record discount redemption (fix call signature)
        try:
            if totals.get('discount_amount', 0) > 0:
                from .discount_utils import record_discount_redemption
                record_discount_redemption(
                    order=order,
                    order_subtotal=totals['subtotal'],
                    discount_amount=totals['discount_amount'],
                )
        except Exception as e:
            current_app.logger.error(f"Failed to record discount redemption: {str(e)}")

        # Clear cart
        if current_user.is_authenticated:
            Cart.query.filter_by(user_id=current_user.id).delete()
        session.pop('cart', None)
        session.pop('discount', None)
        session.pop('discount_code', None)
        session.pop('discount_amount', None)
        session['recent_order_id'] = order.id

        db.session.commit()

        # 4) Handle Uber delivery if delivery type is 'delivery'
        tracking_url = None
        uber_delivery = None
        
        if delivery_type == 'delivery':
            try:
                from uber_service import uber_service, create_manifest_items, format_address_for_uber, get_miami_store_address, get_miami_store_coordinates
                
                # Prepare Uber delivery data
                quote_id = data.get('quote_id')
                current_app.logger.info(f"🔍 Delivery order - quote_id: {quote_id}")
                
                # Check if Uber service is configured
                if not uber_service.client_id:
                    current_app.logger.error(f"❌ Uber service not configured - missing credentials")
                    tracking_url = None
                else:
                    # Store pickup/dropoff info
                    store_address = get_miami_store_address()
                    store_coords = get_miami_store_coordinates()
                    
                    pickup_info = {
                        'name': current_app.config.get('STORE_NAME', 'LoveMeNow Miami'),
                        'address': store_address,
                        'phone': order.phone or current_app.config.get('STORE_PHONE', '+13055550123'),
                        'latitude': store_coords['latitude'],
                        'longitude': store_coords['longitude']
                    }
                    
                    # Format delivery address
                    delivery_addr_dict = {
                        'address': order.shipping_address,
                        'suite': order.shipping_suite or '',
                        'city': order.shipping_city,
                        'state': order.shipping_state,
                        'zip': order.shipping_zip,
                        'country': order.shipping_country or 'US'
                    }
                    
                    dropoff_info = {
                        'name': order.full_name or 'Customer',
                        'address': format_address_for_uber(delivery_addr_dict),
                        'phone': order.phone or '+13055550123',
                        'latitude': order.delivery_latitude,
                        'longitude': order.delivery_longitude
                    }
                    
                    current_app.logger.info(f"🔍 Pickup coords: {pickup_info['latitude']}, {pickup_info['longitude']}")
                    current_app.logger.info(f"🔍 Dropoff coords: {dropoff_info['latitude']}, {dropoff_info['longitude']}")
                    
                    # Create manifest items
                    manifest_items = create_manifest_items(items_for_inv)
                    current_app.logger.info(f"🔍 Manifest items: {manifest_items}")
                    
                    # Create the Uber delivery
                    try:
                        current_app.logger.info(f"🔍 Calling uber_service.create_delivery()...")
                        uber_response = uber_service.create_delivery(
                            quote_id=quote_id,
                            pickup_info=pickup_info,
                            dropoff_info=dropoff_info,
                            manifest_items=manifest_items,
                            use_robocourier=False
                        )
                        
                        # Store Uber delivery record
                        tracking_url = uber_response.get('tracking_url')
                        delivery_id = uber_response.get('id')
                        
                        current_app.logger.info(f"✅ Uber API response: delivery_id={delivery_id}, tracking_url={tracking_url}")
                        
                        uber_delivery = UberDelivery(
                            order_id=order.id,
                            quote_id=quote_id,
                            delivery_id=delivery_id,
                            tracking_url=tracking_url,
                            status=uber_response.get('status', 'pending'),
                            fee=data.get('delivery_fee_cents'),
                            currency='usd'
                        )
                        db.session.add(uber_delivery)
                        db.session.commit()
                        
                        current_app.logger.info(f"✅ Uber delivery created for order {order.id}: tracking_url={tracking_url}")
                        
                    except Exception as uber_err:
                        import traceback
                        current_app.logger.error(f"❌ Failed to create Uber delivery: {str(uber_err)}")
                        current_app.logger.error(traceback.format_exc())
                        tracking_url = None
                        # Continue anyway - order is created, just no Uber delivery yet
                    
            except Exception as e:
                import traceback
                current_app.logger.error(f"❌ Error processing Uber delivery: {str(e)}")
                current_app.logger.error(traceback.format_exc())
                tracking_url = None
                # Don't fail the order creation

        # 5) Send order confirmation email (guest or signed-in)
        try:
            buyer_email = (order.email or '').strip()
            if buyer_email:
                # Build a light-weight items list from what we just saved
                # (avoids another query; uses the same data we inserted)
                email_items = []
                for it in items_for_inv:
                    prod = it.product if hasattr(it, 'product') else it["product"]
                    qty = int(it.quantity if hasattr(it, 'quantity') else it["quantity"])
                    unit_price = float(prod.price)
                    email_items.append({
                        "name": prod.name,
                        "quantity": qty,
                        "unit_price": unit_price
                    })

                # Delivery address for template
                delivery_address = {
                    "address": order.shipping_address,
                    "suite": order.shipping_suite or '',
                    "city": order.shipping_city,
                    "state": order.shipping_state,
                    "zip": order.shipping_zip
                }

                # Context mirrors your success page
                # Wrap to avoid Jinja colliding with dict.items; expose attributes like order.items
                order_ns = SimpleNamespace(
                    public_id=order.order_number,
                    items=email_items,
                    delivery_type=order.delivery_type,
                    delivery_address=delivery_address,
                    tracking_url=tracking_url,  # ← NOW INCLUDES TRACKING URL
                )
                totals_ns = SimpleNamespace(
                    subtotal=totals['subtotal'],
                    discount_amount=totals.get('discount_amount', 0),
                    discount_code=totals.get('discount_code'),
                    delivery_fee=totals.get('delivery_fee', 0),
                    tax=totals.get('tax', 0),
                    total=totals['total'],
                )

                ctx = {
                    "customer_name": order.full_name or None,
                    "order": order_ns,
                    "totals": totals_ns,
                    "now": datetime.utcnow,  # expose callable for {{ now().year }} in template
                }

                html_body = render_template("email_confirmation.html", **ctx)

                subject = f"Order #{order.order_number} confirmed — {current_app.config.get('BRAND_NAME', 'LoveMeNow Miami')}"
                send_email_sendlayer_console(order.full_name or "Customer", buyer_email, subject, html_body)
                current_app.logger.info(f"✅ Confirmation email sent to {buyer_email}")
        except Exception as e:
            # Don't fail the order if email send has issues
            current_app.logger.exception(f"❌ Failed to send order confirmation email: {e}")

        return jsonify({
            'success': True,
            'order_id': order.id,
            'order_number': order.order_number,
            'message': 'Order created successfully',
            'tracking_url': tracking_url  # ← RETURN TRACKING URL FOR DELIVERY ORDERS
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating order: {str(e)}")
        return jsonify({'error': f'Failed to create order: {str(e)}'}), 500



@api_bp.get("/discount/stats")   # << use api_bp and no extra /api
def discount_stats():
    code = (request.args.get("code") or "").upper()
    if code != "WELCOME20":
        return jsonify({"ok": False, "error": "Unknown code"}), 404

    TOTAL = 100
    used = 0
    try:
        used = int(get_redemptions_for(code) or 0)
    except Exception as e:
        current_app.logger.warning(f"discount_stats fallback for {code}: {e}")
    remaining = max(0, TOTAL - used)
    return jsonify({"ok": True, "code": code, "total": TOTAL, "remaining": remaining})



# -------------------------
# Health / Admin utilities
# -------------------------
@api_bp.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        current_app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 500


@api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    """Update order status"""
    try:
        data = request.get_json() or {}
        new_status = data.get('status')
        valid_statuses = ['pending', 'processing', 'ready', 'delivered', 'cancelled']
        if new_status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404

        old_status = order.status
        order.status = new_status
        db.session.commit()

        current_app.logger.info(f"Order {order_id} status updated from {old_status} to {new_status}")
        return jsonify({
            'success': True,
            'order_id': order_id,
            'old_status': old_status,
            'new_status': new_status,
            'message': f'Order status updated to {new_status}'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating order status: {str(e)}")
        return jsonify({'error': 'Failed to update order status'}), 500


@api_bp.route('/track-order', methods=['POST'])
def track_order():
    """Track order by order number and email"""
    try:
        data = request.get_json() or {}
        order_number = (data.get('order_number') or '').strip()
        email = (data.get('email') or '').strip().lower()
        if not order_number or not email:
            return jsonify({'error': 'Order number and email are required'}), 400

        order = Order.query.filter_by(order_number=order_number, email=email).first()
        if not order:
            return jsonify({'error': 'Order not found. Please check your order number and email address.'}), 404

        order_data = {
            'id': order.id,
            'order_number': order.order_number,
            'customer_name': order.full_name,
            'customer_email': order.email,
            'status': order.status,
            'delivery_type': order.delivery_type,
            'total_amount': float(order.total_amount),
            'created_at': order.created_at.isoformat(),
            'delivery_info': None
        }

        if order.delivery and order.delivery_type == 'delivery':
            try:
                # Your Uber status refresh logic can live here
                pass
            except Exception as e:
                current_app.logger.error(f"Error updating delivery status for tracking: {str(e)}")

            order_data['delivery_info'] = {
                'status': order.delivery.status if order.delivery else None,
                'tracking_url': order.delivery.tracking_url if order.delivery else None,
                'pickup_eta': order.delivery.pickup_eta.isoformat() if order.delivery and order.delivery.pickup_eta else None,
                'dropoff_eta': order.delivery.dropoff_eta.isoformat() if order.delivery and order.delivery.dropoff_eta else None,
                'courier_name': order.delivery.courier_name if order.delivery else None,
                'courier_phone': order.delivery.courier_phone if order.delivery else None
            }

        return jsonify({'success': True, 'order': order_data})

    except Exception as e:
        current_app.logger.error(f"Error tracking order: {str(e)}")
        return jsonify({'error': 'Failed to track order'}), 500
