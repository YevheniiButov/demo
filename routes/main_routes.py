from flask import Blueprint, render_template, session, redirect, url_for, request
from models import User, Module

main_bp = Blueprint("main_bp", __name__)

@main_bp.route("/")
def index():
    return render_template("index.html")

@main_bp.route("/big-info")
def big_info():
    return render_template("big-info.html")

@main_bp.route("/profile")
def profile():
    if session.get("user_id"):
        user = User.query.get(session["user_id"])
        if user.is_admin:
            return redirect(url_for("admin_bp.dashboard", lang=request.args.get("lang", "en")))
        return render_template("profile.html", user=user, lang=request.args.get("lang", "en"))
    return redirect(url_for("auth_bp.login", lang=request.args.get("lang", "en")))


@main_bp.route("/learn")
def learn():
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login"))

    user = User.query.get(session["user_id"])
    all_modules = Module.query.all()

    # Категории
    categories = {
        "education": [],
        "bi_toets": [],
        "dutch": []
    }

    for module in all_modules:
        if module.title.lower().startswith("dutch"):
            categories["dutch"].append(module)
        elif "bi" in module.title.lower():
            categories["bi_toets"].append(module)
        else:
            categories["education"].append(module)

    return render_template("learn.html", categories=categories, user=user)
