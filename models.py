from datetime import datetime
from flask_login import UserMixin
from routes import db, bcrypt

FORCE_PRODUCT_STOCK_IDS = {149, 150}

# ─────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    marketing_opt_in = db.Column(db.Boolean, default=False)
    discreet_packaging = db.Column(db.Boolean, default=True)
    stripe_customer_id = db.Column(db.String(40))
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, nullable=True)
    age_verified = db.Column(db.Boolean, default=False)
    age_verification_date = db.Column(db.DateTime, nullable=True)

    # Relationships
    addresses = db.relationship("UserAddress", backref="user", lazy="dynamic")

    # Helpers
    @property
    def password(self):
        raise AttributeError("password is write-only")

    @password.setter
    def password(self, plain_pw: str):
        self.password_hash = bcrypt.generate_password_hash(plain_pw).decode()

    def set_password(self, password):
        self.password = password

    def check_password(self, plain_pw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, plain_pw)


class UserAddress(db.Model):
    __tablename__ = "user_addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    address = db.Column(db.String(255), nullable=True)
    suite = db.Column(db.String(50), nullable=True)
    city = db.Column(db.String(255), nullable=True)
    state = db.Column(db.String(255), nullable=True)
    zip = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), nullable=False)

    is_default = db.Column(db.Boolean, default=False)


# ─────────────────────────────────────────────────────────────
# Catalog
# ─────────────────────────────────────────────────────────────

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    children = db.relationship("Category", backref=db.backref("parent", remote_side=[id]))
    products = db.relationship("Product", backref="category", lazy=True)


class ProductVariant(db.Model):
    __tablename__ = "product_variants"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    color_id = db.Column(db.Integer, db.ForeignKey("colors.id"), nullable=True)

    variant_name = db.Column(db.String(100), nullable=True)
    upc = db.Column(db.String(50), nullable=True)
    
    # Variant-level stock (overrides product-level if set)
    in_stock = db.Column(db.Boolean, nullable=True)
    quantity_on_hand = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship("Product", back_populates="variants")
    color = db.relationship("Color", backref="product_variants")

    __table_args__ = (
        db.UniqueConstraint("product_id", "color_id", name="unique_product_color_variant"),
        db.Index("idx_variant_product_color", "product_id", "color_id"),
    )

    def uses_product_stock(self):
        if not self.product:
            return False
        if self.product.force_product_inventory:
            return True
        return len(self.product.variants or []) <= 1

    def available_stock(self):
        if not self.product:
            return 0
        if self.uses_product_stock():
            return self.product.quantity_on_hand or 0
        if self.quantity_on_hand is not None:
            return self.quantity_on_hand
        return self.product.quantity_on_hand or 0

    def effective_in_stock(self):
        if not self.product:
            return False
        if self.uses_product_stock():
            return bool(self.product.in_stock)
        if self.in_stock is not None:
            return bool(self.in_stock)
        return bool(self.product.in_stock)

    @property
    def is_available(self):
        if not self.product or self.product.in_active:
            return False
        return self.effective_in_stock() and self.available_stock() > 0

    def can_add_to_cart(self, requested_quantity=1, current_cart_quantity=0):
        if not self.is_available:
            return False, "This item is currently out of stock"

        stock_qty = self.available_stock()
        total_requested = current_cart_quantity + requested_quantity
        if total_requested > stock_qty:
            available = stock_qty - current_cart_quantity
            if available <= 0:
                return False, "This item is already at maximum quantity in your cart"
            return False, f"Only {available} more item(s) can be added to cart (stock limit: {stock_qty})"
        return True, "Available"

    def decrement_inventory(self, quantity):
        if quantity <= 0:
            return False

        if self.uses_product_stock():
            if (self.product.quantity_on_hand or 0) < quantity:
                return False
            self.product.quantity_on_hand -= quantity
            if self.product.quantity_on_hand <= 0:
                self.product.in_stock = False
            return True

        if self.quantity_on_hand is not None:
            if (self.quantity_on_hand or 0) < quantity:
                return False
            self.quantity_on_hand -= quantity
            if self.quantity_on_hand <= 0:
                self.in_stock = False
            return True

        if (self.product.quantity_on_hand or 0) < quantity:
            return False
        self.product.quantity_on_hand -= quantity
        if self.product.quantity_on_hand <= 0:
            self.product.in_stock = False
        return True

    @property
    def display_name(self):
        if self.product:
            return self.product.variant_display_name(variant=self)
        label = (self.color.name if self.color else None) or (self.variant_name or None)
        return label or ""


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    alt_text = db.Column(db.String(255))

    variant = db.relationship("ProductVariant", backref="images")


