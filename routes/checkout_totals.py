# routes/checkout_totals.py
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import session
from flask_login import current_user

from routes import db
from models import Product, Cart, DiscountCode

TAX_RATE = 0.07  # Florida 7%

# ── Tiered auto-discounts (no code needed) ──────────────────
# Each tier: (min_subtotal, discount_percent, label)
# Highest qualifying tier wins. Tiers are checked top-down.
SPEND_TIERS = [
    (150.0, 8, "8% OFF + FREE Delivery on orders $150+"),
    (100.0, 0, "FREE Delivery on orders $100+"),
    (75.0,  8, "8% OFF orders $75+"),
    (50.0,  5, "5% OFF orders $50+"),
]

# Free delivery thresholds (subtotal must meet this to qualify)
FREE_DELIVERY_THRESHOLD = 100.0


def resolve_tier(subtotal: float):
    """Return (discount_pct, tier_label, next_tier_info) for the given subtotal."""
    matched = None
    for min_amt, pct, label in SPEND_TIERS:
        if subtotal >= min_amt:
            matched = (pct, label)
            break

    if matched:
        pct, label = matched
        # Find next tier above current
        next_tier = None
        for min_amt, npct, nlabel in reversed(SPEND_TIERS):
            if min_amt > subtotal:
                next_tier = {"spend_more": _round2(min_amt - subtotal), "next_pct": npct, "next_label": nlabel}
                break
        return pct, label, next_tier

    # No tier matched — show nudge toward first tier
    lowest = SPEND_TIERS[-1]  # $50 tier
    nudge = {"spend_more": _round2(lowest[0] - subtotal), "next_pct": lowest[1], "next_label": lowest[2]}
    return 0, None, nudge


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
    
    Delivery behavior:
    - If delivery_type is 'delivery' AND quote is provided: use quote fee
    - If delivery_type is 'delivery' BUT no quote yet: show $0 (user hasn't entered address)
    - If delivery_type is 'pickup': delivery_fee = $0
    """
    import logging
    logger = logging.getLogger(__name__)
    
    items = get_cart_items_for_request()
    if not items:
        return {
            "items": [],
            "subtotal": 0.0,
            "discount_amount": 0.0,
            "discount_code": None,
            "discount_source": None,
            "tier_pct": 0,
            "tier_label": None,
            "next_tier": {"spend_more": 50.0, "next_pct": 5, "next_label": "5% OFF orders $50+"},
            "delivery_fee": 0.0,
            "tax": 0.0,
            "total": 0.0,
            "amount_cents": 0,
        }

    subtotal = _round2(sum(float(it["product"].price) * it["quantity"] for it in items))

    # 1) Check tiered auto-discount
    tier_pct, tier_label, next_tier = resolve_tier(subtotal)
    tier_discount = _round2(subtotal * (tier_pct / 100.0)) if tier_pct else 0.0

    # 2) Check promo code discount
    code_discount, discount_code = resolve_discount(subtotal)

    # Use whichever is greater (no stacking)
    if code_discount >= tier_discount:
        discount_amount = code_discount
        discount_source = "code"
    else:
        discount_amount = tier_discount
        discount_code = None  # tier wins, don't attribute to code
        discount_source = "tier"

    # Free delivery check: $100+ subtotal qualifies
    free_delivery = subtotal >= FREE_DELIVERY_THRESHOLD

    delivery_fee = 0.0
    if delivery_type == "delivery":
        if free_delivery:
            delivery_fee = 0.0
            logger.info(f"🚚 FREE delivery — subtotal ${subtotal:.2f} >= ${FREE_DELIVERY_THRESHOLD}")
        elif delivery_quote and "fee_dollars" in delivery_quote:
            try:
                delivery_fee = _round2(float(delivery_quote["fee_dollars"]))
                logger.info(f"✅ Delivery fee from quote: ${delivery_fee:.2f}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to parse delivery_quote fee: {str(e)}")
                delivery_fee = 0.0
        else:
            logger.info(f"📍 Delivery selected but no quote yet - showing $0 until address is entered")
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
        "discount_source": discount_source,
        "tier_pct": tier_pct,
        "tier_label": tier_label,
        "next_tier": next_tier,
        "free_delivery": free_delivery,
        "delivery_fee": delivery_fee,
        "tax": tax,
        "total": total,
        "amount_cents": int(round(total * 100)),
    }
