from flask import Blueprint, render_template, session, redirect, url_for, request
import json
import os

learnmod_bp = Blueprint("learnmod_bp", __name__)

def get_module_path(module_id):
    return f"learn/{module_id}.1.json"

@learnmod_bp.route("/module/<int:module_id>/block/<int:block_index>", methods=["GET"])
def learning_block(module_id, block_index):
    if not session.get("user_id"):
        return redirect(url_for("auth_bp.login"))

    json_path = get_module_path(module_id)
    if not json_path or not os.path.exists(json_path):
        return "Модуль не найден", 404

    with open(json_path, encoding="utf-8") as f:
        module = json.load(f)

    blocks = module.get("learning_blocks", [])
    if block_index >= len(blocks):
        return redirect(url_for("learn"))

    current_block = blocks[block_index]

    return render_template(
        "learning_module.html",
        module=module,
        module_id=module_id,
        block_index=block_index,
        current_block=current_block
    )
