## Модуль `ves`: автоматический поиск веса опор

Этот модуль отвечает за полный цикл работы с весами опор:

- чтение входного файла с позициями;
- поиск и кэширование весов по доверенным сайтам;
- агрегация результатов по доменам;
- подготовка данных для листа Google Sheets `PDF_ZMK_VES`.

Запуск через CLI:

```bash
# macOS/Linux
python3 -m app.cli ves run --positions ves/test_positions.txt --online --force-refresh --sheet-write

# Windows
py -m app.cli ves run --positions ves/test_positions.txt --online --force-refresh --sheet-write
```

### Файлы модуля

- `ves/test_positions.txt`
  Тестовый список позиций (по одной на строку), на которых отлаживается пайплайн поиска веса и заполнения листа `PDF_ZMK_VES`.

- `ves/weights_db.json`
  Единая локальная база найденных весов. Хранится в виде JSON-объекта вида:

  ```json
  {
    "57-КХ-А11": {
      "name": "57-КХ-А11",
      "sources": [
        {
          "domain": "detalneftehim.ru",
          "url": "https://detalneftehim.ru/...",
          "weight": 1.4,
          "unit": "kg",
          "fetched_at": "2026-03-11T12:00:00Z"
        }
      ],
      "status": "confirmed",
      "note": "Подтверждён одинаковый вес на detalneftehim.ru и oporytrub.ru",
      "updated_at": "2026-03-11T12:00:00Z"
    }
  }
  ```

  Поля:

  - `name` — исходное обозначение опоры (ключ записи).
  - `sources` — список источников с доменом, URL, весом и временем получения.
  - `status` — агрегированный статус:
    - `confirmed` — несколько независимых источников дали одинаковый вес;
    - `single_source` — найден только один надёжный источник;
    - `conflict` — источники дают существенно разные значения;
    - `not_found` — ни один из доверенных источников не дал веса.
  - `note` — человекочитаемое примечание.
  - `updated_at` — время последнего обновления записи.

### Публичное API модуля

Публичные функции в `ves/resolver.py`:

- `resolve_position(name: str) -> ResolvedPosition`
  Принимает обозначение опоры и возвращает структуру с весами по доменам, статусом и примечанием.

- `generate_pdf_zmk_ves_values(positions: list[str]) -> list[list[str]]`
  Строит двумерный массив значений для листа Google Sheets `PDF_ZMK_VES`.

### Лист Google Sheets `PDF_ZMK_VES`

- Имя листа: `PDF_ZMK_VES`.
- Колонки:
  - `A` — исходная позиция;
  - `B, C, D, ...` — по столбцу на каждый домен-источник;
  - последняя колонка — `Примечание`.

### Поток данных

1. CLI читает входной список позиций.
2. Для каждой позиции вызывает `ves.resolver.resolve_position`.
3. Резолвер проверяет кэш `ves/weights_db.json`, при необходимости скрейпит сайты.
4. `generate_pdf_zmk_ves_values` формирует массив для `PDF_ZMK_VES`.
5. CLI очищает лист и записывает значения.
