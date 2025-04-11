import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from routes.lesson_routes import lesson_bp  # ✅ подключение уроков как Blueprint

app = Flask(__name__)
app.secret_key = 'e875ccd43f1993e3c15b91cf6d0dbf649e8a6f5b42cc1b295939eeea0f3f2e91'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

app.register_blueprint(lesson_bp) 

class Module(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_premium = db.Column(db.Boolean, default=True)
    lessons = db.relationship("Lesson", backref="module", lazy=True)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("module.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    quiz = db.Column(db.JSON, nullable=True)

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    has_subscription = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    progress = db.relationship("UserProgress", backref="user", lazy=True)

@app.context_processor
def inject_globals():
    lang = request.args.get("lang", "en")
    return dict(lang=lang, session=session)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
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

            return redirect(url_for("profile", lang=lang))
        else:
            return render_template("login.html", error="Invalid name or password.", lang=lang)

    return render_template("login.html", error=None, lang=lang)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index", lang=request.args.get("lang", "en")))

@app.route("/big-info")
def big_info():
    return render_template("big-info.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    lang = request.args.get("lang", "en") if request.method == "GET" else request.form.get("lang", "en")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        if password != confirm:
            flash("Passwords do not match.")
            return render_template("register.html", lang=lang)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email is already registered.")
            return render_template("register.html", lang=lang)

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        session['user_name'] = new_user.name
        session['user_email'] = new_user.email

        return redirect(url_for("profile", lang=lang))

    return render_template("register.html", lang=lang)

@app.route("/profile", methods=["GET"])
def profile():
    if 'user_id' not in session:
        return redirect(url_for("login", lang=request.args.get("lang", "en")))

    name = session.get("user_name", "User")
    email = session.get("user_email", "user@example.com")
    return render_template(
        "profile.html",
        name=name,
        email=email,
        has_subscription=True,
        progress=[
            {"title": "Anatomy", "completed_lessons": 3, "total_lessons": 5},
            {"title": "Physiology", "completed_lessons": 2, "total_lessons": 4},
            {"title": "Law & Ethics", "completed_lessons": 1, "total_lessons": 3},
        ],
        lang=request.args.get("lang", "en")
    )

@app.route("/learn")
def learn():
    if not session.get("user_id"):
        return redirect(url_for("login"))

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


@app.route("/module/<int:module_id>/lesson/<int:lesson_index>", methods=["GET", "POST"])
def lesson_view(module_id, lesson_index):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    module = Module.query.get_or_404(module_id)
    lessons = Lesson.query.filter_by(module_id=module.id).order_by(Lesson.id).all()

    if lesson_index >= len(lessons):
        flash("Lesson does not exist.")
        return redirect(url_for("learn"))

    lesson = lessons[lesson_index]

    result = None
    if request.method == "POST" and lesson.quiz:
        print("Quiz submission detected")
        score = 0
        total = len(lesson.quiz)
        for i, q in enumerate(lesson.quiz):
            selected = request.form.get(f"q{i}")
            if selected == q["answer"]:
                score += 1
        result = {
        "score": score,
        "total": total,
        "percent": int((score / total) * 100)
    }

    if result and result.get("percent") and result["percent"] >= 70:
        existing = UserProgress.query.filter_by(user_id=user.id, lesson_id=lesson.id).first()
        if not existing:
            new_progress = UserProgress(user_id=user.id, lesson_id=lesson.id, completed=True)
            db.session.add(new_progress)
            db.session.commit()

    if not lesson.quiz:
        return render_template("lesson.html", lesson=lesson, module=module, index=lesson_index, total=len(lessons), result=None, show_continue=True)
    
    return render_template("lesson.html", lesson=lesson, module=module, index=lesson_index, total=len(lessons), result=result)


@app.route("/admin/import-modules", methods=["GET", "POST"])
def import_modules():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user or not user.is_admin:
        return "Access denied", 403

    if request.method == "POST":
        file = request.files.get("json")
        if not file:
            flash("No file uploaded.")
            return redirect(request.url)

        import json
        data = json.load(file)

        for mod in data:
            module = Module(title=mod["title"], description=mod["description"], is_premium=mod.get("is_premium", True))
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
        return redirect(url_for("import_modules"))

    modules = Module.query.all()
    return render_template("import_modules.html", modules=modules)


@app.route("/admin/delete-module/<int:module_id>", methods=["POST"])
def delete_module(module_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user or not user.is_admin:
        return "Access denied", 403

    module = Module.query.get_or_404(module_id)
    Lesson.query.filter_by(module_id=module.id).delete()
    db.session.delete(module)
    db.session.commit()
    flash("Module deleted successfully.")
    return redirect(url_for("import_modules"))


@app.route("/upload", methods=["POST"])
def upload():
    cv = request.files.get("cv")
    doc = request.files.get("doc")

    if cv:
        filename = secure_filename(cv.filename)
        cv.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    if doc:
        filename = secure_filename(doc.filename)
        doc.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    return redirect(url_for("profile", lang=request.args.get("lang", "en")))

@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user or not hasattr(user, "is_admin") or not user.is_admin:
        return "Access denied", 403

    if request.method == "POST":
        user_id = request.form.get("user_id")
        updated_user = User.query.get(user_id)
        if updated_user:
            if request.form.get("action") == "delete":
                db.session.delete(updated_user)
                db.session.commit()
                flash("User deleted successfully.")
                return redirect(url_for("admin_users"))
            updated_user.name = request.form.get("name")
            updated_user.email = request.form.get("email")
            updated_user.has_subscription = "has_subscription" in request.form
            db.session.commit()
            flash("User updated successfully.")
        return redirect(url_for("admin_users"))

    users = User.query.all()
    return render_template("admin_users.html", users=users, current_user=user)

@app.route("/tests")
def subject_tests():
    subjects = [
        {
            "name": "Anatomy",
            "tests": [
                {"id": 1, "title": "Teeth Basics"},
                {"id": 2, "title": "Skull Anatomy"}
            ]
        },
        {
            "name": "Ethics & Law",
            "tests": [
                {"id": 3, "title": "Confidentiality"}
            ]
        }
    ]
    return render_template("tests.html", subjects=subjects)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 5000))

    with app.app_context():
        db.create_all()
      

    app.run(host="0.0.0.0", port=port, debug=True)
