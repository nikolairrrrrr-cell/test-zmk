# Contract: `pdf-zmk` tool

## Purpose
Process drawings/images of type `PDF_ZMK`, normalize extracted rows, write data to Google Sheet tab **`База2`** (override with env `GOOGLE_SHEET_PDF_ZMK`).

## CLI
```
python -m app.cli pdf-zmk full --input-dir <dir> [--sheet-write] [--dry-run] [--workers <n>] [--output-json <path>]
```

## Strict pipeline (4 phases)

The pipeline is **mandatory and sequential**. No phase can be skipped.

### Phase 1 — CROP + UPSCALE
For every image in `--input-dir`:
1. Detect table region (adaptive bbox or static fallback).
2. Crop the table area.
3. Upscale crop ×4.
4. Save to `data/recognition/<slug>.table_x4.jpg`.

### Phase 2 — AGENT READ (hard gate)
The CLI checks if every crop has a corresponding `data/recognition/<slug>.json` with non-empty `items`.

If **any** payload is missing or empty:
- The CLI raises `AgentReadRequired` (exit code 3).
- It prints every pending crop + expected JSON path.
- The **Cursor agent must**:
  1. Open each crop image (`ReadFile`).
  2. Read the specification table from the image.
  3. Extract every row: `poz`, `designation`, `name`, `qty`, `weight`.
  4. Write `data/recognition/<slug>.json`.

No local OCR. No external LLM API. The agent does this.

### Phase 3 — WRITE JSON
The agent writes each payload in this schema:
```json
{
  "drawing_name": "530-12",
  "items": [
    {"poz": "1", "designation": "490x275x8", "name": "Основание", "qty": "1", "weight": "8,41"}
  ]
}
```
- `items` must be non-empty. Empty payloads are **forbidden**.
- If extraction fails, the agent must report the error — never write an empty list.

### Phase 4 — NORMALIZE + SHEETS
The agent re-runs the same command. Now all payloads exist, so:
1. Load all `<slug>.json` files.
2. Normalize each row via `pdf_zmk_normalizer`.
3. Merge all drawings into a single values table.
4. Write to Google Sheet tab `База2` (if `--sheet-write`).

If any payload still has empty `items`, the run **fails** (fail-fast).

## Agent workflow (exact sequence)

```
1. agent runs:  python -m app.cli pdf-zmk full --input-dir new --dry-run
2. CLI does crop+upscale for all files
3. CLI raises AgentReadRequired with list of crops needing reading
4. agent reads each crop image (ReadFile tool)
5. agent writes each <slug>.json (Write tool)
6. agent runs:  python -m app.cli pdf-zmk full --input-dir new --sheet-write
7. CLI loads all payloads, normalizes, writes to Google Sheet
8. done
```

If all payloads already exist from a previous run, step 1 goes straight to Phase 4 (no AgentReadRequired).

## Exit codes
- `0`: success.
- `2`: invalid input/arguments.
- `3`: `AGENT_READ_REQUIRED` — crops exist but payloads are missing.
- `5`: unexpected runtime error.

## Rules
- No local OCR. Ever.
- No external LLM API keys.
- No UNRESOLVED stubs.
- No silent skips.
- No empty `items`.
- The agent reads crops. Always.
