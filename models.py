from datetime import datetime
from flask_login import UserMixin
from routes  import db, bcrypt   # ← come from extensions.py

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id                = db.Column(db.Integer, primary_key=True)
    email             = db.Column(db.String(120), unique=True, nullable=False)
    password_hash     = db.Column(db.String(255), nullable=False)
    full_name         = db.Column(db.String(120), nullable=False)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    active            = db.Column(db.Boolean, default=True)
    stripe_customer_id = db.Column(db.String(40))   # optional

    # ── helper methods ─────────────────────────────────────────
    @property
    def password(self):
        raise AttributeError("password is write‑only")

    @password.setter
    def password(self, plain_pw: str):
        self.password_hash = bcrypt.generate_password_hash(plain_pw).decode()

    def check_password(self, plain_pw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, plain_pw)




