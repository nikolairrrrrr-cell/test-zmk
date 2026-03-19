from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.use_cases.pdf_zmk2 import run_pdf_zmk2_full


def _pdf_zmk2_item(det: str, t: str, section: str) -> dict:
    return {
        "elem": "",
        "det": det,
        "t": t,
        "n": "",
        "section": section,
        "length": "",
        "mass_sht": "1",
        "mass_total": "1",
        "note": "",
    }


def test_run_pdf_zmk2_full_merges_two_json_payloads(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    input_dir = tmp_path / "input"
    input_dir.mkdir()

    (input_dir / "a.json").write_text(
        json.dumps(
            {
                "drawing_name": "A",
                "items": [_pdf_zmk2_item("8", "4", "Шайба A")],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (input_dir / "b.json").write_text(
        json.dumps(
            {
                "drawing_name": "B",
                "items": [_pdf_zmk2_item("7", "8", "Гайка B")],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_pdf_zmk2_full(
        input_dir=input_dir,
        settings=Settings.from_env(),
        dry_run=True,
        workers=4,
    )
    assert result.status == "ok"
    assert result.total_files == 2
    assert result.processed_files == 2
    assert result.rows_count == 2
    assert result.sheet_written is False
