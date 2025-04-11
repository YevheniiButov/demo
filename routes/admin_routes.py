from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, User, Module, Lesson
from werkzeug.utils import secure_filename
import os
import json

admin_bp = Blueprint("admin_bp", __name__)

# --- USERS MANAGEMENT ---
@admin_bp.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login", lang=request.args.get("lang", "en")))

    user = User.query.get(session["user_id"])
    if not user.is_admin:
        return redirect(url_for("main_bp.profile", lang=request.args.get("lang", "en")))

    if request.method == "POST":
        form_user_id = request.form.get("user_id")
        action = request.form.get("action")
        target = User.query.get(form_user_id)

        if action == "save":
            target.name = request.form.get("name")
            target.email = request.form.get("email")
            target.has_subscription = bool(request.form.get("has_subscription"))
            target.is_admin = bool(request.form.get("is_admin"))
            db.session.commit()
            flash(f"✅ User {target.name} updated.")
        return redirect(url_for("admin_bp.admin_users", lang=request.args.get("lang", "en")))

    users = User.query.order_by(User.id).all()
    return render_template("admin/users.html", users=users, current_user=user, lang=request.args.get("lang", "en"))

#___DELETE USER------------------

@admin_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login", lang=request.args.get("lang", "en")))

    admin = User.query.get(session["user_id"])
    if not admin or not admin.is_admin:
        return redirect(url_for("main_bp.profile", lang=request.args.get("lang", "en")))

    user_to_delete = User.query.get(user_id)
    if user_to_delete:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash("🗑 User deleted.")

    return redirect(url_for("admin_bp.admin_users", lang=request.args.get("lang", "en")))


# --- IMPORT MODULES ---
@admin_bp.route("/admin/import-modules", methods=["GET", "POST"])
def import_modules():
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login"))

    user = User.query.get(session["user_id"])
    if not user or not user.is_admin:
        return "Access denied", 403

    if request.method == "POST":
        file = request.files.get("json")
        if not file:
            flash("No file uploaded.")
            return redirect(request.url)

        try:
            data = json.load(file)
            for mod in data:
                module = Module(
                    title=mod["title"],
                    description=mod["description"],
                    is_premium=mod.get("is_premium", True)
                )
                db.session.add(module)
                db.session.flush()

                for lesson in mod.get("lessons", []):
                    new_lesson = Lesson(
                        module_id=module.id,
                        title=lesson["title"],
                        content=lesson["content"],
                        quiz=lesson.get("quiz", [])
                    )
                    db.session.add(new_lesson)

            db.session.commit()
            flash("Modules imported successfully.")
        except Exception as e:
            flash(f"Failed to import modules: {e}")
        return redirect(url_for("admin_bp.import_modules"))

    modules = Module.query.all()
    return render_template("import_modules.html", modules=modules)


# --- DELETE MODULE ---
@admin_bp.route("/admin/delete-module/<int:module_id>", methods=["POST"])
def delete_module(module_id):
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login"))

    user = User.query.get(session["user_id"])
    if not user or not user.is_admin:
        return "Access denied", 403

    module = Module.query.get_or_404(module_id)
    Lesson.query.filter_by(module_id=module.id).delete()
    db.session.delete(module)
    db.session.commit()
    flash("Module deleted successfully.")
    return redirect(url_for("admin_bp.import_modules"))


# --- CREATE MODULE ---
@admin_bp.route("/admin/create-module", methods=["GET", "POST"])
def create_module():
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login"))

    user = User.query.get(session["user_id"])
    if not user or not user.is_admin:
        return "Access denied", 403

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        is_premium = request.form.get("is_premium") == "on"
        lesson_title = request.form.get("lesson_title")
        lesson_content = request.form.get("lesson_content")
        quiz_json = request.form.get("quiz_json")

        try:
            module = Module(title=title, description=description, is_premium=is_premium)
            db.session.add(module)
            db.session.flush()

            quiz = json.loads(quiz_json) if quiz_json else []
            new_lesson = Lesson(module_id=module.id, title=lesson_title, content=lesson_content, quiz=quiz)
            db.session.add(new_lesson)
            db.session.commit()

            flash("Module with first lesson created successfully.")
        except Exception as e:
            flash(f"Error creating module: {e}")
        return redirect(url_for("admin_bp.import_modules"))

    return render_template("admin/create_module.html")

@admin_bp.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login", lang=request.args.get("lang", "en")))

    user = User.query.get(session["user_id"])
    if not user.is_admin:
        return redirect(url_for("main_bp.profile", lang=request.args.get("lang", "en")))

    return render_template("admin/dashboard.html", user=user, lang=request.args.get("lang", "en"))
