## Raw-спецификации

- `data/raw_specs/pdf_zmk/*.csv` — сырые спецификации для листа `PDF_ZMK`.
  - Формат колонок: `poz;designation;name;qty;weight`.
  - Эти файлы повторяют таблицу чертежа `Поз / Обозначение / Наименование / Кол / Примеч.` без нормализации.
  - Используются как fallback в `AgentRecognizer._try_build_payload_from_raw_specs()`.
- `data/raw_specs/pdf_zmk2/*.csv` — сырые спецификации стали для листа Google **`СЕ1`** (pdf-zmk2).
  - Формат: `elem;det;t;n;section;length;mass_sht;mass_total;note`.

## Пайплайн

1. Добавить чертёж (JPEG/PNG/PDF) в `new/`.
2. Запустить:

   ```bash
   # macOS/Linux
   python3 -m app.cli pdf-zmk full --input-dir new --sheet-write

   # Windows
   py -m app.cli pdf-zmk full --input-dir new --sheet-write
   ```

3. CLI автоматически кропает таблицу и апскейлит x4 (`data/recognition/<slug>.table_x4.jpg`).
4. Если JSON-пейлоад отсутствует — CLI падает с `AGENT_READ_REQUIRED` (exit 3). Агент читает кроп и записывает JSON.
5. При повторном запуске нормализатор `normalizer/pdf_zmk_normalizer.py` обрабатывает данные и пишет в Google Sheet `PDF_ZMK`.
