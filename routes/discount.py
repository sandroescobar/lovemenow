# routes/discount.py
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, jsonify, request, session, current_app
from flask_login import current_user
from sqlalchemy.orm import joinedload

from routes import db
from models import Product, Cart, DiscountCode, DiscountUsage, Order

# No url_prefix here; routes below include explicit /api/...
discount_bp = Blueprint("discount", __name__)


# -------------------------
# helpers
# -------------------------
def _round2(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _get_cart_items():
    """
    Return a list of dicts: {'product': Product, 'product_id': int, 'quantity': int}
    Supports logged-in carts (DB) and guest carts (session['cart'])
    """
    items = []
    if current_user.is_authenticated:
        rows = (
            Cart.query.options(joinedload(Cart.product))
            .filter(Cart.user_id == current_user.id)
            .all()
        )
        for r in rows:
            if r.product:
                items.append({"product": r.product, "product_id": r.product_id, "quantity": int(r.quantity or 0)})
    else:
        raw = session.get("cart", {}) or {}
        for cart_key, qty in raw.items():
            try:
                # keys can be "product_id:variant_id" or just "product_id"
                product_id = int(str(cart_key).split(":", 1)[0])
            except Exception:
                continue
            p = Product.query.get(product_id)
            if p:
                items.append({"product": p, "product_id": p.id, "quantity": int(qty or 0)})
    return items


def _cart_subtotal() -> float:
    items = _get_cart_items()
    return _round2(sum(float(it["product"].price) * it["quantity"] for it in items))


def _preview_discount(discount_type: str, discount_value: float, subtotal: float) -> float:
    if subtotal <= 0:
        return 0.0
    if discount_type == "percentage":
        return _round2(subtotal * (float(discount_value) / 100.0))
    # fixed amount
    return _round2(min(float(discount_value), subtotal))


def _code_is_valid(dc: DiscountCode) -> bool:
    # mirrors DiscountCode.is_valid() but defensive if the model method isn't present
    if not dc or not dc.is_active:
        return False
    now = datetime.utcnow()
    if dc.starts_at and now < dc.starts_at:
        return False
    if dc.ends_at and now > dc.ends_at:
        return False
    if dc.max_uses is not None and (dc.current_uses or 0) >= (dc.max_uses or 0):
        return False
    return True


# -------------------------
# Public validate (no side effects)
# POST /api/validate-discount
# -------------------------
@discount_bp.post("/api/validate-discount")
def validate_discount():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        return jsonify({"valid": False, "message": "This code is not applicable at this time."}), 400

    dc = DiscountCode.query.filter_by(code=code).first()
    if not dc or not _code_is_valid(dc):
        return jsonify({"valid": False, "message": "This code is not applicable at this time."}), 400

    # Note: we intentionally DO NOT check per-user prior usage here.
    # That enforcement happens at purchase time.
    payload = {
        "valid": True,
        "code": dc.code,
        "discount_type": dc.discount_type,
        "discount_value": float(dc.discount_value),
        "remaining_uses": (None if dc.max_uses is None else max(0, (dc.max_uses or 0) - (dc.current_uses or 0))),
        "starts_at": dc.starts_at.isoformat() if dc.starts_at else None,
        "ends_at": dc.ends_at.isoformat() if dc.ends_at else None,
    }
    return jsonify(payload)


# -------------------------
# Cart-scoped helpers and routes
#   GET  /api/cart/discount-status   (rich, preferred)
#   GET  /api/cart/status            (alias for old JS)
#   POST /api/cart/apply-discount    (preferred)
#   POST /api/cart/apply_discount    (alias)
#   POST /api/cart/remove-discount
# -------------------------

# ONE function, multiple routes for status
@discount_bp.get("/api/cart/discount-status")
@discount_bp.get("/api/cart/status")  # alias for older JS
def discount_status():
    disc = session.get("discount") or {}

    # cart item count (sum of quantities)
    if current_user.is_authenticated:
        cart_items = (
            db.session.query(db.func.coalesce(db.func.sum(Cart.quantity), 0))
            .filter(Cart.user_id == current_user.id)
            .scalar()
            or 0
        )
    else:
        cart_map = session.get("cart", {}) or {}
        cart_items = sum(int(q or 0) for q in cart_map.values())

    applied = bool(disc.get("code"))
    state = "applied" if (applied and cart_items > 0) else ("saved" if applied else "none")
    return jsonify({
        "applied": applied,
        "has_discount": applied,   # compatibility for older JS
        "state": state,
        "code": disc.get("code"),
        "cart_items": cart_items
    })


# ONE apply function, two paths (hyphen + underscore)
@discount_bp.post("/api/cart/apply-discount")
@discount_bp.post("/api/cart/apply_discount")
def apply_discount():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    replace = bool(data.get("replace"))

    if not code:
        return jsonify({"success": False, "message": "Please enter a code."}), 400

    attached = session.get("discount")
    if attached and attached.get("code") == code:
        # Already attached → just tell the UI; do NOT change usage counters.
        msg = f"Promo {code} is already attached. We’ll deduct it from your cart at checkout."
        return jsonify({"success": True, "already_attached": True, "message": msg, "code": code})

    if attached and attached.get("code") != code and not replace:
        return jsonify({"success": False, "message": "Another promo is already attached. Replace it?"}), 409

    # Validate code is currently usable (active + within window + remaining uses)
    dc = DiscountCode.query.filter_by(code=code).first()
    if not _code_is_valid(dc):
        return jsonify({"success": False, "message": "This code is not applicable at this time."}), 400

    # Attach to session only (no usage increment here)
    session["discount"] = {"code": code, "type": dc.discount_type, "value": float(dc.discount_value)}
    session.modified = True

    # Compute a preview off the current cart
    if current_user.is_authenticated:
        items = (
            db.session.query(Cart)
            .filter(Cart.user_id == current_user.id)
            .all()
        )
        # Avoid lazy-load N+1 by fetching product prices once
        product_ids = [it.product_id for it in items]
        products = {p.id: p for p in Product.query.filter(Product.id.in_(product_ids)).all()} if product_ids else {}
        subtotal = sum(float(products.get(it.product_id).price) * int(it.quantity or 0) for it in items if products.get(it.product_id))
    else:
        cart_map = session.get("cart", {}) or {}
        ids = [int(str(k).split(":")[0]) for k in cart_map.keys()] if cart_map else []
        products = {p.id: p for p in Product.query.filter(Product.id.in_(ids)).all()} if ids else {}
        subtotal = sum(
            float(products.get(int(str(k).split(":")[0])).price) * int(v)
            for k, v in cart_map.items()
            if str(k).split(":")[0].isdigit() and products.get(int(str(k).split(":")[0]))
        )

    discount_amount = _preview_discount(dc.discount_type, float(dc.discount_value), float(subtotal))
    total = _round2(max(0.0, float(subtotal) - discount_amount))

    # Store preview too (checkout will cap by current subtotal anyway)
    session["discount_code"] = code
    session["discount_amount"] = discount_amount
    session.modified = True

    return jsonify({
        "success": True,
        "code": code,
        "message": f"Promo {code} attached. We’ll auto-apply it to your cart.",
        "discount_amount": discount_amount,
        "total": total
    })


# ---- Cart totals for UI (uses the same logic as payment intent) ----
@discount_bp.get("/api/cart/totals")
def cart_totals():
    from routes.checkout_totals import compute_totals
    delivery_type = (request.args.get("delivery_type") or "pickup").strip().lower()

    # allow "?delivery_fee=5.99" or omit
    fee = request.args.get("delivery_fee")
    delivery_quote = {"fee_dollars": float(fee)} if fee else None

    totals = compute_totals(delivery_type=delivery_type, delivery_quote=delivery_quote)
    # Return only what the UI needs
    return jsonify({
        "subtotal": totals["subtotal"],
        "discount_amount": totals["discount_amount"],
        "discount_code": totals["discount_code"],
        "delivery_fee": totals["delivery_fee"],
        "tax": totals["tax"],
        "total": totals["total"]
    })



@discount_bp.post("/api/cart/remove-discount")
@discount_bp.post("/api/cart/remove_discount")  # alias
def remove_discount():
    if "discount" in session:
        session.pop("discount", None)
        session.pop("discount_code", None)
        session.pop("discount_amount", None)
        session.modified = True
        return jsonify({"success": True, "message": "Discount removed."})
    return jsonify({"success": False, "message": "No discount applied."}), 400
