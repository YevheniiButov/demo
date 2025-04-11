import fitz  # PyMuPDF
import os
import uuid
import openai
import json
import re
import sys
import logging

from dotenv import load_dotenv
from pathlib import Path

# Get the directory containing extractor.py
SCRIPT_DIR = Path(__file__).resolve().parent
# Assume the project root is one level up from the script's directory
PROJECT_ROOT = SCRIPT_DIR.parent
# Define output directories relative to the project root
OUTPUT_IMAGE_DIR = PROJECT_ROOT / "static" / "extracted_images"
OUTPUT_DATA_DIR = PROJECT_ROOT / "extracted"

# Загрузка .env из каталога pdf_utils
dotenv_path = SCRIPT_DIR / ".env"
load_dotenv(dotenv_path)

openai.api_key = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TAG_OPTIONS = [
    "anatomy", "physiology", "pathology", "microbiology", "pharmacology", "radiology", "dental_materials",
    "orthodontics",  "endodontics", "periodontology", "prosthodontics", "oral_surgery", "pedodontics",
    "ethics_law", "infection_control", "medical_emergencies", "diagnostics", "table", "image_caption",
    "formula", "diagram", "reference", "definition", "exam_tip", "case_study", "clinical_guideline", "question_block",
    "card_learning", "card_test", "card_summary,toets", "toetsen", "test", "diagnostic"
]

BLOCK_TYPES = ["text", "table", "formula", "caption", "question"]

mode = "full"
use_ai_structure = False  # по умолчанию используем оглавление
if len(sys.argv) > 1:
    if sys.argv[1] in ["fast", "full"]:
        mode = sys.argv[1]
    if "ai" in sys.argv:
        use_ai_structure = True
    mode = sys.argv[1]
logging.info(f"🔧 Режим работы: {mode}")

