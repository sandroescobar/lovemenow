import os
from flask import Flask, render_template, redirect, request, url_for, flash
from dotenv import load_dotenv
from flask_login import login_user
from sqlalchemy import text
from routes import db, bcrypt, login_mgr
from models     import User          # ← import AFTER extensions declared

# ── env vars ─────────────────────────────────────────────────
load_dotenv()                        # reads .env in local dev

# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"]              = os.getenv("SECRET_KEY", "dev_key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── plug extensions into this single app ─────────────────────
db.init_app(app)
bcrypt.init_app(app)
login_mgr.init_app(app)
login_mgr.login_view    = "login_modal"
login_mgr.login_message = "Please log in first."

# ── loader callback required by Flask‑Login ──────────────────
@login_mgr.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))

# ── routes (very trimmed) ─────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/products")
def products():
    return render_template("products.html")

@app.route("/register_modal", methods = ['GET', 'POST'])
def register_modal():

    if request.method == 'POST' and 'full_name' in request.form and 'email' in request.form and 'password' in request.form and 'passwordCon' in request.form:
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        password_confirmation = request.form['passwordCon']

        if password != password_confirmation:
            flash("Passwords do not match")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered", "warning")
            return redirect(url_for("register_modal"))

        user = User(email=email, full_name=full_name)
        user.password = password  # triggers the bcrypt‑hash setter
        db.session.add(user)
        db.session.commit()

    return redirect(url_for("index"))


@app.route("/lgoin_modal")
def login_modal():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).frst()

        if user and user.check_password(password):
            login_user(user)
            flash("you've logged in successfully")
            return redirect(url_for("index"))

        flash("Incorrect email or password!", "danger")








    return render_template("login_modal.html")

# ── run & create tables once ─────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()                # <- now User is known, table created
        # quick sanity check
        db.session.execute(text("SELECT 1"))
        print("✅  DB connected and tables ensured.")

    app.run(debug=True)
