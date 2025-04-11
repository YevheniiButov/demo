# routes/tests_routes.py

import json
from flask import Blueprint, render_template, request, session, redirect, url_for, current_app

# ✅ Чистый Blueprint
card_tests_bp = Blueprint("tests", __name__, url_prefix="/tests")

print("✅ Загружен файл: routes/tests_routes.py")  # 👈 добавлен отладочный вывод

# ✅ Загружаем JSON с вопросами
with open("radio_questions.json", encoding="utf-8") as f:
    radio_questions = json.load(f)

# 🔍 Выводим список всех маршрутов при загрузке
@card_tests_bp.record_once
def log_routes(state):
    print("📜 Зарегистрированные маршруты:")
    for rule in state.app.url_map.iter_rules():
        print("🔗", rule)

# ✅ Карточки по вопросам
@card_tests_bp.route("/card-test/<int:index>", methods=["GET", "POST"])
def card_test_handler(index):
    print(f"📂 Вопросов загружено: {len(radio_questions)}")
    print(f"📌 Вызван вопрос #{index}")

    if index < 0 or index >= len(radio_questions):
        print(f"❌ Индекс {index} вне диапазона")
        return "Einde van de test!", 404

    question = radio_questions[index]
    print(f"❓ Вопрос: {question.get('question')}")
    result = None

    if request.method == "POST":
        selected = request.form.get("selected")
        print(f"📤 Ответ: {selected}")
        if selected == question.get("answer"):
            result = "correct"
            print("✔️ Правильно")
        else:
            result = "incorrect"
            print(f"❌ Неправильно. Правильный: {question.get('answer')}")

    return render_template("test_card.html", question=question, index=index, result=result)

# ✅ Страница со списком тем
@card_tests_bp.route("/")
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

# ✅ Заглушка для запуска теста
@card_tests_bp.route("/test/<subject>/<int:test_id>")
def start_test(subject, test_id):
    return render_template("test.html", subject=subject, test_id=test_id)

# ✅ Полный тест с подсчётом баллов и прогрессом
@card_tests_bp.route("/full-test", methods=["GET", "POST"])
def full_test():
    print("📍 Вызван маршрут /full-test")

    if request.args.get("reset") == "true":
        session.clear()
        return redirect(url_for("tests.full_test"))

    try:
        total = len(radio_questions)

        if "step" not in session:
            print("🧪 Сессия не найдена. Создаю step и score")
            session["step"] = 0
            session["score"] = 0

        step = session["step"]

        if step >= total:
            final_score = session["score"]
            session.clear()
            print(f"🏁 Тест завершён. Баллы: {final_score}/{total}")
            return render_template("test_result.html", score=final_score, total=total)

        question = radio_questions[step]
        print(f"➡️ Вопрос {step + 1}: {question.get('question')}")

        if request.method == "POST":
            selected = request.form.get("selected")
            print(f"📤 Ответ: {selected} — Правильный: {question.get('answer')}")

            if selected == question.get("answer"):
                session["score"] += 1
                result = "correct"
            else:
                result = "incorrect"

    # НЕ прибавляем step сразу, а даём возможность увидеть ответ
            return render_template(
                "test_full.html",
                question=question,
                step=step,
                total=total,
                result=result,
                answer=question.get("answer")
            )


        return render_template(
            "test_full.html",
            question=question,
            step=step,
            total=total,
            result=None,
            answer=question.get("answer")
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Ошибка: {e}", 500

@card_tests_bp.route("/full-test/next", methods=["POST"])
def full_test_next():
    session["step"] += 1
    return redirect(url_for("tests.full_test"))