product_colors = db.Table(
    "product_colors",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id"), primary_key=True),
    db.Column("color_id", db.Integer, db.ForeignKey("colors.id"), primary_key=True),
    extend_existing=True,
)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    upc = db.Column(db.String(50), nullable=True)
    base_upc = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    features = db.Column(db.Text, nullable=True)  # newline-separated or JSON-like text of feature bullets
    specifications = db.Column(db.Text, nullable=True)
    dimensions = db.Column(db.String(200), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    compare_at_price = db.Column(db.Numeric(10, 2), nullable=True)
    wholesale_id = db.Column(db.Integer, nullable=True)
    wholesale_price = db.Column(db.Float, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    in_stock = db.Column(db.Boolean, default=True)
    quantity_on_hand = db.Column(db.Integer, default=0, nullable=False)
    in_active = db.Column(db.Boolean, default=False, nullable=False)
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    variants = db.relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    colors = db.relationship(
        "Color",
        secondary=product_colors,
        backref=db.backref("products", lazy="dynamic"),
        lazy="joined",
    )

    @property
    def force_product_inventory(self):
        return (self.id or 0) in FORCE_PRODUCT_STOCK_IDS

    @property
    def default_variant(self):
        if not self.variants:
            return None
        if len(self.variants) == 1:
            return self.variants[0]
        suffix = None
        name = self.name or ""
        if "(" in name and name.endswith(")"):
            suffix = name.rsplit("(", 1)[1][:-1].strip().lower()
        if suffix:
            for variant in self.variants:
                variant_label = (variant.variant_name or "").strip().lower()
                color_label = (variant.color.name if variant.color else "").strip().lower()
                if variant_label == suffix or color_label == suffix:
                    return variant
        for variant in self.variants:
            if variant.is_available:
                return variant
        return self.variants[0]

    @property
    def main_image_url(self):
        default_variant = self.default_variant
        if default_variant and default_variant.images:
            hero = next((img.url for img in default_variant.images if img.is_primary), None)
            image_path = hero or sorted(default_variant.images, key=lambda x: x.sort_order)[0].url
        else:
            image_path = None

        if image_path:
            if not image_path.startswith("/static/") and not image_path.startswith("http"):
                return f"/static/{image_path}"
            return image_path
        return None

    @property
    def all_image_urls(self):
        all_images = []
        ordered_variants = list(self.variants or [])
        dv = self.default_variant
        if dv:
            ordered_variants.sort(key=lambda v: 0 if v.id == dv.id else 1)
        for variant in ordered_variants:
            for img in sorted(variant.images, key=lambda x: x.sort_order):
                img_url = img.url
                if not img_url.startswith("/static/") and not img_url.startswith("http"):
                    img_url = f"/static/{img_url}"
                if img_url not in all_images:
                    all_images.append(img_url)
        return all_images

    @property
    def is_available(self):
        if self.in_active:
            return False
        if self.in_stock and (self.quantity_on_hand or 0) > 0:
            return True
        if len(self.variants or []) > 1 and not self.force_product_inventory:
            return any(
                (variant.in_stock is not None and variant.in_stock and (variant.quantity_on_hand or 0) > 0)
                for variant in self.variants
            )
        return False

    @property
    def total_quantity_on_hand(self):
        return self.quantity_on_hand

    @property
    def available_colors(self):
        return list(self.colors)

    @property
    def all_colors(self):
        return [variant.color for variant in self.variants if variant.color]

    def get_variant_by_color(self, color_id):
        return next((v for v in self.variants if v.color_id == color_id), None)

    def get_variant_by_id(self, variant_id):
        return next((v for v in self.variants if v.id == variant_id), None)

    def can_add_to_cart(self, requested_quantity=1, current_cart_quantity=0):
        dv = self.default_variant
        if not dv:
            return False, "Product variant not available"
        return dv.can_add_to_cart(requested_quantity, current_cart_quantity)

    def decrement_inventory(self, quantity):
        if quantity <= 0 or self.quantity_on_hand < quantity:
            return False
        self.quantity_on_hand -= quantity
        if self.quantity_on_hand <= 0:
            self.in_stock = False
        return True

    def variant_display_name(self, variant=None, preferred_label=None):
        base_name = (self.name or "").strip()
        label = preferred_label
        if not label and variant:
            vn = (variant.variant_name or "").strip()
            if vn and vn.lower() != "default":
                label = vn
            else:
                label = (variant.color.name if variant and variant.color else None) or (variant.variant_name or None)
        if not label:
            return base_name
        if not base_name:
            return label
        if "(" in base_name and base_name.endswith(")"):
            head = base_name.rsplit("(", 1)[0].rstrip()
            return f"{head} ({label})"
        return f"{base_name} ({label})"

    @property
    def clean_name(self):
        import re
        pattern = r",\s*(Black|White|Beige|Red|Blue|Green|Pink|Purple|Brown|Gray|Grey|Clear|Transparent)$"
        return re.sub(pattern, "", self.name, flags=re.IGNORECASE).strip()


class Wishlist(db.Model):
    __tablename__ = "wishlist"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("wishlist_items", lazy="dynamic"))
    product = db.relationship("Product", backref=db.backref("wishlist_items", lazy="dynamic"))

    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="unique_user_product_wishlist"),)


class Color(db.Model):
    __tablename__ = "colors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    hex = db.Column(db.String(7), nullable=False)
    slug = db.Column(db.String(32), unique=True, nullable=False)


