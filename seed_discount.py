# seed_discount.py
from routes import db
from models import DiscountCode

# Try both app patterns
try:
    from app import app  # global app
except ImportError:
    from app import create_app  # factory
    app = create_app()

CODE = "LOVEMENOW20"

with app.app_context():
    code_upper = CODE.upper()

    dc = DiscountCode.query.filter_by(code=code_upper).first()
    if not dc:
        dc = DiscountCode(
            code=code_upper,
            discount_type="percentage",  # 'percentage' or 'fixed'
            discount_value=20,           # 20% off
            max_uses=100,                # first 100 customers
            current_uses=0,
            active=True
        )
        db.session.add(dc)
        action = "created"
    else:
        dc.discount_type = "percentage"
        dc.discount_value = 20
        dc.max_uses = 100
        # keep current_uses as-is to not reset the counter
        dc.active = True
        action = "updated"

    db.session.commit()

    remaining = dc.remaining_uses if dc.remaining_uses is not None else "∞"
    print(f"{code_upper} {action}.")
    print(f"Type: {dc.discount_type}, Value: {dc.discount_value}")
    print(f"Max uses: {dc.max_uses}, Current uses: {dc.current_uses}, Remaining: {remaining}")
