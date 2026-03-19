from __future__ import annotations

from urllib.parse import quote_plus

import pytest
import requests
from bs4 import BeautifulSoup  # type: ignore[import]

from ves import scraper


def test_awstroy_debug_219_hb_a() -> None:
    """
    Отладочный тест для понимания, что происходит при попытке
    найти массу на awstroy.ru для позиции «219-ХБ-А».

    Тест ИДЁТ В ИНТЕРНЕТ, поэтому помечен как skip и должен
    запускаться только вручную при необходимости.
    """

    name = "219-ХБ-А"
    ctx = scraper._build_search_context(name)  # type: ignore[attr-defined]

    # Собираем запросы так же, как это делает _scrape_awstroy
    queries: list[str] = []

    # Канонический запрос: "Опора 219 ХБ-А ОСТ 36-146-88" (если получится собрать)
    main_parts: list[str] = []
    if "Опора" in ctx.orig:
        main_parts.append("Опора")
    if ctx.diameter:
        main_parts.append(ctx.diameter)

    model = ""
    if ctx.type_code and ctx.exec_code:
        model = f"{ctx.type_code}-{ctx.exec_code}"
    elif ctx.type_code:
        model = ctx.type_code
    elif ctx.exec_code:
        model = ctx.exec_code
    if model:
        main_parts.append(model)

    if ctx.ost_gost:
        main_parts.append(ctx.ost_gost)

    canonical_query = " ".join(main_parts).strip()
    if canonical_query:
        queries.append(canonical_query)

    # Дополнительные варианты
    if ctx.clean_for_search and ctx.clean_for_search not in queries:
        queries.append(ctx.clean_for_search)
    if ctx.no_opora and ctx.no_opora not in queries:
        queries.append(ctx.no_opora)
    if ctx.norm_key and ctx.norm_key not in queries:
        queries.append(ctx.norm_key)
    if ctx.ost_gost and ctx.diameter:
        combo = f"{ctx.ost_gost} {ctx.diameter}"
        if combo not in queries:
            queries.append(combo)

    print(f"DEBUG awstroy queries for '{name}':")
    for q in queries:
        url = f"https://awstroy.ru/search/?query={quote_plus(q)}"
        print(f"\n=== QUERY: {q!r}")
        print(f"URL: {url}")

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": scraper.USER_AGENT},  # type: ignore[attr-defined]
                timeout=15,
            )
        except Exception as exc:  # pragma: no cover - чисто отладка
            print(f"REQUEST ERROR: {exc!r}")
            continue

        print(f"status_code: {resp.status_code}")
        print(f"final_url: {resp.url}")
        print(f"content_length: {len(resp.content)} bytes")

        if resp.status_code != 200:
            continue

        html = resp.text

        # Пробуем тем же парсером, что и в проде
        weight = scraper._parse_weight_from_awstroy(html, ctx)  # type: ignore[attr-defined]
        print(f"parsed_weight_by_parser: {weight!r}")

        # И параллельно смотрим глазами в HTML, есть ли блок характеристики "weight"
        soup = BeautifulSoup(html, "html.parser")
        feature = soup.find(
            "div",
            class_="product-feature",
            attrs={"data-feature-code": "weight"},
        )
        if feature is None:
            print("HTML: NO product-feature[data-feature-code='weight'] on search page")
        else:
            value_div = feature.find(class_="product-feature__value")
            text = value_div.get_text(" ", strip=True) if value_div else ""
            print(f"HTML: weight block on search page => {text!r}")

    # Никаких жёстких ассертов — тест служит для интерактивной диагностики.
    assert True

