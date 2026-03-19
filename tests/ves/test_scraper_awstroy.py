from pathlib import Path

import pytest

from ves import scraper


def _load_fixture(relative: str) -> str:
    base = Path(__file__).parent.parent / "fixtures" / "ves"
    return (base / relative).read_text(encoding="utf-8")


def test_scrape_awstroy_via_search_and_product(monkeypatch: pytest.MonkeyPatch) -> None:
    search_html = _load_fixture("awstroy/search_57_kh_a11.html")
    product_html = _load_fixture("awstroy/product_57_kh_a11.html")

    def fake_get(domain: str, url: str):
        if domain != "awstroy.ru":
            return None
        if "/search/?" in url:
            return search_html
        if "/product/" in url:
            return product_html
        return None

    monkeypatch.setattr(scraper, "_rate_limited_get", fake_get)

    name = "Опора 57 КХ-А11 ст.12Х18Н10Т ОСТ 36-146-88"
    results = scraper._scrape_awstroy(name)

    assert len(results) == 1
    r = results[0]
    assert r.domain == "awstroy.ru"
    assert "/product/" in r.url
    assert r.weight == pytest.approx(2.5)

