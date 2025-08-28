from datetime import datetime
from flask_login import UserMixin
from sqlalchemy.orm import foreign, relationship

from routes import db, bcrypt  # ← come from extensions.py


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    marketing_opt_in = db.Column(db.Boolean, default=False)  # Email marketing consent
    discreet_packaging = db.Column(db.Boolean, default=True)  # Discreet packaging preference
    stripe_customer_id = db.Column(db.String(40))  # optional
    is_admin = db.Column(db.Boolean, default=False)  # Admin role flag
    last_login = db.Column(db.DateTime, nullable=True)  # Track last login for security
    age_verified = db.Column(db.Boolean, default=False)  # Age verification status
    age_verification_date = db.Column(db.DateTime, nullable=True)  # When age was verified

    # Relationships
    addresses = db.relationship('UserAddress', backref='user', lazy='dynamic')

    # ── helper methods ─────────────────────────────────────────
    @property
    def password(self):
        raise AttributeError("password is write‑only")

    @password.setter
    def password(self, plain_pw: str):
        self.password_hash = bcrypt.generate_password_hash(plain_pw).decode()

    def set_password(self, password):
        self.password = password  # ✅ Use the setter

    def check_password(self, plain_pw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, plain_pw)


class UserAddress(db.Model):  # 👈 Capitalized to match class naming convention
    __tablename__ = "user_addresses"

    id = db.Column(db.Integer, primary_key=True)

    # ✅ Foreign key to link address to user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    address = db.Column(db.String(255), nullable=True)
    suite = db.Column(db.String(50), nullable=True)  # changed from Integer → String
    city = db.Column(db.String(255), nullable=True)
    state = db.Column(db.String(255), nullable=True)
    zip = db.Column(db.String(20), nullable=True)  # allow flexibility like '33101-4455'
    country = db.Column(db.String(100), nullable=False)

    is_default = db.Column(db.Boolean, default=False)  # ✅ handles the checkbox


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)

    # Self-referential relationship for hierarchical categories
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))
    products = db.relationship('Product', backref='category', lazy=True)


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    alt_text = db.Column(db.String(255))

    # back-link to Product
    product = db.relationship("Product", back_populates="images")


product_colors = db.Table(
    "product_colors",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id"), primary_key=True),
    db.Column("color_id", db.Integer, db.ForeignKey("colors.id"), primary_key=True),
    extend_existing=True
)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(50), nullable=True)  # Will be added later
    description = db.Column(db.Text, nullable=True)
    specifications = db.Column(db.Text, nullable=True)
    dimensions = db.Column(db.String(200), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)  # Will be added later
    in_stock = db.Column(db.Boolean, default=True)
    quantity_on_hand = db.Column(db.Integer, default=0, nullable=False)
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    colors = db.relationship(
        "Color",
        secondary=product_colors,
        backref=db.backref("products", lazy="dynamic"),
        lazy="joined"
    )

    images = relationship("ProductImage", back_populates="product", lazy="joined")

    @property
    def main_image_url(self):
        """Return url of the image with is_primary = 1 or fall back to image_url."""
        hero = next((img.url for img in self.images if img.is_primary), None)
        image_path = hero or self.image_url
        
        if image_path:
            # Ensure the path starts with /static/ for web serving
            if not image_path.startswith('/static/') and not image_path.startswith('http'):
                return f"/static/{image_path}"
            return image_path
        return None

    @property
    def all_image_urls(self):
        """Return all image URLs for this product."""
        all_images = []

        # Add main image if it exists
        if self.image_url:
            image_url = self.image_url
            # Ensure proper static path
            if not image_url.startswith('/static/') and not image_url.startswith('http'):
                image_url = f"/static/{image_url}"
            all_images.append(image_url)

        # Add additional images from the relationship
        for img in self.images:
            img_url = img.url
            # Ensure proper static path
            if not img_url.startswith('/static/') and not img_url.startswith('http'):
                img_url = f"/static/{img_url}"
            
            if img_url not in all_images:  # Avoid duplicates
                all_images.append(img_url)

        return all_images
    
    @property
    def is_available(self):
        """Check if product is available for purchase"""
        return self.in_stock and self.quantity_on_hand > 0
    
    def can_add_to_cart(self, requested_quantity=1, current_cart_quantity=0):
        """Check if requested quantity can be added to cart"""
        if not self.is_available:
            return False, "This item is currently out of stock"
        
        total_requested = current_cart_quantity + requested_quantity
        if total_requested > self.quantity_on_hand:
            available = self.quantity_on_hand - current_cart_quantity
            if available <= 0:
                return False, "This item is already at maximum quantity in your cart"
            else:
                return False, f"Only {available} more item(s) can be added to cart (stock limit: {self.quantity_on_hand})"
        
        return True, "Available"
    
    def decrement_inventory(self, quantity):
        """Safely decrement inventory and update stock status"""
        if quantity <= 0:
            return False
        
        if self.quantity_on_hand < quantity:
            return False
        
        self.quantity_on_hand -= quantity
        
        # Update in_stock status if quantity reaches 0
        if self.quantity_on_hand <= 0:
            self.in_stock = False
        
        return True


