from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.use_cases.pdf_zmk import run_pdf_zmk_full


def test_run_pdf_zmk_full_with_json_payloads(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    rec_dir = tmp_path / "data" / "recognition"
    rec_dir.mkdir(parents=True, exist_ok=True)

    for idx in range(4):
        payload = input_dir / f"doc_{idx}.json"
        payload.write_text(
            json.dumps(
                {
                    "drawing_name": f"DOC-{idx}",
                    "items": [
                        {
                            "poz": "1",
                            "designation": "10x10x1",
                            "name": "Основание",
                            "qty": "1",
                            "weight": "0,1",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    result = run_pdf_zmk_full(
        input_dir=input_dir,
        settings=Settings.from_env(),
        dry_run=True,
        workers=4,
    )
    assert result.status == "ok"
    assert result.total_files == 4
    assert result.processed_files == 4
    assert result.skipped_files == 0
    assert result.rows_count == 4
