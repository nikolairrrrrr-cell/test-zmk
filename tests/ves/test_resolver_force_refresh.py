from __future__ import annotations

import json
from pathlib import Path

import pytest

from ves import resolver
from ves.scraper import SourceRecord


def test_force_refresh_ignores_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "weights_db.json"
    name = "Опора 57 КХ-А11"

    db_path.write_text(
        json.dumps(
            {
                name: {
                    "name": name,
                    "weights_by_domain": {"opora-trub.ru": 1.0},
                    "status": "single_source",
                    "note": "cached",
                    "updated_at": "2099-01-01T00:00:00+00:00",
                    "sources": [
                        {
                            "domain": "opora-trub.ru",
                            "url": "https://cached",
                            "weight": 1.0,
                            "unit": "kg",
                            "fetched_at": "2099-01-01T00:00:00+00:00",
                        }
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(resolver, "DB_PATH", db_path)

    calls = {"count": 0}

    def fake_fetch(_name: str) -> list[SourceRecord]:
        calls["count"] += 1
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

    resolved = resolver.resolve_position(name, force_refresh=True, online=True)
    assert calls["count"] == 1
    assert resolved.weights_by_domain["opora-trub.ru"] == 2.5

