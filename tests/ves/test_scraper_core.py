from __future__ import annotations

from pathlib import Path

import pytest

from ves import scraper


def test_normalize_search_key_variants() -> None:
    assert scraper._normalize_search_key("57-КХ-А11") == "57-КХ-А11"
    assert (
        scraper._normalize_search_key(
            "Опора 57 КХ-А11 ст.12Х18Н10Т ОСТ 36-146-88"
        )
        == "57-КХ-А11"
    )
    assert (
        scraper._normalize_search_key("Опора 18 ТХ-АС10 ст.12Х18Н10Т ОСТ 36-146-88")
        == "18-ТХ-АС10"
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Масса опоры = 2,8 кг", 2.8),
        ("Вес 3.5 кг", 3.5),
        ("масса 10,25 кг", 10.25),
        ("нет числа", None),
    ],
)
def test_extract_weight_by_label(text: str, expected: float | None) -> None:
    assert scraper._extract_weight_by_label(text) == expected


def test_build_search_context_basic() -> None:
    ctx = scraper._build_search_context(
        "Опора 57 КХ-А11 ст.12Х18Н10Т ОСТ 36-146-88"
    )
    assert ctx.orig.startswith("Опора 57")
    assert ctx.norm_key == "57-КХ-А11"
    assert ctx.diameter == "57"
    assert ctx.type_code in {"КХ", "КП", "ХБ", "ТО", "ТХ", "ТР", "ТП", "ВП", "УП", "ШП", "КН"}
    assert ctx.exec_code.startswith("А")
    assert "ОСТ 36-146-88" in ctx.ost_gost
    assert "Опора" not in ctx.no_opora


def _load_fixture(relative: str) -> str:
    base = Path(__file__).parent.parent / "fixtures" / "ves"
    return (base / relative).read_text(encoding="utf-8")


def test_parse_weight_from_awstroy_prefers_table() -> None:
    html = _load_fixture("awstroy/product_57_kh_a11.html")
    weight = scraper._parse_weight_from_awstroy(html, None)
    assert weight == pytest.approx(2.5)

