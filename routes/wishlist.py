"""
Wishlist routes
"""
from flask import Blueprint, request, jsonify, session, current_app
from flask_login import current_user
from sqlalchemy.orm import joinedload

from routes import db
from models import Product, Wishlist
from security import validate_input

wishlist_bp = Blueprint('wishlist', __name__)

@wishlist_bp.route('/add', methods=['POST'])
def add_to_wishlist():
    """Add item to wishlist"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['product_id']
        errors = validate_input(data, required_fields)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        product_id = data['product_id']
        
        # Check if product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if current_user.is_authenticated:
            # For logged-in users, save to database
            existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if existing:
                return jsonify({'message': 'Already in wishlist', 'in_wishlist': True})
            
            wishlist_item = Wishlist(user_id=current_user.id, product_id=product_id)
            db.session.add(wishlist_item)
            db.session.commit()
            
            # Get updated count
            count = Wishlist.query.filter_by(user_id=current_user.id).count()
            return jsonify({'message': 'Added to wishlist', 'in_wishlist': True, 'count': count})
        else:
            # For guest users, use session storage
            if 'wishlist' not in session:
                session['wishlist'] = []
            
            if product_id not in session['wishlist']:
                session['wishlist'].append(product_id)
                session.modified = True
            
            return jsonify({'message': 'Added to wishlist', 'in_wishlist': True, 'count': len(session['wishlist'])})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding to wishlist: {str(e)}")
        return jsonify({'error': 'Failed to add item to wishlist'}), 500

@wishlist_bp.route('/remove', methods=['POST'])
def remove_from_wishlist():
    """Remove item from wishlist"""
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['product_id']
        errors = validate_input(data, required_fields)
        
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        product_id = data['product_id']
        
        if current_user.is_authenticated:
            # For logged-in users, remove from database
            wishlist_item = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if wishlist_item:
                db.session.delete(wishlist_item)
                db.session.commit()
            
            count = Wishlist.query.filter_by(user_id=current_user.id).count()
            return jsonify({'message': 'Removed from wishlist', 'in_wishlist': False, 'count': count})
        else:
            # For guest users, remove from session
            if 'wishlist' in session and product_id in session['wishlist']:
                session['wishlist'].remove(product_id)
                session.modified = True
            
            count = len(session.get('wishlist', []))
            return jsonify({'message': 'Removed from wishlist', 'in_wishlist': False, 'count': count})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing from wishlist: {str(e)}")
        return jsonify({'error': 'Failed to remove item from wishlist'}), 500

@wishlist_bp.route('/check/<int:product_id>')
def check_wishlist_status(product_id):
    """Check if product is in wishlist"""
    try:
        if current_user.is_authenticated:
            exists = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first() is not None
            count = Wishlist.query.filter_by(user_id=current_user.id).count()
        else:
            wishlist = session.get('wishlist', [])
            exists = product_id in wishlist
            count = len(wishlist)
        
        return jsonify({'in_wishlist': exists, 'count': count})
    
    except Exception as e:
        current_app.logger.error(f"Error checking wishlist status: {str(e)}")
        return jsonify({'in_wishlist': False, 'count': 0})

@wishlist_bp.route('/')
def get_wishlist():
    """Get wishlist contents"""
    try:
        if current_user.is_authenticated:
            wishlist_items = (
                db.session.query(Wishlist, Product)
                .join(Product)
                .filter(Wishlist.user_id == current_user.id)
                .order_by(Wishlist.created_at.desc())
                .options(joinedload(Wishlist.product))
                .all()
            )
            products = [item.product for item, product in wishlist_items]
        else:
            wishlist_ids = session.get('wishlist', [])
            products = Product.query.filter(Product.id.in_(wishlist_ids)).all() if wishlist_ids else []
        
        return jsonify({
            'products': [
                {
                    'id': p.id,
                    'name': p.name,
                    'price': float(p.price),
                    'image_url': p.main_image_url,
                    'in_stock': p.in_stock
                }
                for p in products
            ],
            'count': len(products)
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching wishlist: {str(e)}")
        return jsonify({'products': [], 'count': 0})

@wishlist_bp.route('/count')
def get_wishlist_count():
    """Get wishlist item count"""
    try:
        if current_user.is_authenticated:
            count = Wishlist.query.filter_by(user_id=current_user.id).count()
        else:
            count = len(session.get('wishlist', []))
        
        return jsonify({'count': count})
    
    except Exception as e:
        current_app.logger.error(f"Error fetching wishlist count: {str(e)}")
        return jsonify({'count': 0})