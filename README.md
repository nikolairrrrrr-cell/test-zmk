# test-zmk

Три независимых CLI-инструмента для работы с чертежами и Google Sheets.

| Инструмент | Назначение | Лист в Google Sheets |
|---|---|---|
| `pdf-zmk` | Извлечение данных из чертежей/изображений типа PDF_ZMK | `PDF_ZMK` |
| `pdf-zmk2` | Извлечение данных из чертежей типа PDF_ZMK2 | `PDF_ZMK2` |
| `ves` | Парсинг веса с сайтов, кэш, выгрузка | `PDF_ZMK_VES` |

## Структура проекта

```
app/
  cli.py              — единый CLI: pdf-zmk, pdf-zmk2, ves
  config.py            — настройки (Google Sheets ID, пути к credentials)
  sheets_gateway.py    — работа с Google Sheets API
  recognizers/
    agent.py           — AgentRecognizer + фазы пайплайна
    table_pipeline.py  — crop + upscale таблиц из изображений
    base.py            — AgentReadRequired, RecognitionError
  use_cases/
    pdf_zmk.py         — логика pdf-zmk full
    pdf_zmk2.py        — логика pdf-zmk2
    ves.py             — логика ves
ves/                   — скраперы для opora-trub.ru и awstroy.ru
normalizer/            — нормализация данных для Google Sheets
data/recognition/      — кропы (*.table_x4.jpg) и JSON-пейлоады (*.json)
scripts/
  run-tools.sh         — хелпер для macOS/Linux
  run-tools.ps1        — хелпер для Windows PowerShell
docs/contracts/        — контракты CLI-инструментов
tests/                 — pytest
```

## Требования

- Python 3.9+ (рекомендуется 3.11+)
- Интернет для `ves` (парсинг сайтов) и для Google Sheets API
- `credentials.json` для Google OAuth (см. раздел ниже)

## Установка

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Если `py` не найден, используй `python` вместо `py`.
> Если PowerShell блокирует скрипт активации:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

## Настройка Google Sheets

### 1. Получение `credentials.json`

1. Открой [Google Cloud Console](https://console.cloud.google.com/).
2. Создай проект (или выбери существующий).
3. Включи **Google Sheets API** (APIs & Services → Enable APIs).
4. Создай OAuth 2.0 Client ID (APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app).
5. Скачай JSON и сохрани как `credentials.json` в корень проекта.

### 2. Первый запуск (OAuth логин)

При первом запуске любой команды с `--sheet-write` откроется браузер для авторизации Google-аккаунта. После подтверждения создастся `token.json` — он хранит токен доступа и обновляется автоматически.

> На Windows без браузера (сервер/RDP): убедись, что порт localhost не заблокирован файрволом — OAuth использует временный локальный HTTP-сервер.

### 3. Переменные окружения (опционально)

По умолчанию проект ищет файлы в корне. Переопределить можно через env:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `GOOGLE_SPREADSHEET_ID` | встроенный ID | ID Google-таблицы |
| `GOOGLE_CREDENTIALS_PATH` | `credentials.json` | Путь к OAuth credentials |
| `GOOGLE_TOKEN_PATH` | `token.json` | Путь к сохранённому токену |

## Команды CLI

### pdf-zmk full

Единственная команда для обработки чертежей PDF_ZMK. Всегда работает по strict pipeline.

```bash
# macOS/Linux
python3 -m app.cli pdf-zmk full --input-dir new --sheet-write

# Windows
py -m app.cli pdf-zmk full --input-dir new --sheet-write
```

Флаги:
- `--input-dir` (обязательно) — папка с изображениями/PDF
- `--sheet-write` — записать результат в Google Sheets
- `--dry-run` — обработать, но не писать в Sheets
- `--workers N` — количество потоков (по умолчанию 6)
- `--output-json path` — сохранить отчёт о запуске

### pdf-zmk2 run

```bash
# macOS/Linux
python3 -m app.cli pdf-zmk2 run --input path/to/payload.json --sheet-write

# Windows
py -m app.cli pdf-zmk2 run --input path/to/payload.json --sheet-write
```

### ves run

```bash
# macOS/Linux
python3 -m app.cli ves run --positions ves/test_positions.txt --online --force-refresh --sheet-write

# Windows
py -m app.cli ves run --positions ves/test_positions.txt --online --force-refresh --sheet-write
```

Флаги:
- `--positions` (обязательно) — файл со списком позиций
- `--online` — парсить сайты (без флага — только кэш)
- `--force-refresh` — игнорировать кэш, перескрапить всё
- `--dry-run` — не писать в Sheets
- `--db-path` — путь к кэш-файлу (по умолчанию `weights_db.json`)

## PDF_ZMK strict pipeline

`pdf-zmk full` работает в 4 фазы. Ни одна не может быть пропущена.

```
Phase 1: CROP + UPSCALE
  Для каждого изображения в --input-dir:
  → обнаружение таблицы → crop → upscale x4
  → сохранение в data/recognition/<slug>.table_x4.jpg

Phase 2: AGENT READ (жёсткий гейт)
  Если для какого-то кропа нет JSON-пейлоада:
  → CLI падает с exit code 3 (AGENT_READ_REQUIRED)
  → агент в Cursor читает каждый crop, извлекает данные таблицы
  → записывает data/recognition/<slug>.json

Phase 3: WRITE JSON
  Агент пишет пейлоад:
  {"drawing_name": "...", "items": [{"poz","designation","name","qty","weight"}]}
  Пустой items запрещён.

Phase 4: NORMALIZE + SHEETS
  Повторный запуск pdf-zmk full:
  → загрузка всех JSON → нормализация → запись в Google Sheet PDF_ZMK
```

Exit-коды: `0` — успех, `2` — ошибка входных данных, `3` — AGENT_READ_REQUIRED, `5` — runtime ошибка.

## Хелпер-скрипты

```bash
# macOS/Linux
./scripts/run-tools.sh pdf-zmk new
./scripts/run-tools.sh ves

# Windows PowerShell
.\scripts\run-tools.ps1 -Command pdf-zmk -InputPath new
.\scripts\run-tools.ps1 -Command ves
```

## Тесты

```bash
# macOS/Linux
python3 -m pytest -q

# Windows
py -m pytest -q
```

## Troubleshooting

| Проблема | Решение |
|---|---|
| `python3` не найден на Windows | Используй `py` или `python` |
| PowerShell блокирует `.ps1` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| OAuth: браузер не открывается | Проверь что localhost не блокируется файрволом/антивирусом |
| OAuth: `token.json` протух | Удали `token.json` и запусти команду с `--sheet-write` заново |
| Пути с кириллицей/пробелами | Оборачивай пути в кавычки: `--input-dir "Мои чертежи"` |
| `ModuleNotFoundError` | Убедись что venv активирован и `pip install -r requirements.txt` выполнен |
| Exit code 3 при `pdf-zmk full` | Нормальное поведение — агент должен прочитать кропы и записать JSON |
