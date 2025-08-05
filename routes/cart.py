"""
Shopping cart routes
"""
from flask import Blueprint, request, jsonify, session, current_app
from flask_login import current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from routes import db
from models import Product, Cart
from security import validate_input

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
        quantity = data.get('quantity', 1)
        
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be positive'}), 400
        
        # Check if product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Check if product is available
        if not product.is_available:
            return jsonify({'error': 'This item is currently out of stock'}), 400
        
        if current_user.is_authenticated:
            # For logged-in users, save to database
            existing = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
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
                cart_item = Cart(user_id=current_user.id, product_id=product_id, quantity=quantity)
                db.session.add(cart_item)
            
            db.session.commit()
            
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
            current_cart_quantity = cart.get(str(product_id), 0)
            
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
            
            cart[str(product_id)] = new_total_quantity
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
        
        # Validate input
        required_fields = ['product_id']
        errors = validate_input(data, required_fields)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        product_id = data['product_id']
        
        if current_user.is_authenticated:
            cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if cart_item:
                db.session.delete(cart_item)
                db.session.commit()
            
            count = db.session.query(func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
            return jsonify({'message': 'Removed from cart', 'count': count})
        else:
            if 'cart' in session and str(product_id) in session['cart']:
                del session['cart'][str(product_id)]
                session.modified = True
            
            count = sum(session.get('cart', {}).values())
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
        quantity = data['quantity']
        
        if quantity < 0:
            return jsonify({'error': 'Invalid quantity'}), 400
        
        if quantity == 0:
            return remove_from_cart()
        
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
            cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if cart_item:
                cart_item.quantity = quantity
                db.session.commit()
            
            count = db.session.query(func.sum(Cart.quantity)).filter_by(user_id=current_user.id).scalar() or 0
            return jsonify({'message': 'Cart updated', 'count': count})
        else:
            if 'cart' in session and str(product_id) in session['cart']:
                session['cart'][str(product_id)] = quantity
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
            # Optimized query with selective loading - only load what we need
            cart_items = (
                db.session.query(Cart, Product)
                .join(Product, Cart.product_id == Product.id)
                .filter(Cart.user_id == current_user.id)
                .all()
            )
            
            products = []
            total = 0
            
            for cart_item, product in cart_items:
                item_total = float(product.price) * cart_item.quantity
                total += item_total
                
                products.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price),
                    'quantity': cart_item.quantity,
                    'image_url': product.main_image_url,
                    'description': product.description or '',
                    'dimensions': product.dimensions or '',
                    'in_stock': product.is_available,
                    'max_quantity': product.quantity_on_hand,
                    'item_total': item_total
                })
        else:
            cart_ids = session.get('cart', {})
            products = []
            total = 0
            
            if cart_ids:
                # Convert string keys to integers for the query
                product_ids = [int(pid) for pid in cart_ids.keys()]
                
                # Optimized query - only select needed fields
                cart_products = (
                    Product.query
                    .filter(Product.id.in_(product_ids))
                    .all()
                )
                
                for product in cart_products:
                    quantity = cart_ids[str(product.id)]
                    item_total = float(product.price) * quantity
                    total += item_total
                    
                    products.append({
                        'id': product.id,
                        'name': product.name,
                        'price': float(product.price),
                        'quantity': quantity,
                        'image_url': product.main_image_url,
                        'description': product.description or '',
                        'dimensions': product.dimensions or '',
                        'in_stock': product.is_available,
                        'max_quantity': product.quantity_on_hand,
                        'item_total': item_total
                    })
        
        # Calculate shipping
        shipping = 9.99 if total > 0 and total < 50 else 0
        
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