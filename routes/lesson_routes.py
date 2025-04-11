from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from models import db, Module, User, Lesson, UserProgress

lesson_bp = Blueprint("lesson_bp", __name__)

@lesson_bp.route("/lesson/<int:module_id>/<int:lesson_index>", methods=["GET", "POST"])
def lesson_view(module_id, lesson_index):
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login"))

    user = User.query.get(session["user_id"])
    module = Module.query.get_or_404(module_id)
    lessons = Lesson.query.filter_by(module_id=module.id).order_by(Lesson.id).all()

    if lesson_index >= len(lessons):
        flash("Lesson not found.")
        return redirect(url_for("learn"))

    lesson = lessons[lesson_index]
    result = None

    if request.method == "POST" and lesson.quiz:
        correct = 0
        for i, q in enumerate(lesson.quiz):
            if request.form.get(f"q{i}") == q["answer"]:
                correct += 1
        percent = round(correct / len(lesson.quiz) * 100)
        result = {"percent": percent, "passed": percent >= 70}

        if result["passed"]:
            existing = UserProgress.query.filter_by(user_id=user.id, lesson_id=lesson.id).first()
            if not existing:
                progress = UserProgress(user_id=user.id, lesson_id=lesson.id, completed=True)
                db.session.add(progress)
                db.session.commit()

    return render_template("lesson.html", module=module, lesson=lesson, index=lesson_index, total=len(lessons), result=result)
