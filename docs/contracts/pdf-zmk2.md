# Contract: `pdf-zmk2` tool

## Purpose
Process drawings/images of type `PDF_ZMK2`, normalize extracted rows, optionally write data to Google Sheets tab **`СЕ1`** (override with env `GOOGLE_SHEET_PDF_ZMK2`).

**Источник истины для строк таблицы:** только чтение кропа `data/recognition/<slug>.table_x4.jpg` (агент/человек). Подстановка строк из сторонних «эталонных» файлов без разбора кропа нарушает контракт; см. `docs/pdf_zmk2-instrukciya.md`.

## CLI

**Один файл** (перезаписывает весь лист **`СЕ1`** только этим чертежом):

`python -m app.cli pdf-zmk2 run --input <path> [--sheet-write] [--dry-run] [--output-json <path>]`

**Папка — как `pdf-zmk full` / База2** (все документы в каталоге → один merge → одна запись на лист):

`python -m app.cli pdf-zmk2 full [--input-dir <dir>] [--sheet-write] [--dry-run] [--workers <n>] [--output-json <path>]`

Если `--input-dir` не указан, используется папка **`СЕ1`** в корне проекта (или путь из **`PDF_ZMK2_INPUT_DIR`**). Договорённость: в **`СЕ1`** — исходники; payload и кропы — в **`data/recognition/`** (аналогично `pdf-zmk`).

## Strict pipeline (4 phases) — как у База2 (pdf-zmk)

Конвейер **обязательный и последовательный**. Ни один этап не пропускается.

### Phase 1 — CROP + UPSCALE
Для каждого изображения в `--input-dir` (или СЕ1):
1. Найти область таблицы (адаптивный bbox или статический fallback).
2. Вырезать кроп.
3. Увеличить кроп ×4.
4. Сохранить в `data/recognition/<slug>.table_x4.jpg`.

### Phase 2 — AGENT READ (гейт)
CLI проверяет: у каждого кропа есть `data/recognition/<slug>.json` с непустым `items`?

Если **хотя бы одного** payload нет или он пустой:
- CLI поднимает **`AgentReadRequired`** (exit code 3).
- Выводит список ожидаемых кропов и путей к JSON.
- **Агент в Cursor обязан**: открыть каждый кроп, прочитать таблицу спецификации, выписать строки (отпр/дет, сечение, длина, массы, примечания), записать `data/recognition/<slug>.json`.

Без локального OCR. Без внешнего LLM API. Читает агент.

### Phase 3 — WRITE JSON
Агент пишет каждый payload в схеме PDF_ZMK2 (`drawing_name`, `items` с полями `elem`, `det`, `t`, `n`, `section`, `length`, `mass_sht`, `mass_total`, `note` и при необходимости `mass_elem`, `steel`).

### Phase 4 — NORMALIZE + SHEETS
Повторный запуск `pdf-zmk2 full` (с или без `--sheet-write`):
- Загрузка всех JSON из `data/recognition/` по подготовленному списку.
- Нормализация строк по колонкам листа (схема PDF_ZMK2).
- Склейка блоков (пустая строка между чертежами, шапка один раз в начале).
- При `--sheet-write`: очистка листа **`СЕ1`** и запись результата.

## Inputs

### `run`
- `--input` (required): path to recognition payload (JSON) or source asset path.
- `--sheet-write` (optional): write to Google Sheets.
- `--dry-run` (optional): process data but do not write to Google Sheets.
- `--output-json` (optional): write execution report JSON.

### `full`
- `--input-dir` (optional): folder with images/PDF/JSON (same rules as `pdf-zmk full`). Default: **`СЕ1`** / `PDF_ZMK2_INPUT_DIR`.
- `--sheet-write`, `--dry-run`, `--output-json` — same as `run`.
- `--workers` — зарезервировано под совместимость с CLI `pdf-zmk full` (по умолчанию 6).

## Recognition contract
The tool uses `AgentRecognizer` (no local OCR). Recognizer output for this tool:

```json
{
  "drawing_name": "630-13",
  "items": [
    {
      "elem": "",
      "det": "8",
      "t": "4",
      "n": "",
      "section": "Шайба 30 ГОСТ 11371-78*",
      "length": "",
      "mass_sht": "0,053",
      "mass_total": "0,21",
      "note": ""
    }
  ]
}
```

### Field semantics vs Google Sheet columns

Per `docs/nonstandard-rules.md` (тип 2 / PDF_ZMK2):

- **`elem`** — отпр. элем.; **`det`** — номер детали; **`t`** / **`n`** — развёртка КОЛ (колонки «т.» / «н.»).

**Legacy layout (still supported):** if **`elem` is empty**, the pipeline treats **`det` / `t`** as **отпр. элем. / дет.** (same as `data/raw_specs/pdf_zmk2/*.csv`). In that case **`n`** maps to column «т.» (first part of КОЛ if present); use a non-empty **`elem`** when both деталь and full КОЛ need separate `t`/`n`.

## Outputs
- Normalized rows in memory (2D list, row schema for PDF_ZMK2).
- Optional write to Google Sheet tab **`СЕ1`**.
- Optional JSON report (`run`): `tool`, `status`, `rows_count`, `sheet_written`, `input_path`.
- Optional JSON report (`full`): как у `pdf-zmk full` — `total_files`, `processed_files`, `rows_count`, `processed`, `elapsed_seconds`, и т.д.

## Side effects
- If `--sheet-write` and not `--dry-run`: clears and updates `СЕ1!A:Z` (или имя из `GOOGLE_SHEET_PDF_ZMK2`).
- If `--output-json`: writes report file to disk.

## Exit codes
- `0`: success.
- `2`: invalid input contract/arguments.
- `3`: `AGENT_READ_REQUIRED` (для `full` — нет валидного JSON по кропу).
- `4`: Google auth/sheets failure.
- `5`: unexpected runtime error (в т.ч. часть файлов в `full` с ошибкой валидации).
