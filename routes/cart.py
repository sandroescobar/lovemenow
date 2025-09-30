"""
Shopping cart routes
"""
from flask import Blueprint, request, jsonify, session, current_app
from flask_login import current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from routes import db
from models import Product, ProductVariant, Cart
from security import validate_input
from routes.main import invalidate_user_counts_cache
from routes.checkout_totals import compute_totals

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/add', methods=['POST'])
def add_to_cart():
    """Add item to cart with per-product stock enforcement across all variants."""
    try:
        data = request.get_json() or {}

        # Validate input
        required_fields = ['product_id']
        errors = validate_input(data, required_fields)
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400

        try:
            product_id = int(data['product_id'])
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid product_id'}), 400

        variant_id = data.get('variant_id')
        try:
            # allow null/empty variant_id
            variant_id = int(variant_id) if variant_id not in (None, '', 'null') else None
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid variant_id'}), 400

        try:
            quantity = int(data.get('quantity', 1))
        except (TypeError, ValueError):
            return jsonify({'error': 'Quantity must be a number'}), 400

        if quantity <= 0:
            return jsonify({'error': 'Quantity must be positive'}), 400

        # Check product
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        if not product.is_available or (product.quantity_on_hand or 0) <= 0:
            return jsonify({'error': 'This item is currently out of stock'}), 400

        total_stock = int(product.quantity_on_hand or 0)

        # ---- Compute how many of THIS PRODUCT are already in the cart (all variants) ----
        if current_user.is_authenticated:
            # Sum all rows for this product for this user
            current_total_for_product = (
                db.session.query(func.coalesce(func.sum(Cart.quantity), 0))
                .filter(Cart.user_id == current_user.id, Cart.product_id == product_id)
                .scalar()
                or 0
            )
        else:
            cart_map = session.get('cart', {}) or {}
            prefix = f"{product_id}:"
            current_total_for_product = 0
            for k, q in cart_map.items():
                try:
                    if k == str(product_id) or str(k).startswith(prefix):
                        current_total_for_product += int(q or 0)
                except (TypeError, ValueError):
                    continue

        # How many more we can add of this product (regardless of variant)
        max_additional = max(0, total_stock - int(current_total_for_product))
        if max_additional <= 0:
            return jsonify({'error': 'This item is out of stock in your cart.'}), 400
        if quantity > max_additional:
            return jsonify({
                'error': f'Only {max_additional} left in stock (you already have {current_total_for_product} in cart).',
                'max_additional': max_additional
            }), 400

        # ---- Update the specific row (variant-specific key) ----
        if current_user.is_authenticated:
            existing = (
                Cart.query
                .filter_by(user_id=current_user.id, product_id=product_id, variant_id=variant_id)
                .first()
            )
            if existing:
                existing.quantity = int(existing.quantity or 0) + quantity
            else:
                db.session.add(Cart(
                    user_id=current_user.id,
                    product_id=product_id,
                    variant_id=variant_id,
                    quantity=quantity
                ))

            db.session.commit()
            # Invalidate cache after cart update
            invalidate_user_counts_cache()

            count = (
                db.session.query(func.coalesce(func.sum(Cart.quantity), 0))
                .filter(Cart.user_id == current_user.id)
                .scalar()
                or 0
            )
        else:
            if 'cart' not in session:
                session['cart'] = {}
            cart = session['cart']

            cart_key = f"{product_id}:{variant_id}" if variant_id is not None else str(product_id)
            current_row_qty = int(cart.get(cart_key, 0) or 0)
            cart[cart_key] = current_row_qty + quantity
            session.modified = True

            try:
                count = sum(int(v or 0) for v in session.get('cart', {}).values())
            except Exception:
                count = 0

        # Remaining stock for the product overall (not per row)
        remaining_stock = max(0, total_stock - (int(current_total_for_product) + quantity))

        return jsonify({
            'message': 'Added to cart',
            'count': int(count),
            'remaining_stock': int(remaining_stock)
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding to cart: {str(e)}")
        return jsonify({'error': 'Failed to add item to cart'}), 500

@cart_bp.route('/remove', methods=['POST'])
def remove_from_cart():
    """Remove item from cart"""
    try:
        data = request.get_json()
        current_app.logger.info(f"Remove from cart request data: {data}")
        
        # Validate input
        required_fields = ['product_id']
        errors = validate_input(data, required_fields)
        
        if errors:
            current_app.logger.error(f"Validation errors: {errors}")
            return jsonify({'error': '; '.join(errors)}), 400
        
        product_id = data['product_id']
        variant_id = data.get('variant_id')
        current_app.logger.info(f"Removing product_id: {product_id}, variant_id: {variant_id}")
        
        if current_user.is_authenticated:
            # Remove product from cart with variant_id
            cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id, variant_id=variant_id).first()
            current_app.logger.info(f"Looking for cart item with user_id={current_user.id}, product_id={product_id}")
            current_app.logger.info(f"Found cart item for authenticated user: {cart_item}")
            
            if cart_item:
                current_app.logger.info(f"Deleting cart item: {cart_item.id} (product_id={cart_item.product_id})")
                db.session.delete(cart_item)
                db.session.commit()
                # Invalidate cache after cart update
                invalidate_user_counts_cache()
                current_app.logger.info("Cart item deleted successfully")
            else:
                current_app.logger.warning(f"No cart item found to delete with product_id={product_id}")
            
            count = db.session.query(func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
            current_app.logger.info(f"New cart count: {count}")
            return jsonify({'message': 'Removed from cart', 'count': count})
        else:
            # For guest users, use product_id:variant_id as key
            cart_key = f"{product_id}:{variant_id}" if variant_id else str(product_id)
            current_app.logger.info(f"Guest user cart key: {cart_key}")
            current_app.logger.info(f"Current session cart: {session.get('cart', {})}")
            if 'cart' in session and cart_key in session['cart']:
                del session['cart'][cart_key]
                session.modified = True
                current_app.logger.info(f"Removed {cart_key} from guest cart")
            else:
                current_app.logger.warning(f"Cart key {cart_key} not found in session")
            
            count = sum(session.get('cart', {}).values())
            current_app.logger.info(f"New guest cart count: {count}")
            return jsonify({'message': 'Removed from cart', 'count': count})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing from cart: {str(e)}")
        return jsonify({'error': 'Failed to remove item from cart'}), 500


@cart_bp.route('/totals', methods=['GET', 'POST'])
def cart_totals():
    """
    Return the canonical pricing breakdown for the current cart.
    Accepts optional delivery quote so we always compute:
      subtotal - discount + delivery + tax -> total
    """
    payload = {}
    if request.method == 'POST':
        payload = request.get_json(silent=True) or {}

    delivery_type = request.args.get('delivery_type') or payload.get('delivery_type') or 'pickup'

    delivery_quote = None
    # Accept either {delivery_quote: {fee_dollars: ...}} or {delivery_fee: ...}
    if 'delivery_quote' in payload and isinstance(payload['delivery_quote'], dict):
        delivery_quote = payload['delivery_quote']
    elif 'delivery_fee' in payload:
        try:
            delivery_quote = {"fee_dollars": float(payload['delivery_fee'])}
        except Exception:
            delivery_quote = None

    # NEW: also support delivery_fee sent as a GET param
    if delivery_quote is None:
        fee_arg = request.args.get('delivery_fee')
        if fee_arg is not None:
            try:
                delivery_quote = {"fee_dollars": float(fee_arg)}
            except Exception:
                pass
    # -----

    totals = compute_totals(delivery_type=delivery_type, delivery_quote=delivery_quote)

    return jsonify({
        "subtotal": totals["subtotal"],
        "discount_amount": totals["discount_amount"],
        "discount_code": totals["discount_code"],
        "delivery_fee": totals["delivery_fee"],
        "tax": totals["tax"],
        "total": totals["total"],
        "amount_cents": totals["amount_cents"],
    })



@cart_bp.route('/update', methods=['POST'])
def update_cart_quantity():
    """Update cart item quantity with per-product stock enforcement across variants."""
    try:
        data = request.get_json() or {}

        # Validate input
        required_fields = ['product_id', 'quantity']
        errors = validate_input(data, required_fields)
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400

        # Parse inputs safely
        try:
            product_id = int(data['product_id'])
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid product_id'}), 400

        variant_id = data.get('variant_id')
        try:
            variant_id = int(variant_id) if variant_id not in (None, '', 'null') else None
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid variant_id'}), 400

        try:
            quantity = int(data['quantity'])
        except (TypeError, ValueError):
            return jsonify({'error': 'Quantity must be a number'}), 400

        if quantity < 0:
            return jsonify({'error': 'Invalid quantity'}), 400

        # If quantity == 0, remove this specific row (respect variant_id)
        if quantity == 0:
            if current_user.is_authenticated:
                cart_item = Cart.query.filter_by(
                    user_id=current_user.id,
                    product_id=product_id,
                    variant_id=variant_id
                ).first()
                if cart_item:
                    db.session.delete(cart_item)
                    db.session.commit()
                    invalidate_user_counts_cache()

                count = (
                    db.session.query(func.coalesce(func.sum(Cart.quantity), 0))
                    .filter(Cart.user_id == current_user.id)
                    .scalar() or 0
                )
                return jsonify({'message': 'Removed from cart', 'count': int(count)})
            else:
                cart_key = f"{product_id}:{variant_id}" if variant_id is not None else str(product_id)
                if 'cart' in session and cart_key in session['cart']:
                    del session['cart'][cart_key]
                    session.modified = True

                try:
                    count = sum(int(v or 0) for v in session.get('cart', {}).values())
                except Exception:
                    count = 0
                return jsonify({'message': 'Removed from cart', 'count': int(count)})

        # For positive quantities, validate product & stock
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        if not product.is_available or (product.quantity_on_hand or 0) <= 0:
            return jsonify({'error': 'Product is out of stock'}), 400

        total_on_hand = int(product.quantity_on_hand or 0)

        # ---- Compute quantity already in cart for this product EXCLUDING the row being updated ----
        if current_user.is_authenticated:
            q = db.session.query(func.coalesce(func.sum(Cart.quantity), 0)).filter(
                Cart.user_id == current_user.id,
                Cart.product_id == product_id
            )
            if variant_id is None:
                # Exclude the "no-variant" row itself; count only rows that DO have a variant_id
                q = q.filter(Cart.variant_id.isnot(None))
            else:
                # Count rows that are not this variant OR are the "no-variant" row
                q = q.filter((Cart.variant_id != variant_id) | (Cart.variant_id.is_(None)))
            other_qty = q.scalar() or 0
        else:
            cart_map = session.get('cart', {}) or {}
            prefix = f"{product_id}:"
            other_qty = 0
            for k, q in cart_map.items():
                try:
                    qi = int(q or 0)
                except (TypeError, ValueError):
                    continue

                if k == str(product_id):
                    # plain (no-variant) row
                    if variant_id is not None:
                        # we're updating a variant row → the plain row counts as "other"
                        other_qty += qi
                    # else we're updating the plain row → exclude it (do nothing)
                elif str(k).startswith(prefix):
                    # key like "product_id:vid"
                    try:
                        vid = int(str(k).split(':', 1)[1])
                    except Exception:
                        vid = None
                    # if it's not the same variant row, count it as "other"
                    if vid != variant_id:
                        other_qty += qi

        # Max allowed for THIS row given what's already in cart for the same product
        max_allowed_for_this_row = max(0, total_on_hand - int(other_qty))
        if quantity > max_allowed_for_this_row:
            return jsonify({
                'error': f'Only {max_allowed_for_this_row} available given what’s already in your cart.',
                'max_quantity': int(max_allowed_for_this_row)
            }), 400

        # ---- Apply update ----
        if current_user.is_authenticated:
            cart_item = Cart.query.filter_by(
                user_id=current_user.id, product_id=product_id, variant_id=variant_id
            ).first()

            if cart_item:
                cart_item.quantity = quantity
            else:
                # Create row if it doesn't exist yet
                db.session.add(Cart(
                    user_id=current_user.id,
                    product_id=product_id,
                    variant_id=variant_id,
                    quantity=quantity
                ))

            db.session.commit()
            invalidate_user_counts_cache()

            count = (
                db.session.query(func.coalesce(func.sum(Cart.quantity), 0))
                .filter(Cart.user_id == current_user.id)
                .scalar() or 0
            )
            return jsonify({'message': 'Cart updated', 'count': int(count)})

        else:
            # Guests: set the row to the new quantity
            if 'cart' not in session:
                session['cart'] = {}
            cart_key = f"{product_id}:{variant_id}" if variant_id is not None else str(product_id)
            session['cart'][cart_key] = quantity
            session.modified = True

            try:
                count = sum(int(v or 0) for v in session.get('cart', {}).values())
            except Exception:
                count = 0

            return jsonify({'message': 'Cart updated', 'count': int(count)})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating cart: {str(e)}")
        return jsonify({'error': 'Failed to update cart'}), 500


@cart_bp.route('/')
def get_cart():
    """Get cart contents"""
    try:
        if current_user.is_authenticated:
            # Simplified query without variants
            cart_items = (
                db.session.query(Cart, Product)
                .join(Product, Cart.product_id == Product.id)
                .filter(Cart.user_id == current_user.id)
                .all()
            )
            
            products = []
            total = 0
            
            for cart_item, product in cart_items:
                try:
                    item_total = float(product.price) * cart_item.quantity
                    total += item_total
                    
                    # Build display name - include variant info if variant_id exists
                    display_name = product.name
                    variant_name = None
                    variant_color = None
                    
                    if cart_item.variant_id:
                        # Find the variant to get its name/color
                        variant = next((v for v in product.variants if v.id == cart_item.variant_id), None)
                        if variant:
                            variant_name = variant.variant_name
                            if variant.color:
                                variant_color = variant.color.name
                                display_name = f"{product.name} - {variant_color}"
                            elif variant_name:
                                display_name = f"{product.name} - {variant_name}"
                    
                    # Use variant-specific image if available
                    image_url = product.main_image_url
                    if cart_item.variant_id:
                        variant = next((v for v in product.variants if v.id == cart_item.variant_id), None)
                        if variant and variant.upc:
                            # Find image that matches variant UPC
                            variant_images = [img for img in product.all_image_urls if variant.upc in img]
                            if variant_images:
                                image_url = variant_images[0]  # Use first matching image
                    
                    products.append({
                        'id': product.id,
                        'variant_id': cart_item.variant_id,
                        'name': display_name,
                        'price': float(product.price),
                        'quantity': cart_item.quantity,
                        'image_url': image_url,
                        'description': product.description or '',
                        'dimensions': product.dimensions or '',
                        'in_stock': product.is_available,
                        'max_quantity': product.quantity_on_hand,
                        'item_total': item_total,
                        'variant_name': variant_name,
                        'variant_color': variant_color
                    })
                except Exception as e:
                    current_app.logger.error(f"Error processing cart item: {e}")
                    # Skip this item and continue
        else:
            cart_items = session.get('cart', {})
            products = []
            total = 0
            
            if cart_items:
                # Simple parsing - just product_ids
                product_ids = []
                cart_data = []
                
                for cart_key, quantity in cart_items.items():
                    # Parse cart_key - could be "product_id" or "product_id:variant_id"
                    if ':' in cart_key:
                        product_id, variant_id = cart_key.split(':', 1)
                        product_id = int(product_id)
                        variant_id = int(variant_id)
                    else:
                        product_id = int(cart_key)
                        variant_id = None
                    
                    product_ids.append(product_id)
                    cart_data.append({
                        'product_id': product_id,
                        'variant_id': variant_id,
                        'quantity': quantity,
                        'cart_key': cart_key
                    })
                
                # Fetch products
                cart_products = Product.query.filter(Product.id.in_(product_ids)).all()
                
                # Create lookup dictionary
                products_dict = {p.id: p for p in cart_products}
                
                for item_data in cart_data:
                    product = products_dict.get(item_data['product_id'])
                    if not product:
                        continue
                        
                    quantity = item_data['quantity']
                    item_total = float(product.price) * quantity
                    total += item_total
                    
                    # Build display name - include variant info if variant_id exists
                    display_name = product.name
                    variant_name = None
                    variant_color = None
                    variant_id = item_data.get('variant_id')
                    
                    if variant_id:
                        # Find the variant to get its name/color
                        variant = next((v for v in product.variants if v.id == variant_id), None)
                        if variant:
                            variant_name = variant.variant_name
                            if variant.color:
                                variant_color = variant.color.name
                                display_name = f"{product.name} - {variant_color}"
                            elif variant_name:
                                display_name = f"{product.name} - {variant_name}"
                    
                    # Use variant-specific image if available
                    image_url = product.main_image_url
                    if variant_id:
                        variant = next((v for v in product.variants if v.id == variant_id), None)
                        if variant and variant.upc:
                            # Find image that matches variant UPC
                            variant_images = [img for img in product.all_image_urls if variant.upc in img]
                            if variant_images:
                                image_url = variant_images[0]  # Use first matching image
                    
                    products.append({
                        'id': product.id,
                        'variant_id': variant_id,
                        'name': display_name,
                        'price': float(product.price),
                        'quantity': quantity,
                        'image_url': image_url,
                        'description': product.description or '',
                        'dimensions': product.dimensions or '',
                        'in_stock': product.is_available,
                        'max_quantity': product.quantity_on_hand,
                        'item_total': item_total,
                        'variant_name': variant_name,
                        'variant_color': variant_color
                    })
        
        # Calculate shipping - will be determined at checkout based on delivery method
        shipping = 0  # No shipping fee in cart, will be calculated at checkout
        
        # Format items for checkout (keeping original structure)
        items = []
        for product in products:
            items.append({
                'product': {
                    'id': product['id'],
                    'name': product['name'],
                    'price': product['price'],
                    'image_url': product['image_url'],
                    'description': product['description']
                },
                'quantity': product['quantity']
            })
        
        return jsonify({
            'items': items,
            'products': products,  # Keep both for compatibility
            'subtotal': total,
            'shipping': shipping,
            'total': total + shipping,
            'count': sum(p['quantity'] for p in products)
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching cart: {str(e)}")
        return jsonify({'error': 'Failed to fetch cart'}), 500

@cart_bp.route('/count')
def get_cart_count():
    """Get cart item count - optimized for speed"""
    try:
        if current_user.is_authenticated:
            # Use a more efficient query with index
            count = (
                db.session.query(func.sum(Cart.quantity))
                .filter(Cart.user_id == current_user.id)
                .scalar() or 0
            )
        else:
            count = sum(session.get('cart', {}).values())
        
        return jsonify({'count': int(count)})
    
    except Exception as e:
        current_app.logger.error(f"Error fetching cart count: {str(e)}")
        return jsonify({'count': 0})

@cart_bp.route('/debug')
def debug_cart():
    """Debug endpoint to check cart state"""
    try:
        debug_info = {
            'user_authenticated': current_user.is_authenticated,
            'user_id': current_user.id if current_user.is_authenticated else None,
            'user_email': current_user.email if current_user.is_authenticated else None,
            'session_cart': session.get('cart', {}),
            'session_keys': list(session.keys()),
        }
        
        if current_user.is_authenticated:
            # Get database cart items
            cart_items = Cart.query.filter_by(user_id=current_user.id).all()
            debug_info['db_cart_items'] = [
                {
                    'id': item.id,
                    'product_id': item.product_id,
                    'quantity': item.quantity,
                    'created_at': item.created_at.isoformat() if item.created_at else None
                }
                for item in cart_items
            ]
            debug_info['db_cart_count'] = sum(item.quantity for item in cart_items)
        else:
            debug_info['db_cart_items'] = []
            debug_info['db_cart_count'] = 0
        
        return jsonify(debug_info)
    
    except Exception as e:
        current_app.logger.error(f"Error in cart debug: {str(e)}")
        return jsonify({'error': str(e)}), 500

@cart_bp.route('/clear', methods=['POST'])
def clear_cart():
    """Clear all items from cart"""
    try:
        if current_user.is_authenticated:
            # Clear database cart for authenticated users
            Cart.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
        else:
            # Clear session cart for guest users
            if 'cart' in session:
                session.pop('cart', None)
                session.modified = True
        
        return jsonify({'success': True, 'message': 'Cart cleared successfully'})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error clearing cart: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to clear cart'}), 500