class Cart(db.Model):
    __tablename__ = "cart"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=True, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="cart_items")
    product = db.relationship("Product", backref="cart_items")
    variant = db.relationship("ProductVariant", backref="cart_items")

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", "variant_id", name="unique_user_product_variant_cart"),
        db.Index("idx_cart_user_product_variant", "user_id", "product_id", "variant_id"),
    )

    @property
    def total_price(self):
        return float(self.product.price) * self.quantity if self.product else 0.0


# ─────────────────────────────────────────────────────────────
# Orders & Delivery
# ─────────────────────────────────────────────────────────────

class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)

    email = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)

    shipping_address = db.Column(db.String(255), nullable=False)
    shipping_suite = db.Column(db.String(50), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=False)
    shipping_state = db.Column(db.String(50), nullable=False)
    shipping_zip = db.Column(db.String(20), nullable=False)
    shipping_country = db.Column(db.String(50), nullable=False, default="US")

    delivery_type = db.Column(db.String(20), nullable=False, default="pickup")
    delivery_latitude = db.Column(db.Float, nullable=True)
    delivery_longitude = db.Column(db.Float, nullable=True)

    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    shipping_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)

    payment_method = db.Column(db.String(50), nullable=False)
    payment_status = db.Column(db.String(50), nullable=False, default="pending")
    stripe_session_id = db.Column(db.String(255), nullable=True)

    status = db.Column(db.String(50), nullable=False, default="pending")
    pin_code = db.Column(db.String(10), nullable=True)  # PIN for manual delivery verification
    
    # NEW: Track if this order is a duplicate from same PI or was cancelled
    is_duplicate_payment = db.Column(db.Boolean, default=False)  # True if another order was already created from this PI
    payment_intent_status_at_creation = db.Column(db.String(50), nullable=True)  # Track PI status when order was created
    cancellation_reason = db.Column(db.String(255), nullable=True)  # Why order was marked incomplete/cancelled

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref="orders")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    delivery = db.relationship("UberDelivery", backref="order", uselist=False, cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    product_name = db.Column(db.String(255), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    product = db.relationship("Product", backref="order_items")


class UberDelivery(db.Model):
    __tablename__ = "uber_deliveries"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)

    quote_id = db.Column(db.String(100), nullable=True)
    delivery_id = db.Column(db.String(100), nullable=True)
    tracking_url = db.Column(db.String(500), nullable=True)

    status = db.Column(db.String(50), nullable=False, default="pending")
    fee = db.Column(db.Integer, nullable=True)  # cents
    currency = db.Column(db.String(3), nullable=False, default="usd")

    pickup_eta = db.Column(db.DateTime, nullable=True)
    dropoff_eta = db.Column(db.DateTime, nullable=True)
    pickup_deadline = db.Column(db.DateTime, nullable=True)
    dropoff_deadline = db.Column(db.DateTime, nullable=True)

    courier_name = db.Column(db.String(100), nullable=True)
    courier_phone = db.Column(db.String(20), nullable=True)
    courier_location_lat = db.Column(db.Float, nullable=True)
    courier_location_lng = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def fee_dollars(self):
        return self.fee / 100 if self.fee else 0

    @property
    def is_active(self):
        return self.status in ["pending", "active", "pickup", "dropoff"]


# ─────────────────────────────────────────────────────────────
# Discounts
# ─────────────────────────────────────────────────────────────

class DiscountCode(db.Model):
    __tablename__ = "discount_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    discount_type = db.Column(db.String(16), nullable=False, default="percentage")  # 'percentage' | 'fixed'
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    max_uses = db.Column(db.Integer, nullable=True)         # None = unlimited
    current_uses = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usages = db.relationship("DiscountUsage", backref="code", lazy="dynamic")

    @property
    def remaining_uses(self):
        return None if self.max_uses is None else max(0, (self.max_uses or 0) - (self.current_uses or 0))

    @property
    def is_valid(self):
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        if self.max_uses is not None and (self.current_uses or 0) >= (self.max_uses or 0):
            return False
        return True

    def __repr__(self):
        return f"<DiscountCode {self.code} type={self.discount_type} val={self.discount_value}>"


class DiscountUsage(db.Model):
    __tablename__ = "discount_usages"

    id = db.Column(db.Integer, primary_key=True)
    discount_code_id = db.Column(db.Integer, db.ForeignKey("discount_codes.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    session_identifier = db.Column(db.String(64), nullable=True, index=True)  # guest cookie/fingerprint
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True, index=True)
    original_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index("idx_discount_usage_person", "discount_code_id", "user_id", "session_identifier"),
    )

    def __repr__(self):
        return f"<DiscountUsage code_id={self.discount_code_id} order_id={self.order_id}>"


# ─────────────────────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────────────────────

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=True)
    resource_id = db.Column(db.String(50), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="success")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref="audit_logs")

    @staticmethod
    def log_action(action, user_id=None, resource_type=None, resource_id=None,
                   details=None, ip_address=None, user_agent=None, status="success"):
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
        )
        db.session.add(log_entry)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            from flask import current_app
            current_app.logger.error(f"Failed to create audit log: {e}")

    @property
    def is_active(self):
        return self.status in ["pending", "active", "pickup", "dropoff"]

    @property
    def is_completed(self):
        return self.status in ["delivered", "cancelled"]