def analyze_block_with_gpt(text):
    try:
        prompt = f"""
You are an AI assistant helping to extract content from dental textbooks.
Analyze the following block of text and return a JSON object with:
- "summary": a short 1-sentence summary of the content
- "tags": a list of relevant tags from this set:
  {TAG_OPTIONS}
- "type": one of {BLOCK_TYPES}

Text block:
{text}
"""
        response = openai.chat.completions.create(
            model="gpt-4o",  # Использована модель gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"} # Явно запрашиваем JSON
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except json.JSONDecodeError as e:
        logging.error(f"⚠️ JSONDecodeError при анализе блока: {e}\nСодержимое ответа:\n{response.choices[0].message.content.strip()}")
        return {"summary": "", "tags": [], "type": "text"}
    except Exception as e:
        logging.error(f"⚠️ GPT error: {e}")
        return {"summary": "", "tags": [], "type": "text"}

def is_title_case(text):
    """Проверяет, является ли текст заголовком (Title Case)."""
    words = text.split()
    if not words:
        return False
    for word in words:
        if len(word) > 1 and not word[0].isupper() and not any(c.isupper() for c in word[1:]):
            return False
        elif len(word) == 1 and not word.isupper(): # Разрешаем одиночные заглавные буквы (например, "A.")
            return False
    return True

def is_all_caps(text):
    """Проверяет, состоит ли текст только из заглавных букв."""
    return text.isupper()

def extract_headings(pdf_path, font_size_threshold=16, top_margin_threshold=150):
    """
    Улучшенное извлечение заголовков из PDF-файла на основе размера шрифта, жирности, положения и формата текста.

    Args:
        pdf_path (str): Путь к PDF-файлу.
        font_size_threshold (int): Минимальный размер шрифта для заголовка (ужесточено).
        top_margin_threshold (int): Максимальное расстояние от верха страницы (в пикселях) для заголовка (ужесточено).

    Returns:
        list: Список словарей, где каждый словарь представляет заголовок
              и содержит текст, номер страницы и координаты.
    """
    headings = []
    try:
        doc = fitz.open(str(pdf_path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")['blocks']
            base_font_size = None
            # Попытка определить базовый размер шрифта на странице (первый текстовый блок)
            for block in blocks:
                if 'lines' in block and block['lines']:
                    base_font_size = block['lines'][0]['spans'][0]['size']
                    break
            if base_font_size is None:
                base_font_size = 12 # Значение по умолчанию, если не удалось определить

            for block in blocks:
                if 'lines' in block and len(block['lines']) > 0:
                    is_significantly_larger = False
                    is_bold = False
                    text = ""
                    max_span_size = 0
                    for line in block['lines']:
                        for span in line['spans']:
                            text += span['text']
                            max_span_size = max(max_span_size, span['size'])
                            if span['flags'] & 2**0:  # Проверяем флаг жирного шрифта
                                is_bold = True

                    if max_span_size > base_font_size * 1.3 or max_span_size > font_size_threshold:
                        is_significantly_larger = True

                    cleaned_text = text.strip()
                    is_title = is_title_case(cleaned_text)
                    is_caps = is_all_caps(cleaned_text)
                    is_short = len(cleaned_text.split()) <= 15 and len(cleaned_text.split('\n')) <= 2

                    # Ужесточенные условия для заголовка
                    if block['bbox'][1] < top_margin_threshold and is_significantly_larger and is_bold and is_short:
                        headings.append({
                            'text': cleaned_text,
                            'page': page_num + 1,
                            'bbox': block['bbox']
                        })
                    elif block['bbox'][1] < top_margin_threshold and is_significantly_larger and (is_title or is_caps) and is_short:
                        headings.append({
                            'text': cleaned_text,
                            'page': page_num + 1,
                            'bbox': block['bbox']
                        })
                    elif is_significantly_larger and is_bold and is_short and block['bbox'][1] < top_margin_threshold * 2: # Чуть менее строго для заголовков не в самом верху
                         headings.append({
                            'text': cleaned_text,
                            'page': page_num + 1,
                            'bbox': block['bbox']
                        })


        return headings

    except Exception as e:
        logging.error(f"⚠️ Ошибка при извлечении заголовков (улучшенная версия): {e}")
        return []

def find_toc_pages(pdf_path, search_range=15):
    """
    Автоматически пытается определить страницы оглавления в PDF-файле,
    ограничиваясь первыми и последними `search_range` страницами.

    Args:
        pdf_path (str): Путь к PDF-файлу.
        search_range (int): Количество страниц для поиска в начале и конце документа.

    Returns:
        list: Список номеров страниц, которые предположительно содержат оглавление.
              Возвращает пустой список, если автоматическое определение не удалось.
    """
    toc_pages = []
    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)

        # Поиск в первых страницах
        for page_num in range(min(search_range, num_pages)):
            page = doc[page_num]
            text = page.get_text().lower()
            if re.search(r"(table of contents|contents|оглавление)", text):
                toc_pages.append(page_num + 1)

        # Поиск в последних страницах (избегаем дублирования, если книга короткая)
        if num_pages > search_range:
            for page_num in range(max(0, num_pages - search_range), num_pages):
                page = doc[page_num]
                text = page.get_text().lower()
                if re.search(r"(table of contents|contents|оглавление)", text) and (page_num + 1) not in toc_pages:
                    toc_pages.append(page_num + 1)

        return sorted(list(set(toc_pages))) # Удаляем дубликаты и сортируем

    except Exception as e:
        logging.error(f"⚠️ Ошибка при поиске оглавления: {e}")
        return []

def extract_toc_text(pdf_path, toc_pages):
    """
    Извлекает весь текст с указанных страниц PDF-файла.

    Args:
        pdf_path (str): Путь к PDF-файлу.
        toc_pages (list): Список номеров страниц для извлечения текста.

    Returns:
        str: Объединенный текст со всех указанных страниц, разделенный переносами строк.
             Возвращает пустую строку в случае ошибки.
    """
    toc_text = ""
    try:
        doc = fitz.open(pdf_path)
        for page_num in toc_pages:
            if 1 <= page_num <= len(doc):
                page = doc[page_num - 1]
                toc_text += page.get_text() + "\n\n"
        return toc_text.strip()
    except Exception as e:
        logging.error(f"⚠️ Ошибка при извлечении текста оглавления: {e}")
        return ""
    
def analyze_toc_with_gpt(toc_text):

    """
    Анализирует текст оглавления с помощью GPT для определения структуры документа.

    Args:
        toc_text (str): Текст, извлеченный из оглавления PDF.

    Returns:
        list: Список словарей, где каждый словарь представляет главу
              с полями 'title', 'start_page', и возможно 'end_page'.
              Возвращает пустой список в случае ошибки.
    """
    try:
        prompt = f"""
Ты — AI-ассистент, который анализирует оглавление учебника по стоматологии.
На основе следующего текста оглавления определи главы и соответствующие начальные страницы.
Попробуй также определить конечные страницы глав, если это явно указано или можно логически вывести из следующей главы.
Верни результат в формате JSON, где каждый элемент массива представляет главу со следующими полями:
- "title": заголовок главы (строка)
- "start_page": номер начальной страницы (целое число)
- "end_page": номер конечной страницы (целое число, если определено, иначе null)

Оглавление:
{toc_text}
"""
        response = openai.chat.completions.create(
            model="gpt-4o",  # Можете использовать другую подходящую модель
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except json.JSONDecodeError as e:
        logging.error(f"⚠️ JSONDecodeError при анализе оглавления: {e}\nСодержимое ответа:\n{response.choices[0].message.content.strip()}")
        return {"chapters": json.loads(content)}
    except Exception as e:
        logging.error(f"⚠️ GPT error при анализе оглавления: {e}")
        return []    

def extract_pdf_structure(pdf_path):
    doc = fitz.open(pdf_path)
    all_blocks = []
    # Use the absolute path defined above
    os.makedirs(OUTPUT_IMAGE_DIR, exist_ok=True) # Ensure directory exists

    for page_number in range(len(doc)):
        page = doc[page_number]
        blocks = page.get_text("blocks") # Extract blocks with block numbers
        images_on_page = page.get_images(full=True)
        image_bboxes = [page.get_image_bbox(img[0]) for img in images_on_page]

        current_page_images = [] # Store images saved from this page to associate with blocks

        # --- Image Extraction ---
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image:
                    logging.warning(f"⚠️ Page {page_number+1}: Skipped image with xref={xref}: base_image is None")
                    continue

                image_bytes = base_image.get("image")
                ext = base_image.get("ext")

                if not image_bytes:
                    logging.warning(f"⚠️ Page {page_number+1}: Skipped image with xref={xref}: no image data")
                    continue

                if not ext:
                    logging.warning(f"⚠️ Page {page_number+1}: Skipped image with xref={xref}: no file extension, defaulting to 'png'")
                    ext = "png" # Default extension if missing

                # Create a more unique filename
                image_filename = f"image_{page_number+1}_{img_index+1}_{uuid.uuid4().hex}.{ext}"
                image_path = OUTPUT_IMAGE_DIR / image_filename
                logging.info(f"💾 Attempting to save image to: {image_path}") # Log the final absolute path

                try:
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    current_page_images.append(image_filename)
                    logging.info(f"📷 Saved image: {image_filename} (xref={xref}) from page {page_number+1}")
                except IOError as e:
                    logging.error(f"❌ Page {page_number+1}: Error saving image {image_filename} (xref={xref}): {e}")
                except Exception as e:
                     logging.error(f"❌ Page {page_number+1}: Unexpected error saving image {image_filename} (xref={xref}): {e}")


            except Exception as e:
                logging.error(f"❌ Page {page_number+1}: Error processing image with xref={xref}: {e}")
                continue

        # --- Block Processing ---
        for i, block in enumerate(blocks):
            # block format: (x0, y0, x1, y1, "text", block_no, block_type)
            # block_type 0 is text, 1 is image? Check PyMuPDF docs.
            if len(block) < 6: # Need at least coordinates and text
                 logging.warning(f"⚠️ Page {page_number+1}: Skipping block {i} due to unexpected format: {block}")
                 continue

            x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
            text = block[4].strip()
            block_no = block[5] # Get block number
            block_type_num = block[6] # 0 for text, 1 for image

            if block_type_num == 1: # Skip image blocks themselves, we handle images separately
                continue

            if not text: # Skip empty text blocks
                continue

            is_related_to_image = False
            block_bbox = (x0, y0, x1, y1)
            # Check proximity to any image on the page
            for img_bbox in image_bboxes:
                if fitz.Rect(block_bbox).intersects(fitz.Rect(img_bbox)) or \
                   fitz.Rect(block_bbox).is_near(fitz.Rect(img_bbox), distance=20):
                    is_related_to_image = True
                    break

            # *** UNCOMMENTED THIS SECTION ***
            if text:
                gpt_data = analyze_block_with_gpt(text) # Analyze the text block

                # Determine block type more robustly
                final_type = gpt_data.get("type", "text")
                tags = set(gpt_data.get("tags", []))

                # Add heuristic tags/types
                if re.search(r'=|\^|\d+\s*/\s*\d+', text):
                    tags.add("formula")
                    if final_type == "text": final_type = "formula" # Prioritize formula if detected
                if re.search(r'\bcolumn\b|\brow\b|\btable\b|\d+\s*\|\s*\d+', text, re.IGNORECASE):
                    tags.add("table")
                    if final_type == "text": final_type = "table" # Prioritize table
                if re.search(r'(?i)\b(quiz|test|question|choose the correct|exam tip|review question)\b', text):
                    tags.update(["quiz", "question_block", "exam_tip"])
                    if final_type == "text": final_type = "question" # Prioritize question

                # If GPT identified as caption, mark as related to image
                if gpt_data.get("type") == "caption":
                    is_related_to_image = True
                    tags.add("image_caption") # Ensure tag is present

                block_data = {
                    "page": page_number + 1,
                    "text": text,
                    "images": current_page_images[:], # Associate *all* images from the page for now
                    "summary": gpt_data.get("summary", ""),
                    "tags": list(tags),
                    "type": final_type,
                    "block_coords": [x0, y0, x1, y1],
                    "block_id": block_no, # Use the block number from PyMuPDF
                    "is_related_to_image": is_related_to_image
                }
                all_blocks.append(block_data)
            # *** END OF UNCOMMENTED SECTION ***

        # Clear page images list for the next page (optional, good practice)
        # current_page_images = [] # Reset for next page if association should be strictly per-block

    return all_blocks


def analyze_structure_with_ai(blocks):
    try:
        text_by_page = {}
        blocks_by_id = {block['block_id']: block for block in blocks if block['block_id'] != -1} # Создаем словарь блоков по ID
        for block in blocks:
            page = block['page']
            if page not in text_by_page:
                text_by_page[page] = []
            text_by_page[page].append(block['text'])

        ordered_text = "\n\n".join([f"[Page {page}]\n" + "\n".join(text_by_page[page]) for page in sorted(text_by_page.keys())])

        prompt = f"""
Ты — ассистент AI, который анализирует структуру учебного текста по стоматологии.
Проанализируй следующий текст и определи главы, их заголовки, основную тему и границы (начало и конец).
Верни результат в формате JSON, где каждый элемент массива представляет главу со следующими полями:
- "title": заголовок главы
- "theme": основная тема главы
- "start_page": номер начальной страницы
- "end_page": номер конечной страницы
- "content_block_ids": список идентификаторов блоков текста (поле 'block_id' из входных данных), относящихся к этой главе.

Текст:
{ordered_text[:15000]}  # Увеличим лимит, если необходимо
"""
        response = openai.chat.completions.create(
            model="gpt-4o",  # Использована модель gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"} # Явно запрашиваем JSON
        )
        content = response.choices[0].message.content.strip()
        structure = json.loads(content)
        if 'chapters' in structure:
            for chapter in structure['chapters']:
                image_names = set()
                has_image_related_content = False
                for block_id in chapter.get('content_block_ids', []):
                    if block_id in blocks_by_id:
                        block = blocks_by_id[block_id]
                        image_names.update(block.get('images', []))
                        if block.get('is_related_to_image', False):
                            has_image_related_content = True
                chapter['image_names'] = list(image_names)
                chapter['has_image_related_content'] = has_image_related_content
        return structure
    except json.JSONDecodeError as e:
        logging.error(f"⚠️ JSONDecodeError при анализе структуры: {e}\nСодержимое ответа:\n{response.choices[0].message.content.strip()}")
        return []
    except Exception as e:
        logging.error(f"⚠️ AI structure analysis failed: {e}")
        return []

def generate_chapter_summary(blocks, chapter_data):
    """
    Генерирует краткий конспект для заданной главы, используя GPT-3.5-turbo и информацию об изображениях.

    Args:
        blocks (list): Список всех блоков текста из PDF.
        chapter_data (dict): Данные о главе из структуры, включая 'content_block_ids' и 'image_names'.

    Returns:
        str: Сгенерированный конспект главы. Возвращает пустую строку в случае ошибки.
    """
    try:
        chapter_text_blocks = [block for block in blocks if block['block_id'] in chapter_data['content_block_ids']]
        chapter_text = "\n\n".join([block['text'] for block in chapter_text_blocks])
        chapter_images = chapter_data.get('image_names', [])
        image_prompt_part = f"\n\nИзображения, связанные с этой главой: {', '.join(chapter_images)}" if chapter_images else "\n\nС этой главой не связаны изображения."

        prompt = f"""
Ты - AI-ассистент, который создает краткие конспекты для учебных материалов по стоматологии.
На основе следующего текста главы:

{chapter_text}

{image_prompt_part}

создай краткий, но содержательный конспект, охватывающий основные моменты, включая информацию, представленную на связанных изображениях (если они есть).
Конспект должен быть не более 5 предложений.
"""
        response = openai.chat.completions.create(
            model="gpt-4o",  # Использована модель gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"⚠️ GPT error во время создания конспекта главы (с изображениями): {e}")
        return ""

def generate_chapter_cards(blocks, chapter_data):
    """
    Генерирует список обучающих карточек для заданной главы, учитывая связь текста с изображениями (улучшенный промпт).

    Args:
        blocks (list): Список всех блоков текста из PDF.
        chapter_data (dict): Данные о главе из структуры, включая 'content_block_ids', 'image_names' и 'has_image_related_content'.

    Returns:
        list: Список сгенерированных карточек в формате JSON. Возвращает пустой список в случае ошибки.
    """
    try:
        chapter_text_blocks = [block for block in blocks if block['block_id'] in chapter_data['content_block_ids']]
        chapter_text = "\n\n".join([block['text'] for block in chapter_text_blocks])
        chapter_images = chapter_data.get('image_names', [])
        has_image_content = chapter_data.get('has_image_related_content', False)
        image_prompt_part = f"\n\nИзображения, связанные с этой главой: {', '.join(chapter_images)}" if chapter_images else "\n\nС этой главой не связаны изображения."
        image_relation_hint = "В этой главе есть текстовые фрагменты, которые могут быть связаны с изображениями." if has_image_content else "В этой главе нет явных текстовых фрагментов, связанных с изображениями."

        prompt = f"""
Ты — интеллектуальный ассистент, помогающий создавать обучающие карточки для студентов-стоматологов.
На основе следующего текста главы:

{chapter_text}

{image_prompt_part}
{image_relation_hint}

Если в тексте главы или на связанных изображениях встречаются уже готовые вопросы (например, из раздела "Review Questions", "Test Yourself", "Quiz", "Вопросы для самоконтроля" и т.п.), используй в первую очередь эти вопросы для создания карточек типа "test".
Если таких вопросов недостаточно, можешь дополнительно сгенерировать недостающие тестовые карточки.

Создай список из 10–15 обучающих карточек, в формате JSON. Для каждой карточки укажи:
- "type": один из "learning", "test", "summary"
- "question": что будет отображаться пользователю (для "test" — сам вопрос)
- "answer": ответ на карточку (для "test" — правильный вариант ответа, для "learning" — объяснение)
- "tags": ключевые теги по содержанию из этого списка: {', '.join(TAG_OPTIONS)}
- "image_hint": укажи true, если карточка напрямую основана на информации из текстового фрагмента, связанного с изображением, или если она объясняет/иллюстрирует ключевой аспект одного из связанных изображений (даже без прямого текста). В противном случае укажи false. Попробуй создать карточки, которые явно ссылаются на содержание изображений.

Для карточек типа "learning": объясняй тему в 3–7 предложениях, как если бы ты обучал студента с нуля.
Для карточек типа "test": сгенерируй вопрос с 3-4 вариантами ответов (a, b, c, d). Правильный вариант должен быть четко указан в поле "answer".
Для "summary": сделай краткий повтор ключевых моментов, включая информацию с изображений, если это уместно.

Верни результат в формате JSON (массив карточек).
"""
        response = openai.chat.completions.create(
            model="gpt-4o",  # Использована модель gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"} # Явно запрашиваем JSON
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except json.JSONDecodeError as e:
        logging.error(f"⚠️ JSONDecodeError при генерации карточек главы (с учетом связи с изображениями): {e}\nСодержимое ответа:\n{response.choices[0].message.content.strip()}")
        return []
    except Exception as e:
        logging.error(f"⚠️ GPT error во время создания карточек главы (с учетом связи с изображениями): {e}")
        return []
    #------------------------------------------
def generate_learning_cards(blocks):
    return [block for block in blocks if "card_learning" in block.get("tags", [])]

def generate_chapter_summary_from_text(text, chapter_data):
    try:
        prompt = f"""
Ты - AI-ассистент, который создает краткие конспекты для учебных материалов по стоматологии.
На основе следующего текста главы создай краткий, но содержательный конспект, охватывающий основные моменты.
Конспект должен быть не более 5 предложений.

Текст главы:
{text}
"""
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"⚠️ GPT error во время создания текстового конспекта главы: {e}")
        return ""

def generate_chapter_cards_from_text(text, chapter_data):
    try:
        prompt = f"""
Ты — интеллектуальный ассистент, помогающий создавать обучающие карточки для студентов-стоматологов.
На основе следующего текста главы:

{text}

Создай список из 10–15 обучающих карточек, в формате JSON. Для каждой карточки укажи:
- "type": один из "learning", "test", "summary"
- "question": что будет отображаться пользователю
- "answer": ответ на карточку (для test — правильный вариант, для learning — объяснение)
- "tags": ключевые теги по содержанию из этого списка: {', '.join(TAG_OPTIONS)}
- "image_hint": true/false

Верни результат в формате JSON (массив карточек).
"""
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logging.error(f"⚠️ GPT error при генерации карточек из текста: {e}")
        return []


def generate_test_cards(blocks):
    return [block for block in blocks if "card_test" in block.get("tags", [])]

def generate_summary_cards(blocks):
    return [block for block in blocks if "card_summary" in block.get("tags", [])]

def extract_pdf_structure_with_ai(pdf_path):
    return extract_pdf_structure(pdf_path)

def extract_chapter_text(pdf_path, start_page, end_page):
    """
    Извлекает объединенный текст из диапазона страниц PDF-файла.

    Args:
        pdf_path (str): Путь к PDF-файлу.
        start_page (int): Номер начальной страницы.
        end_page (int): Номер конечной страницы.

    Returns:
        str: Объединенный текст с указанных страниц, разделенный переносами строк.
             Возвращает пустую строку в случае ошибки или некорректного диапазона страниц.
    """
    chapter_text = ""
    try:
        doc = fitz.open(pdf_path)
        try:
            start_page_int = int(start_page)
            end_page_int = int(end_page)
            if 1 <= start_page_int <= end_page_int <= len(doc):
                for page_num in range(start_page_int - 1, end_page_int):  # fitz индексирует страницы с 0
                    page = doc[page_num]
                    chapter_text += page.get_text() + "\n\n"
            else:
                logging.error(f"⚠️ Некорректный диапазон страниц: {start_page}-{end_page}")
        except ValueError:
            logging.error(f"⚠️ Ошибка преобразования страниц в целое число: start_page={start_page}, end_page={end_page}")
        except Exception as e:
            logging.error(f"⚠️ Непредвиденная ошибка при обработке номеров страниц: {e}")
        return chapter_text.strip()
    except Exception as e:
        logging.error(f"⚠️ Ошибка при открытии PDF или извлечении текста главы: {e}")
        return ""

if __name__ == '__main__':
    # Define the input PDF path relative to the project root for testing
    # Ensure the 'uploads' directory exists at the project root
    pdf_input_path = PROJECT_ROOT / "uploads" / "Wheelers_Dental_Anatomy_Physiology_and_Occlusion_11e_Original_PDF.pdf"

    # Check if PDF file exists
    if not pdf_input_path.is_file():
        logging.error(f"❌ Input PDF file not found at: {pdf_input_path}")
        sys.exit(1) # Exit if PDF is missing

    # Ensure output directories exist (using absolute paths)
    try:
        os.makedirs(OUTPUT_IMAGE_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)
        logging.info(f"Image Output Dir: {OUTPUT_IMAGE_DIR}")
        logging.info(f"Data Output Dir: {OUTPUT_DATA_DIR}")
    except Exception as e:
        logging.error(f"❌ Failed to create output directories: {e}", exc_info=True)
        sys.exit(1) # Exit if directories can't be created

    logging.info(f"Processing PDF: {pdf_input_path}")

    if use_ai_structure:
        logging.info("🧠 Using AI structure analysis (extract_pdf_structure + analyze_structure_with_ai)")
        # Pass the absolute path string to the extraction function
        all_blocks = extract_pdf_structure(str(pdf_input_path))
        if not all_blocks:
             logging.error("❌ Failed to extract any blocks from PDF. AI structure analysis cannot proceed.")
        else:
            logging.info(f"📊 Extracted {len(all_blocks)} blocks.")
            logging.info("🤖 Analyzing structure with AI...")
            structure = analyze_structure_with_ai(all_blocks)
            ai_structure_path = OUTPUT_DATA_DIR / "ai_structure.json"
            try:
                with open(ai_structure_path, "w", encoding="utf-8") as f:
                    json.dump(structure, f, ensure_ascii=False, indent=2)
                logging.info(f"✅ AI structure saved to {ai_structure_path}")
            except Exception as e:
                 logging.error(f"❌ Error saving AI structure to {ai_structure_path}: {e}", exc_info=True)

            # --- Process chapters based on AI structure ---
            if structure and 'chapters' in structure and structure['chapters']:
                logging.info(f"🤖 AI identified {len(structure['chapters'])} chapters. Processing each...")
                for i, chapter in enumerate(structure['chapters'], 1):
                    title = chapter.get('title', f'AI_Chapter_{i}')
                    safe_title = sanitize_filename(f"ai_{title}") # Sanitize for filename
                    if not safe_title: safe_title = f"AI_Chapter_{i}" # Fallback

                    logging.info(f"--- Processing AI Chapter {i}/{len(structure['chapters'])}: '{title}' ---")

                    block_ids = chapter.get('content_block_ids', [])
                    if not block_ids:
                        logging.warning(f"⚠️ AI Chapter '{title}' has no associated content block IDs. Skipping summary/card generation.")
                        continue

                    # Filter blocks for the current chapter
                    chapter_blocks = [block for block in all_blocks if block.get('block_id') in block_ids]
                    if not chapter_blocks:
                         logging.warning(f"⚠️ AI Chapter '{title}': No blocks found matching IDs {block_ids}. Skipping summary/card generation.")
                         continue

                    logging.info(f"Chapter '{title}': Found {len(chapter_blocks)} associated blocks.")

                    # Generate summary
                    summary_filename = f"summary_{safe_title}.txt"
                    summary_path = OUTPUT_DATA_DIR / summary_filename
                    try:
                        logging.info(f"Generating summary for AI chapter '{title}'...")
                        summary = generate_chapter_summary(chapter_blocks, chapter)
                        if summary:
                            with open(summary_path, "w", encoding="utf-8") as f:
                                f.write(summary)
                            logging.info(f"✅ AI Summary saved to {summary_path}")
                        else:
                            logging.warning(f"⚠️ Generated summary for AI chapter '{title}' was empty.")
                    except Exception as e:
                        logging.error(f"❌ Error generating summary for AI chapter '{title}': {e}", exc_info=True)

                    # Generate cards
                    cards_filename = f"cards_{safe_title}.json"
                    cards_path = OUTPUT_DATA_DIR / cards_filename
                    try:
                        logging.info(f"Generating cards for AI chapter '{title}'...")
                        cards_data = generate_chapter_cards(chapter_blocks, chapter) # Expecting a dict/list from JSON
                        if cards_data: # Check if cards_data is not empty
                             # Ensure it's saved as a JSON array if the function returns one directly
                            cards_to_save = cards_data.get('cards', cards_data) if isinstance(cards_data, dict) else cards_data
                            if isinstance(cards_to_save, list):
                                with open(cards_path, "w", encoding="utf-8") as f:
                                    json.dump(cards_to_save, f, ensure_ascii=False, indent=2)
                                logging.info(f"✅ AI Cards saved to {cards_path}")
                            else:
                                 logging.warning(f"⚠️ Card generation for AI chapter '{title}' did not return a list.")
                        else:
                            logging.warning(f"⚠️ Generated cards data for AI chapter '{title}' was empty.")
                    except Exception as e:
                        logging.error(f"❌ Error generating cards for AI chapter '{title}': {e}", exc_info=True)
            else:
                 logging.warning("⚠️ AI analysis did not return a valid 'chapters' list in the structure.")

    else: # --- Use Table of Contents (TOC) based approach ---
        logging.info("📖 Using Table of Contents (TOC) analysis")
        toc_pages = find_toc_pages(str(pdf_input_path))

        if not toc_pages:
            logging.warning("⚠️ Could not automatically find TOC pages. Attempting heading extraction as fallback?")
            # Optionally add heading extraction logic here if TOC fails
            # headings = extract_headings(str(pdf_input_path))
            # if headings: ... process based on headings ...
        else:
            logging.info(f"📖 Found potential TOC pages: {toc_pages}")
            toc_text = extract_toc_text(str(pdf_input_path), toc_pages)

            if not toc_text:
                logging.warning("⚠️ Failed to extract text from TOC pages.")
            else:
                logging.info("🤖 Analyzing TOC text with AI...")
                toc_analysis_result = analyze_toc_with_gpt(toc_text)

                chapter_structure = None
                if isinstance(toc_analysis_result, dict) and 'chapters' in toc_analysis_result:
                     chapter_structure = toc_analysis_result['chapters']
                elif isinstance(toc_analysis_result, list): # Handle case where it might return a list directly
                     chapter_structure = toc_analysis_result

                if not chapter_structure:
                     logging.warning(f"⚠️ Failed to analyze TOC structure using AI. Response: {toc_analysis_result}")
                else:
                    logging.info(f"📖 TOC analysis identified {len(chapter_structure)} chapters. Processing each...")
                    for i, chapter in enumerate(chapter_structure, 1):
                        title = chapter.get('title', f'TOC_Chapter_{i}')
                        start_page = chapter.get('start_page')
                        end_page = chapter.get('end_page')

                        safe_title = sanitize_filename(f"toc_{title}") # Sanitize for filename
                        if not safe_title: safe_title = f"TOC_Chapter_{i}" # Fallback

                        logging.info(f"--- Processing TOC Chapter {i}/{len(chapter_structure)}: '{title}' (Pages: {start_page}-{end_page}) ---")

                        if start_page is not None and end_page is not None:
                            try:
                                start_page_int = int(start_page)
                                end_page_int = int(end_page)

                                if start_page_int <= 0 or end_page_int < start_page_int:
                                     logging.warning(f"⚠️ Invalid page range for TOC chapter '{title}': {start_page_int}-{end_page_int}. Skipping.")
                                     continue

                                logging.info(f"Extracting text for TOC chapter '{title}' (pages {start_page_int}-{end_page_int})")
                                chapter_text = extract_chapter_text(str(pdf_input_path), start_page_int, end_page_int)
                                logging.info(f"Extracted text length: {len(chapter_text)}")

                                if not chapter_text:
                                    logging.warning(f"⚠️ No text extracted for TOC chapter '{title}'. Skipping summary/card generation.")
                                    continue

                                # Generate summary from text
                                summary_filename = f"summary_{safe_title}.txt"
                                summary_path = OUTPUT_DATA_DIR / summary_filename
                                try:
                                    logging.info(f"Generating summary for TOC chapter '{title}'...")
                                    summary = generate_chapter_summary_from_text(chapter_text, chapter) # Pass chapter data for context if needed
                                    if summary:
                                        with open(summary_path, "w", encoding="utf-8") as f:
                                            f.write(summary)
                                        logging.info(f"✅ TOC Summary saved to {summary_path}")
                                    else:
                                        logging.warning(f"⚠️ Generated summary for TOC chapter '{title}' was empty.")
                                except Exception as e:
                                    logging.error(f"❌ Error generating summary for TOC chapter '{title}': {e}", exc_info=True)

                                # Generate cards from text
                                cards_filename = f"cards_{safe_title}.json"
                                cards_path = OUTPUT_DATA_DIR / cards_filename
                                try:
                                    logging.info(f"Generating cards for TOC chapter '{title}'...")
                                    cards_data = generate_chapter_cards_from_text(chapter_text, chapter) # Pass chapter data for context
                                    if cards_data: # Check if cards_data is not empty
                                        # Ensure it's saved as a JSON array
                                        cards_to_save = cards_data.get('cards', cards_data) if isinstance(cards_data, dict) else cards_data
                                        if isinstance(cards_to_save, list):
                                            with open(cards_path, "w", encoding="utf-8") as f:
                                                json.dump(cards_to_save, f, indent=2, ensure_ascii=False)
                                            logging.info(f"✅ TOC Cards saved to {cards_path}")
                                        else:
                                            logging.warning(f"⚠️ Card generation for TOC chapter '{title}' did not return a list.")
                                    else:
                                        logging.warning(f"⚠️ Generated cards data for TOC chapter '{title}' was empty.")
                                except Exception as e:
                                    logging.error(f"❌ Error generating cards for TOC chapter '{title}': {e}", exc_info=True)

                            except ValueError:
                                logging.error(f"⚠️ Invalid page numbers for TOC chapter '{title}': start='{start_page}', end='{end_page}'", exc_info=True)
                            except Exception as e:
                                logging.error(f"❌ Unexpected error processing TOC chapter '{title}': {e}", exc_info=True)
                        else:
                            logging.warning(f"⚠️ Missing start or end page for TOC chapter '{title}'. Skipping text extraction.")

    logging.info("🏁 PDF processing finished.")
