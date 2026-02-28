# routes/discount.py
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, jsonify, request, session
from flask_login import current_user
from sqlalchemy.orm import joinedload

from routes import db
from models import Product, Cart, DiscountCode  # ← use DiscountCode

discount_bp = Blueprint("discount", __name__)  # ← this blueprint is used everywhere in this file


# -------------------------
# helpers
# -------------------------
def _round2(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _get_cart_items():
    """
    Return list: {'product': Product, 'product_id': int, 'quantity': int}
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
                items.append({
                    "product": r.product,
                    "product_id": r.product_id,
                    "quantity": int(r.quantity or 0)
                })
    else:
        raw = session.get("cart", {}) or {}
        for cart_key, qty in raw.items():
            try:
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


def _preview_discount(dc: DiscountCode, subtotal: float) -> float:
    """Compute discount amount for the given DiscountCode against subtotal."""
    if not dc or subtotal <= 0:
        return 0.0
    if dc.discount_type == "percentage":
        return _round2(subtotal * (float(dc.discount_value) / 100.0))
    # fixed amount
    return _round2(min(float(dc.discount_value), subtotal))


def _code_is_valid(dc: DiscountCode) -> bool:
    if not dc or not getattr(dc, "is_active", False):
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
        return jsonify({"success": False, "valid": False, "message": "This code is not applicable at this time."}), 400

    dc = DiscountCode.query.filter(DiscountCode.code.ilike(code)).first()
    if not dc or not _code_is_valid(dc):
        return jsonify({"success": False, "valid": False, "message": "This code is not applicable at this time."}), 400

    return jsonify({
        "success": True,
        "valid": True,
        "code": dc.code,
        "discount_type": dc.discount_type,
        "discount_value": float(dc.discount_value),
        "remaining_uses": (None if dc.max_uses is None else max(0, (dc.max_uses or 0) - (dc.current_uses or 0))),
        "starts_at": dc.starts_at.isoformat() if dc.starts_at else None,
        "ends_at": dc.ends_at.isoformat() if dc.ends_at else None,
    })


# -------------------------
# Cart discount endpoints
#   GET  /api/cart/discount-status  (preferred; includes computed amount)
#   GET  /api/cart/status           (alias)
#   POST /api/cart/apply-discount   (preferred)
#   POST /api/apply-discount        (alias)
#   POST /api/cart/remove-discount  (preferred)
#   POST /api/remove-discount       (alias)
# -------------------------

@discount_bp.get("/api/cart/discount-status")
@discount_bp.get("/api/cart/status")  # alias for older JS
def discount_status():
    subtotal = _cart_subtotal()

    # read code from either structure
    sess_disc = session.get("discount") or {}
    code = (sess_disc.get("code") or session.get("discount_code") or "").strip().upper()

    if not code:
        return jsonify({"success": True, "has_discount": False, "applied": False, "state": "none", "cart_items": sum(i["quantity"] for i in _get_cart_items())})

    dc = DiscountCode.query.filter(DiscountCode.code.ilike(code)).first()
    if not _code_is_valid(dc):
        # drop stale code
        session.pop("discount", None)
        session.pop("discount_code", None)
        return jsonify({"success": True, "has_discount": False, "applied": False, "state": "none", "cart_items": sum(i["quantity"] for i in _get_cart_items())})

    amount = _preview_discount(dc, subtotal)
    state = "applied" if sum(i["quantity"] for i in _get_cart_items()) > 0 else "saved"

    return jsonify({
        "success": True,
        "has_discount": amount > 0,
        "applied": amount > 0,
        "state": state,
        "discount": {
            "code": dc.code,
            "discount_amount": amount
        },
        "cart_items": sum(i["quantity"] for i in _get_cart_items())
    })


@discount_bp.post("/api/cart/apply-discount")
@discount_bp.post("/api/apply-discount")  # alias for older JS
def apply_discount_to_cart():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        return jsonify(success=False, message="Missing discount code"), 400

    dc = DiscountCode.query.filter(DiscountCode.code.ilike(code)).first()
    if not _code_is_valid(dc):
        return jsonify(success=False, message="Invalid or inactive code"), 400

    # ━━━ Anti-stacking: Prevent LOVEMENOWMIAMI + $10 combo ━━━
    # If applying LOVEMENOWMIAMI, reject if $10 code is active; vice versa
    conflicting_codes = {
        'LOVEMENOWMIAMI': 'LOVEMENOW10',
        'LOVEMENOW10': 'LOVEMENOWMIAMI'
    }
    
    if code in conflicting_codes:
        conflicting = conflicting_codes[code]
        sess_disc = session.get("discount") or {}
        current_code = (sess_disc.get("code") or session.get("discount_code") or "").strip().upper()
        
        if current_code == conflicting:
            return jsonify(
                success=False, 
                message=f"You cannot combine {code} with {conflicting}. Please remove the current discount to apply {code}."
            ), 400
    
    # Persist ONLY the code (but keep a tiny dict for legacy code that expects session['discount'])
    session["discount_code"] = code
    session["discount"] = {"code": code}
    session.pop("discount_amount", None)
    session.modified = True

    return jsonify(success=True, message="Discount applied", code=code), 200


@discount_bp.post("/api/cart/remove-discount")
@discount_bp.post("/api/remove-discount")  # alias for older JS
def remove_discount():
    removed = False
    for k in ("discount", "discount_code", "discount_amount"):
        if k in session:
            session.pop(k, None)
            removed = True
    session.modified = True
    return jsonify({"success": True, "message": "Discount removed" if removed else "No discount to remove"}), 200


# (Optional) Totals passthrough — only keep this if you don't already register the same path elsewhere.
@discount_bp.get("/api/cart/totals")
def cart_totals():
    # Avoid circular import at module import time
    from routes.checkout_totals import compute_totals
    delivery_type = (request.args.get("delivery_type") or "pickup").strip().lower()
    fee = request.args.get("delivery_fee")
    delivery_quote = {"fee_dollars": float(fee)} if fee else None

    totals = compute_totals(delivery_type=delivery_type, delivery_quote=delivery_quote)
    return jsonify({
        "subtotal": totals["subtotal"],
        "discount_amount": totals["discount_amount"],
        "discount_code": totals["discount_code"],
        "discount_source": totals.get("discount_source"),
        "tier_pct": totals.get("tier_pct", 0),
        "tier_label": totals.get("tier_label"),
        "next_tier": totals.get("next_tier"),
        "delivery_fee": totals["delivery_fee"],
        "tax": totals["tax"],
        "total": totals["total"]
    })
