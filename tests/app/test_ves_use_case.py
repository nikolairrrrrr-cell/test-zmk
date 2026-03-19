from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.use_cases.ves import run_ves
from ves import resolver
from ves.scraper import SourceRecord


def test_run_ves_force_refresh_with_temp_db(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    positions = tmp_path / "positions.txt"
    positions.write_text("Опора 57 КХ-А11\n", encoding="utf-8")
    db_path = tmp_path / "weights.json"

    def fake_fetch(_name: str) -> list[SourceRecord]:
        return [
            SourceRecord(
                domain="opora-trub.ru",
                url="https://fresh",
                weight=2.5,
                unit="kg",
                fetched_at="2026-01-01T00:00:00+00:00",
            )
        ]

    monkeypatch.setattr(resolver, "fetch_sources_for_position", fake_fetch)

    result = run_ves(
        positions_path=positions,
        settings=Settings.from_env(),
        online=True,
        force_refresh=True,
        dry_run=True,
        db_path=db_path,
    )
    assert result.status == "ok"
    assert result.positions_count == 1
    assert db_path.exists()

