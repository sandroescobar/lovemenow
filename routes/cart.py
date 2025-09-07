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

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/add', methods=['POST'])
def add_to_cart():
    """Add item to cart"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['product_id']
        errors = validate_input(data, required_fields)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        product_id = data['product_id']
        variant_id = data.get('variant_id')
        quantity = data.get('quantity', 1)
        
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be positive'}), 400
        
        # Check if product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Handle variant_id for products with color variants
        
        # Check if product is available
        if not product.is_available:
            return jsonify({'error': 'This item is currently out of stock'}), 400
        
        if current_user.is_authenticated:
            # For logged-in users, save to database
            existing = Cart.query.filter_by(user_id=current_user.id, product_id=product_id, variant_id=variant_id).first()
            current_cart_quantity = existing.quantity if existing else 0
            
            # Check if requested quantity can be added
            can_add, message = product.can_add_to_cart(quantity, current_cart_quantity)
            if not can_add:
                available = product.quantity_on_hand - current_cart_quantity
                if available <= 0:
                    return jsonify({'error': message}), 400
                else:
                    return jsonify({
                        'error': message,
                        'max_additional': available
                    }), 400
            
            new_total_quantity = current_cart_quantity + quantity
            
            if existing:
                existing.quantity = new_total_quantity
            else:
                cart_item = Cart(user_id=current_user.id, product_id=product_id, variant_id=variant_id, quantity=quantity)
                db.session.add(cart_item)
            
            db.session.commit()
            
            # Invalidate cache after cart update
            invalidate_user_counts_cache()
            
            # Get updated count
            count = db.session.query(func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
            
            # Get remaining stock after this addition
            remaining_stock = product.quantity_on_hand - new_total_quantity
            
            return jsonify({
                'message': 'Added to cart', 
                'count': count,
                'remaining_stock': remaining_stock
            })
        else:
            # For guest users, use session storage
            if 'cart' not in session:
                session['cart'] = {}
            
            cart = session['cart']
            # Use product_id as key, include variant_id if provided for color variants
            cart_key = f"{product_id}:{variant_id}" if variant_id else str(product_id)
            current_cart_quantity = cart.get(cart_key, 0)
            
            # Check if requested quantity can be added
            can_add, message = product.can_add_to_cart(quantity, current_cart_quantity)
            if not can_add:
                available = product.quantity_on_hand - current_cart_quantity
                if available <= 0:
                    return jsonify({'error': message}), 400
                else:
                    return jsonify({
                        'error': message,
                        'max_additional': available
                    }), 400
            
            new_total_quantity = current_cart_quantity + quantity
            
            cart[cart_key] = new_total_quantity
            session.modified = True
            count = sum(cart.values())
            
            # Get remaining stock after this addition
            remaining_stock = product.quantity_on_hand - new_total_quantity
            
            return jsonify({
                'message': 'Added to cart', 
                'count': count,
                'remaining_stock': remaining_stock
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

@cart_bp.route('/update', methods=['POST'])
def update_cart_quantity():
    """Update cart item quantity"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['product_id', 'quantity']
        errors = validate_input(data, required_fields)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        product_id = data['product_id']
        variant_id = data.get('variant_id')
        quantity = data['quantity']
        
        if quantity < 0:
            return jsonify({'error': 'Invalid quantity'}), 400
        
        if quantity == 0:
            # If quantity is 0, remove the item directly
            if current_user.is_authenticated:
                cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
                if cart_item:
                    db.session.delete(cart_item)
                    db.session.commit()
                    # Invalidate cache after cart update
                    invalidate_user_counts_cache()
                
                count = db.session.query(func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
                return jsonify({'message': 'Removed from cart', 'count': count})
            else:
                # For guest users, use just product_id as key
                cart_key = str(product_id)
                if 'cart' in session and cart_key in session['cart']:
                    del session['cart'][cart_key]
                    session.modified = True
                
                count = sum(session.get('cart', {}).values())
                return jsonify({'message': 'Removed from cart', 'count': count})
        
        # Check product stock availability
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if not product.is_available:
            return jsonify({'error': 'Product is out of stock'}), 400
        
        if quantity > product.quantity_on_hand:
            return jsonify({
                'error': f'Only {product.quantity_on_hand} item(s) available in stock',
                'max_quantity': product.quantity_on_hand
            }), 400
        
        if current_user.is_authenticated:
            # Update product in cart with variant_id
            cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id, variant_id=variant_id).first()
            if cart_item:
                cart_item.quantity = quantity
                db.session.commit()
                # Invalidate cache after cart update
                invalidate_user_counts_cache()
            
            count = db.session.query(func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
            return jsonify({'message': 'Cart updated', 'count': count})
        else:
            # For guest users, use product_id:variant_id as key
            cart_key = f"{product_id}:{variant_id}" if variant_id else str(product_id)
            if 'cart' in session and cart_key in session['cart']:
                session['cart'][cart_key] = quantity
                session.modified = True
            
            count = sum(session.get('cart', {}).values())
            return jsonify({'message': 'Cart updated', 'count': count})
    
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