from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app import cli


def test_cli_pdf_zmk_full_dry_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    image = input_dir / "doc.jpg"
    Image.new("RGB", (1000, 700), color="white").save(image)

    rec = tmp_path / "data" / "recognition"
    rec.mkdir(parents=True, exist_ok=True)
    (rec / "doc.json").write_text(
        json.dumps(
            {
                "drawing_name": "doc",
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
    code = cli.main(
        [
            "pdf-zmk",
            "full",
            "--input-dir",
            str(input_dir),
            "--dry-run",
            "--workers",
            "4",
        ]
    )
    assert code == 0


def test_cli_pdf_zmk_full_agent_read_required(tmp_path: Path, monkeypatch) -> None:
    """When image has no payload, CLI must exit with AGENT_READ_REQUIRED (exit 3)."""
    monkeypatch.chdir(tmp_path)

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    image = input_dir / "drawing.jpg"
    Image.new("RGB", (1000, 700), color="white").save(image)

    code = cli.main(
        ["pdf-zmk", "full", "--input-dir", str(input_dir), "--dry-run"]
    )
    assert code == cli.EXIT_AGENT_READ


def test_cli_ves_run_dry_mode(tmp_path: Path) -> None:
    positions = tmp_path / "positions.txt"
    positions.write_text("57-КХ-А11\n", encoding="utf-8")
    db_path = tmp_path / "weights.json"
    code = cli.main(
        [
            "ves",
            "run",
            "--positions",
            str(positions),
            "--dry-run",
            "--db-path",
            str(db_path),
        ]
    )
    assert code == 0
