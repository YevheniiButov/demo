# routes/pdf_routes.py

import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from pdf_utils.extractor import extract_pdf_structure, analyze_structure_with_ai, generate_chapter_summary, generate_chapter_cards

pdf_bp = Blueprint("pdf_bp", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
EXTRACTED_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'extracted')
STRUCTURE_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'structure')
CARDS_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'cards')
SUMMARY_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'summaries')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACTED_FOLDER, exist_ok=True)
os.makedirs(STRUCTURE_FOLDER, exist_ok=True)
os.makedirs(CARDS_FOLDER, exist_ok=True)
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

@pdf_bp.route("/admin/pdf", methods=["GET", "POST"])
def pdf_upload():
    if request.method == "POST":
        pdf_file = request.files.get("pdf")
        if not pdf_file:
            flash("❌ No file uploaded")
            return redirect(request.url)

        filename = secure_filename(pdf_file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        pdf_file.save(filepath)

        flash(f"✅ File '{filename}' uploaded successfully.")

        mode = request.form.get("mode")
        show_pdf = request.form.get("show_pdf") == "on"
        show_blocks = request.form.get("show_blocks") == "on"
        show_images = request.form.get("show_images") == "on"

        try:
            blocks = extract_pdf_structure(filepath)
            json_path = os.path.join(EXTRACTED_FOLDER, filename.replace(".pdf", ".json"))
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(blocks, f, ensure_ascii=False, indent=2)
            flash(f"✅ Extracted {len(blocks)} blocks and saved to {json_path}")

            structure = analyze_structure_with_ai(blocks)
            structure_path = os.path.join(STRUCTURE_FOLDER, filename.replace(".pdf", "_structure.json"))
            with open(structure_path, "w", encoding="utf-8") as f:
                json.dump(structure, f, ensure_ascii=False, indent=2)
            flash(f"✅ Analyzed structure and saved to {structure_path}")

            return redirect(url_for("pdf_bp.pdf_structure", filename=filename.replace(".pdf", "_structure.json")))

        except ImportError as ie:
            flash(f"❌ OpenAI module not found: {str(ie)}")
        except json.JSONDecodeError as je:
            flash(f"❌ JSON decode error during structure analysis: {str(je)}")
        except Exception as e:
            flash(f"❌ Error during PDF processing: {str(e)}")

        return redirect(request.url)

    files = os.listdir(EXTRACTED_FOLDER)
    extracted_files = [f for f in files if f.endswith('.json') and not f.endswith('_structure.json')]
    return render_template("admin/pdf_upload.html", extracted_files=extracted_files)

@pdf_bp.route("/admin/pdf/view/<filename>")
def view_pdf_blocks(filename):
    json_path = os.path.join(EXTRACTED_FOLDER, filename)
    if not os.path.exists(json_path):
        flash("❌ JSON file not found.")
        return redirect(url_for("pdf_bp.pdf_upload"))

    with open(json_path, encoding="utf-8") as f:
        blocks = json.load(f)

    return render_template("admin/pdf_view.html", filename=filename, blocks=blocks)

@pdf_bp.route("/admin/pdf/edit/<filename>/<int:block_index>", methods=["GET", "POST"])
def edit_pdf_block(filename, block_index):
    json_path = os.path.join(EXTRACTED_FOLDER, filename)
    if not os.path.exists(json_path):
        flash("❌ JSON file not found.")
        return redirect(url_for("pdf_bp.pdf_upload"))

    with open(json_path, encoding="utf-8") as f:
        blocks = json.load(f)

    if block_index < 0 or block_index >= len(blocks):
        flash("❌ Invalid block index.")
        return redirect(url_for("pdf_bp.view_pdf_blocks", filename=filename))

    if request.method == "POST":
        blocks[block_index]["chapter"] = request.form.get("chapter")
        blocks[block_index]["tags"] = request.form.get("tags", "").split(",")
        blocks[block_index]["text"] = request.form.get("text", blocks[block_index].get("text"))

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(blocks, f, ensure_ascii=False, indent=2)

        flash("✅ Block updated successfully.")
        return redirect(url_for("pdf_bp.view_pdf_blocks", filename=filename))

    block = blocks[block_index]
    return render_template("admin/pdf_edit.html", filename=filename, block=block, block_index=block_index)

@pdf_bp.route("/admin/pdf/delete/<filename>/<int:block_index>")
def delete_pdf_block(filename, block_index):
    json_path = os.path.join(EXTRACTED_FOLDER, filename)
    if not os.path.exists(json_path):
        flash("❌ JSON file not found.")
        return redirect(url_for("pdf_bp.pdf_upload"))

    with open(json_path, encoding="utf-8") as f:
        blocks = json.load(f)

    if block_index < 0 or block_index >= len(blocks):
        flash("❌ Invalid block index.")
    else:
        del blocks[block_index]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(blocks, f, ensure_ascii=False, indent=2)
        flash("🗑 Block deleted.")

    return redirect(url_for("pdf_bp.view_pdf_blocks", filename=filename))

@pdf_bp.route("/admin/pdf/create-card/<filename>/<int:block_index>")
def create_card_from_block(filename, block_index):
    json_path = os.path.join(EXTRACTED_FOLDER, filename)
    if not os.path.exists(json_path):
        flash("❌ JSON file not found.")
        return redirect(url_for("pdf_bp.pdf_upload"))

    with open(json_path, encoding="utf-8") as f:
        blocks = json.load(f)

    if block_index < 0 or block_index >= len(blocks):
        flash("❌ Invalid block index.")
        return redirect(url_for("pdf_bp.view_pdf_blocks", filename=filename))

    block = blocks[block_index]

    card = {
        "source": filename,
        "chapter": block.get("chapter"),
        "tags": block.get("tags", []),
        "text": block.get("text"),
        "images": block.get("images", []),
        "summary": block.get("summary"),
        "type": block.get("type")
    }
    card_filename = f"{filename.replace('.json', '')}_card_{block_index}.json"
    card_path = os.path.join(CARDS_FOLDER, card_filename)
    with open(card_path, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)

    flash(f"📇 Card saved as {card_filename}.")
    return redirect(url_for("pdf_bp.view_pdf_blocks", filename=filename))

@pdf_bp.route("/admin/pdf/structure/<filename>")
def pdf_structure(filename):
    structure_path = os.path.join(STRUCTURE_FOLDER, filename)
    if not os.path.exists(structure_path):
        flash("❌ Structure file not found.")
        return redirect(url_for("pdf_bp.pdf_upload"))

    with open(structure_path, encoding="utf-8") as f:
        structure = json.load(f)

    return render_template("admin/pdf_structure.html", filename=filename, structure=structure)

@pdf_bp.route('/summary/<filename>/<int:chapter_index>')
def chapter_summary(filename, chapter_index):
    structure_path = os.path.join(STRUCTURE_FOLDER, filename)
    if os.path.exists(structure_path):
        with open(structure_path, 'r', encoding='utf-8') as f:
            structure_data = json.load(f)
            chapters = structure_data.get('chapters', []) # Получаем список глав из ключа 'chapters'
            if 0 <= chapter_index < len(chapters):
                chapter_data = chapters[chapter_index]
                pdf_filename = filename.replace("_structure.json", ".pdf")
                pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                all_blocks = extract_pdf_structure(pdf_path) # Убедитесь, что эта функция возвращает нужные данные
                summary = generate_chapter_summary(all_blocks, chapter_data)
                summary_filename = f"{pdf_filename.replace('.pdf', '')}_chapter_{chapter_index}_summary.txt"
                summary_path = os.path.join(SUMMARY_FOLDER, summary_filename)
                os.makedirs(SUMMARY_FOLDER, exist_ok=True)
                with open(summary_path, 'w', encoding='utf-8') as sf:
                    sf.write(summary)
                return render_template('admin/pdf_summary.html', filename=pdf_filename, chapter_title=chapter_data['title'], summary=summary, structure_filename=filename)
            else:
                return "Глава не найдена."
    else:
        return "Структура PDF не найдена."

@pdf_bp.route('/cards/<filename>/<int:chapter_index>')
def chapter_cards(filename, chapter_index):
    structure_path = os.path.join(STRUCTURE_FOLDER, filename)
    if os.path.exists(structure_path):
        with open(structure_path, 'r', encoding='utf-8') as f:
            structure_data = json.load(f)
            chapters = structure_data.get('chapters', []) # Получаем список глав из ключа 'chapters'
            if 0 <= chapter_index < len(chapters):
                chapter_data = chapters[chapter_index]
                pdf_filename = filename.replace("_structure.json", ".pdf")
                pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                all_blocks = extract_pdf_structure(pdf_path) # Убедитесь, что эта функция возвращает нужные данные
                cards = generate_chapter_cards(all_blocks, chapter_data)
                return render_template('admin/pdf_cards.html', filename=pdf_filename, chapter_title=chapter_data['title'], cards=cards)
            else:
                return "Глава не найдена."
    else:
        return "Структура PDF не найдена."

    chapter_data = structure[chapter_index]

    with open(extracted_path, encoding="utf-8") as f_extracted:
        blocks = json.load(f_extracted)

    cards = generate_chapter_cards(blocks, chapter_data)

    # Сохраняем карточки в JSON-файл
    with open(cards_output_path, "w", encoding="utf-8") as f_cards:
        json.dump(cards, f_cards, ensure_ascii=False, indent=2)

    flash(f"✅ Generated {len(cards)} cards for chapter '{chapter_data['title']}' and saved to {os.path.basename(cards_output_path)}")
    return render_template("admin/pdf_cards.html", filename=filename, chapter_title=chapter_data['title'], cards=cards)