class Wishlist(db.Model):
    __tablename__ = "wishlist"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('wishlist_items', lazy='dynamic'))
    product = db.relationship('Product', backref=db.backref('wishlist_items', lazy='dynamic'))

    # Ensure unique user-product combinations
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_user_product_wishlist'),)


class Color(db.Model):
    __tablename__ = "colors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    hex = db.Column(db.String(7), nullable=False)  # '#6633ff'
    slug = db.Column(db.String(32), unique=True, nullable=False)


class Cart(db.Model):
    __tablename__ = "cart"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='cart_items')
    product = db.relationship('Product', backref='cart_items')
    
    # Ensure unique user-product combinations and add composite index for performance
    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='unique_user_product_cart'),
        db.Index('idx_cart_user_product', 'user_id', 'product_id'),
    )


class Order(db.Model):
    __tablename__ = "orders"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for guest orders
    session_id = db.Column(db.String(255), nullable=True)  # For guest orders
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Customer information
    email = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    
    # Shipping address
    shipping_address = db.Column(db.String(255), nullable=False)
    shipping_suite = db.Column(db.String(50), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=False)
    shipping_state = db.Column(db.String(50), nullable=False)
    shipping_zip = db.Column(db.String(20), nullable=False)
    shipping_country = db.Column(db.String(50), nullable=False, default='US')
    
    # Delivery information
    delivery_type = db.Column(db.String(20), nullable=False, default='pickup')  # 'delivery' or 'pickup'
    delivery_latitude = db.Column(db.Float, nullable=True)  # For delivery address
    delivery_longitude = db.Column(db.Float, nullable=True)  # For delivery address
    
    # Order totals
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    shipping_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Payment information
    payment_method = db.Column(db.String(50), nullable=False)  # 'card', 'paypal', etc.
    payment_status = db.Column(db.String(50), nullable=False, default='pending')  # 'pending', 'paid', 'failed'
    stripe_session_id = db.Column(db.String(255), nullable=True)  # Stripe checkout session ID
    
    # Order status
    status = db.Column(db.String(50), nullable=False, default='pending')  # 'pending', 'processing', 'shipped', 'delivered', 'cancelled'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')
    delivery = db.relationship('UberDelivery', backref='order', uselist=False, cascade='all, delete-orphan')


class OrderItem(db.Model):
    __tablename__ = "order_items"
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Store product details at time of order (in case product changes later)
    product_name = db.Column(db.String(255), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # Price at time of order
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)  # quantity * price
    
    # Relationships
    product = db.relationship('Product', backref='order_items')


class UberDelivery(db.Model):
    __tablename__ = "uber_deliveries"
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    
    # Uber API identifiers
    quote_id = db.Column(db.String(100), nullable=True)  # Uber quote ID
    delivery_id = db.Column(db.String(100), nullable=True)  # Uber delivery ID
    tracking_url = db.Column(db.String(500), nullable=True)  # Uber tracking URL
    
    # Delivery details
    status = db.Column(db.String(50), nullable=False, default='pending')  # 'pending', 'active', 'delivered', 'cancelled'
    fee = db.Column(db.Integer, nullable=True)  # Fee in cents
    currency = db.Column(db.String(3), nullable=False, default='usd')
    
    # Timing information
    pickup_eta = db.Column(db.DateTime, nullable=True)
    dropoff_eta = db.Column(db.DateTime, nullable=True)
    pickup_deadline = db.Column(db.DateTime, nullable=True)
    dropoff_deadline = db.Column(db.DateTime, nullable=True)
    
    # Courier information
    courier_name = db.Column(db.String(100), nullable=True)
    courier_phone = db.Column(db.String(20), nullable=True)
    courier_location_lat = db.Column(db.Float, nullable=True)
    courier_location_lng = db.Column(db.Float, nullable=True)
    
    # Status tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def fee_dollars(self):
        """Convert fee from cents to dollars"""
        return self.fee / 100 if self.fee else 0
    
    @property
    def is_active(self):
        """Check if delivery is currently active"""
        return self.status in ['pending', 'active', 'pickup', 'dropoff']


class AuditLog(db.Model):
    """Audit log for tracking user actions and security events"""
    __tablename__ = "audit_logs"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for anonymous actions
    action = db.Column(db.String(100), nullable=False)  # e.g., 'login', 'logout', 'order_created', 'admin_access'
    resource_type = db.Column(db.String(50), nullable=True)  # e.g., 'user', 'product', 'order'
    resource_id = db.Column(db.String(50), nullable=True)  # ID of the affected resource
    details = db.Column(db.Text, nullable=True)  # Additional details in JSON format
    ip_address = db.Column(db.String(45), nullable=True)  # Support IPv6
    user_agent = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='success')  # 'success', 'failed', 'warning'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
    
    @staticmethod
    def log_action(action, user_id=None, resource_type=None, resource_id=None, 
                   details=None, ip_address=None, user_agent=None, status='success'):
        """Helper method to create audit log entries"""
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status
        )
        db.session.add(log_entry)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log to application logger if database logging fails
            from flask import current_app
            current_app.logger.error(f"Failed to create audit log: {e}")

    @property
    def is_active(self):
        """Check if delivery is currently active"""
        return self.status in ['pending', 'active', 'pickup', 'dropoff']
    
    @property
    def is_completed(self):
        """Check if delivery is completed"""
        return self.status in ['delivered', 'cancelled']