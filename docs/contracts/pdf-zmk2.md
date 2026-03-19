# Contract: `pdf-zmk2` tool

## Purpose
Process drawings/images of type `PDF_ZMK2`, normalize extracted rows, optionally write data to Google Sheets `PDF_ZMK2`.

## CLI
`python -m app.cli pdf-zmk2 run --input <path> [--sheet-write] [--dry-run] [--output-json <path>]`

## Inputs
- `--input` (required): path to recognition payload (JSON) or source asset path.
- `--sheet-write` (optional): write to Google Sheets.
- `--dry-run` (optional): process data but do not write to Google Sheets.
- `--output-json` (optional): write execution report JSON.

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

## Outputs
- Normalized rows in memory (2D list, row schema for `PDF_ZMK2`).
- Optional write to Google Sheet `PDF_ZMK2`.
- Optional JSON report:
  - `tool`, `status`, `rows_count`, `sheet_written`, `input_path`.

## Side effects
- If `--sheet-write` and not `--dry-run`: clears and updates `PDF_ZMK2!A:Z`.
- If `--output-json`: writes report file to disk.

## Exit codes
- `0`: success.
- `2`: invalid input contract/arguments.
- `3`: recognizer/network failure.
- `4`: Google auth/sheets failure.
- `5`: unexpected runtime error.
