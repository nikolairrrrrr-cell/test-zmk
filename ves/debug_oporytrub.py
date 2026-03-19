#!/usr/bin/env python3
"""
Дебаг скрейпера opora-trub.ru для конкретных позиций.
Запуск: python -m ves.debug_oporytrub
"""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ves.scraper import (
    _build_search_context,
    _parse_weight_from_oporytrub,
    _rate_limited_get,
)

DEBUG_POSITIONS = [
    "Опора Дн 630 01 ОСТ 24.125.158-01 скользящая",
    "Опора Дн 720 01 ОСТ 24.125.158-01 скользящая",
    "Опора 32 ХБ-А 12Х18Н10Т ОСТ 36-146-88",
]


def main() -> None:
    catalog_url = "https://www.opora-trub.ru/produkciya/opory-truboprovodov/"

    for name in DEBUG_POSITIONS:
        print("\n" + "=" * 70)
        print("ПОЗИЦИЯ:", name)
        print("=" * 70)

        ctx = _build_search_context(name)
        print(
            "SearchContext: diameter=%r exec_code=%r type_code=%r ost_gost=%r norm_key=%r"
            % (ctx.diameter, ctx.exec_code, ctx.type_code, ctx.ost_gost, ctx.norm_key)
        )

        # Каталог
        catalog_html = _rate_limited_get("opora-trub.ru", catalog_url)
        if not catalog_html:
            print("ОШИБКА: не удалось загрузить каталог")
            continue

        soup = BeautifulSoup(catalog_html, "html.parser")
        best_href = None
        best_score = 0
        best_text = ""

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            haystack = f"{text} {href}"

            score = 0
            if "/produkciya/opory-truboprovodov/" in href:
                score += 2
            if ctx.ost_gost:
                norm_ost = ctx.ost_gost.replace(" ", "")
                if norm_ost and norm_ost in haystack.replace(" ", ""):
                    score += 5
            if ctx.type_code and ctx.type_code in haystack:
                score += 3
            if "опора" in text.lower() or "опоры" in text.lower():
                score += 1
            if ctx.t6_code:
                if "opory-t6" in href:
                    score += 10
                if "4-903-10" in haystack or "4.903-10" in haystack:
                    score += 8
                if "opory-t6" in href and ("4-903-10" in href or "4.903-10" in href):
                    score += 40

            if score > best_score:
                best_score = score
                best_href = href
                best_text = text[:80]

        print("Каталог: best_score=%s best_href=%r text=%r" % (best_score, best_href, best_text))

        if not best_href or best_score <= 0:
            print("По каталогу подходящая ссылка не найдена.")
            continue

        detail_url = urljoin(catalog_url, best_href)
        print("Страница типа: %s" % detail_url)

        detail_html = _rate_limited_get("opora-trub.ru", detail_url)
        if not detail_html:
            print("ОШИБКА: не удалось загрузить страницу типа")
            continue

        # Показать структуру таблиц на странице
        doc = BeautifulSoup(detail_html, "html.parser")
        for i, table in enumerate(doc.find_all("table")):
            headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
            if not headers:
                first = table.find("tr")
                if first:
                    headers = [td.get_text(" ", strip=True) for td in first.find_all("td")]
            if not headers:
                continue
            print("  Таблица %d: заголовки %s" % (i, headers[:6]))
            # первые 3 строки данных
            for j, tr in enumerate(table.find_all("tr")):
                if j == 0 and headers and "Исполнение" not in str(headers) and "Теоретическая" not in str(headers):
                    continue
                cells = tr.find_all("td")
                if len(cells) < 2:
                    continue
                row_texts = [c.get_text(" ", strip=True) for c in cells]
                print("    Строка: %s" % row_texts[:5])
                if j >= 4:
                    break

        weight = _parse_weight_from_oporytrub(detail_html, name, ctx=ctx)
        print("Результат _parse_weight_from_oporytrub: %s" % weight)


if __name__ == "__main__":
    main()
