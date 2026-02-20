# routes/checkout_totals.py
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import session
from flask_login import current_user

from routes import db
from models import Product, Cart, DiscountCode

TAX_RATE = 0.07  # Florida 7%


def _round2(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _code_is_valid(dc: DiscountCode) -> bool:
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


def get_cart_items_for_request():
    """
    Return a list of {'product': Product, 'quantity': int}
    Works for logged-in carts (DB) and guest carts (session).
    """
    items = []
    if current_user.is_authenticated:
        rows = Cart.query.filter(Cart.user_id == current_user.id).all()
        for r in rows:
            if r.product:
                items.append({"product": r.product, "quantity": int(r.quantity or 0)})
        return items

    # guests
    raw = session.get("cart", {}) or {}
    if not raw:
        return items

    # Collect product ids and prefetch
    pids = set()
    for k in raw.keys():
        try:
            pid = int(str(k).split(":", 1)[0])
            pids.add(pid)
        except Exception:
            continue

    if not pids:
        return items

    products = {p.id: p for p in Product.query.filter(Product.id.in_(list(pids))).all()}
    for k, qty in raw.items():
        try:
            pid = int(str(k).split(":", 1)[0])
            p = products.get(pid)
            if p:
                items.append({"product": p, "quantity": int(qty or 0)})
        except Exception:
            continue
    return items


# routes/checkout_totals.py

def resolve_discount(subtotal: float):
    """
    Return (discount_amount, code) using the session-attached promo.
    We recompute from DB and cap by any preview saved in session,
    but only if that preview is a positive number (avoid wiping
    a valid discount with a stale zero).
    """
    attached = session.get("discount") or {}
    code = (attached.get("code") or "").strip().upper()
    preview = session.get("discount_amount")
    discount_amount = 0.0

    if code:
        dc = DiscountCode.query.filter_by(code=code).first()
        if _code_is_valid(dc):
            if dc.discount_type == "percentage":
                discount_amount = _round2(subtotal * (float(dc.discount_value) / 100.0))
            else:
                discount_amount = _round2(float(dc.discount_value))
        else:
            code = None

    # Cap by preview only if preview is a positive number
    try:
        preview_val = float(preview)
        if preview_val > 0:
            discount_amount = min(preview_val, discount_amount or subtotal)
    except (TypeError, ValueError):
        pass

    return min(subtotal, discount_amount), code



def compute_totals(delivery_type: str = "pickup", delivery_quote: dict | None = None):
    """
    Compute the full pricing breakdown from the current cart + session discount.
    Returns a dict with all numbers rounded to 2 decimals and amount_cents.
    Tax base: (discounted_subtotal + delivery_fee)
    """
    items = get_cart_items_for_request()
    if not items:
        return {
            "items": [],
            "subtotal": 0.0,
            "discount_amount": 0.0,
            "discount_code": None,
            "delivery_fee": 0.0,
            "tax": 0.0,
            "total": 0.0,
            "amount_cents": 0,
        }

    subtotal = _round2(sum(float(it["product"].price) * it["quantity"] for it in items))

    discount_amount, discount_code = resolve_discount(subtotal)

    delivery_fee = 0.0
    if delivery_type == "delivery":
        if delivery_quote and "fee_dollars" in delivery_quote:
            try:
                delivery_fee = _round2(float(delivery_quote["fee_dollars"]))
            except Exception:
                delivery_fee = 0.0

    discounted_subtotal = _round2(max(0.0, subtotal - discount_amount))
    tax_base = discounted_subtotal + delivery_fee
    tax = _round2(tax_base * TAX_RATE)
    total = _round2(discounted_subtotal + delivery_fee + tax)

    return {
        "items": items,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "discount_code": discount_code,
        "delivery_fee": delivery_fee,
        "tax": tax,
        "total": total,
        "amount_cents": int(round(total * 100)),
    }
