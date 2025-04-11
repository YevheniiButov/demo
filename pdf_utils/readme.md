# 📘 PDF Extractor for Dental Education

🧠 Интеллектуальный Python-скрипт для анализа стоматологических учебников в формате PDF.

---

## 🚀 Возможности

- 📄 Извлекает текст и изображения из PDF
- 📚 Автоматически определяет оглавление (TOC) и структуру документа
- 🧠 Использует OpenAI GPT-4o для анализа глав
- 🧹 Генерирует обучающие карточки (learning/test/summary)
- 🗒️ Создаёт краткие конспекты и JSON-структуру глав

---

## 🛠️ Установка

```bash
git clone https://github.com/yourname/pdf-extractor.git
cd pdf-extractor
python3 -m venv .venv
source .venv/bin/activate
uv install
```

---

## ⚙️ Настройка

Создайте файл `.env` в папке `pdf_utils/`:

```
OPENAI_API_KEY=sk-...
```

---

## 💻 Запуск

```bash
python3 pdf_utils/extractor.py
```

### Опции:

- `fast` — только заголовки и оглавление, без анализа
- `full` — полная обработка с анализом GPT
- `ai` — использовать AI-анализ структуры вместо TOC

Пример:

```bash
python3 pdf_utils/extractor.py full ai
```

---

## 📂 Структура выходных данных

| Папка            | Назначение                           |
|------------------|--------------------------------------|
| `extracted/`     | Все сгенерированные JSON, тексты     |
| `cards_*.json`   | Карточки по каждой главе             |
| `summary_*.txt`  | Конспекты глав                       |
| `toc_structure.json` | Структура оглавления              |

---

## 🧐 Зависимости

- `PyMuPDF (fitz)`
- `openai`
- `python-dotenv`
- `uuid`, `re`, `json`, `os`, `sys`

---

## 📌 TODO

- [ ] Добавить поддержку изображений в карточки
- [ ] Встроенное редактирование тегов через HTML-интерфейс
- [ ] Интеграция с веб-платформой Tandarts Academy

---

## 💬 Автор

[Evgenij Butov](mailto:your@email.com)

