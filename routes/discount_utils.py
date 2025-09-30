from flask import request, session
from flask_login import current_user
from routes import db
from models import DiscountCode, DiscountUsage

def record_discount_redemption(order, order_subtotal, discount_amount):
    disc = session.get('discount')
    if not disc:
        return

    dc = DiscountCode.query.filter_by(code=disc.get('code')).with_for_update().first()
    if not dc:
        return

    # Identify user or guest
    user_id = current_user.id if current_user.is_authenticated else None
    guest_key = request.cookies.get('lmn_guest') or session.get('guest_key') or 'guest'

    usage = DiscountUsage(
        discount_code_id=dc.id,
        user_id=user_id,
        session_identifier=guest_key,
        order_id=order.id,
        original_amount=order_subtotal,
        discount_amount=discount_amount
    )
    db.session.add(usage)

    # bump global count
    dc.current_uses = (dc.current_uses or 0) + 1
    db.session.commit()

    # clear the cart discount for this session so it can't be reused
    session.pop('discount', None)
    session.modified = True
