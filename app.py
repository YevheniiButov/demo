import os
from flask import Flask, request, session
from extensions import db, bcrypt
from werkzeug.utils import secure_filename

from routes.main_routes import main_bp
from routes.auth_routes import auth_bp
from routes.lesson_routes import lesson_bp
from routes.admin_routes import admin_bp
from routes.tests_routes import card_tests_bp
from routes.learnmod_routes import learnmod_bp
from routes.pdf_routes import pdf_bp

app = Flask(__name__)
@app.before_request
def debug_requests():
    print("🔍 Запрос на маршрут:", request.path)

app.secret_key = "kapacb83"

app.config["SESSION_COOKIE_SECURE"] = False
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt.init_app(app)

@app.context_processor
def inject_globals():
    lang = request.args.get("lang", "en")
    return dict(lang=lang, session=session)

# Регистрируем блюпринты
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(lesson_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(card_tests_bp)
app.register_blueprint(learnmod_bp)
app.register_blueprint(pdf_bp)

for rule in app.url_map.iter_rules():
    print("🔗", rule)


if __name__ == "__main__":
    app.run(debug=True)
