from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db, bcrypt
from models import User

auth_bp = Blueprint("auth_bp", __name__)

@auth_bp.context_processor
def inject_lang():
    lang = request.args.get("lang", "en")
    return dict(lang=lang, session=session)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    lang = request.args.get("lang", "en") if request.method == "GET" else request.form.get("lang", "en")

    if request.method == "POST":
        name = request.form.get("name")
        password = request.form.get("password")

        user = User.query.filter_by(name=name).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_email'] = user.email

            return redirect(url_for("main_bp.profile", lang=lang))
        else:
            return render_template("login.html", error="Invalid name or password.", lang=lang)

    return render_template("login.html", error=None, lang=lang)

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main_bp.index", lang=request.args.get("lang", "en")))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    lang = request.args.get("lang", "en") if request.method == "GET" else request.form.get("lang", "en")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        if password != confirm:
            flash("Passwords do not match.")
            return render_template("main_bp.register.html", lang=lang)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email is already registered.")
            return render_template("main_bp.register.html", lang=lang)

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        session['user_name'] = new_user.name
        session['user_email'] = new_user.email

        return redirect(url_for("main_bp.profile", lang=lang))

    return render_template("register.html", lang=lang)