# Contract: `ves` tool

## Purpose
Resolve support-position weights using scraper sources, cache results in local DB, optionally write table to Google Sheets `Масса`.

## CLI
`python -m app.cli ves run --positions <path> [--online] [--force-refresh] [--sheet-write] [--dry-run] [--output-json <path>]`

## Inputs
- `--positions` (required): path to text file with one position per line.
- `--online` (flag, default `False`): allow scraping when cache is missing/stale.
- `--force-refresh` (flag): bypass cache and re-scrape all positions.
- `--sheet-write` (optional): write to Google Sheets.
- `--dry-run` (optional): process data but do not write to Google Sheets.
- `--output-json` (optional): write execution report JSON.

## Data sources and storage
- Active scraping sources are defined in `ves/scraper.py`.
- Persistent cache DB: `ves/weights_db.json` (or custom path from CLI/env when configured).

## Outputs
- 2D table values from `ves.resolver.generate_pdf_zmk_ves_values`.
- Optional write to Google Sheet `Масса`.
- Optional JSON report:
  - `tool`, `status`, `positions_count`, `rows_count`, `online`, `force_refresh`, `sheet_written`.

## Side effects
- Updates local cache DB when online resolution is used.
- Writes `ves/debug_last_run.json`.
- If `--sheet-write` and not `--dry-run`: clears and updates `Масса!A:Z`.

## Exit codes
- `0`: success.
- `2`: invalid input contract/arguments.
- `3`: scraper/network failure.
- `4`: Google auth/sheets failure.
- `5`: unexpected runtime error.
