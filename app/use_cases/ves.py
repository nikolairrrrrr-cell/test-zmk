from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import Settings
from app.sheets_gateway import SheetsGateway
from ves import resolver


@dataclass
class VesResult:
    tool: str
    status: str
    positions_count: int
    rows_count: int
    online: bool
    force_refresh: bool
    sheet_written: bool


def run_ves(
    positions_path: Path,
    settings: Settings,
    sheet_write: bool = False,
    dry_run: bool = False,
    online: bool = False,
    force_refresh: bool = False,
    output_json: Path | None = None,
    db_path: Path | None = None,
) -> VesResult:
    if db_path is not None:
        resolver.DB_PATH = db_path
        resolver.DEBUG_LAST_RUN_PATH = db_path.with_name("debug_last_run.json")

    positions = resolver.load_positions(positions_path)
    values = resolver.generate_pdf_zmk_ves_values(
        positions, online=online, force_refresh=force_refresh
    )

    sheet_written = False
    if sheet_write and not dry_run:
        SheetsGateway(settings).write_values(settings.sheet_pdf_zmk_ves, values)
        sheet_written = True

    result = VesResult(
        tool="ves",
        status="ok",
        positions_count=len(positions),
        rows_count=max(0, len(values) - 1),
        online=online,
        force_refresh=force_refresh,
        sheet_written=sheet_written,
    )
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result

