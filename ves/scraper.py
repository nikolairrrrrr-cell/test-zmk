from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup  # type: ignore[import]


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)

# Минимальная задержка между запросами к одному домену (секунды)
_RATE_LIMIT_SECONDS = 1.0
_last_request_time: Dict[str, float] = {}


@dataclass
class ScrapeResult:
    domain: str
    url: str
    weight: Optional[float]


@dataclass
class SourceRecord:
    domain: str
    url: str
    weight: Optional[float]
    unit: str = "kg"
    fetched_at: str = ""


@dataclass
class SearchContext:
    """
    Нормализованный контекст имени опоры для поиска по сайтам.

    Собираем все часто используемые признаки один раз и переиспользуем
    в скрейперах разных доменов.
    """

    orig: str
    norm_key: str
    diameter: str
    type_code: str
    exec_code: str
    ost_gost: str
    t6_code: str
    clean_for_search: str
    no_opora: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rate_limited_get(domain: str, url: str, max_attempts: int = 3) -> Optional[str]:
    """
    Обёртка над requests.get с rate limiting по домену и повтором при сбое.
    При таймауте/сетевой ошибке повторяет запрос до max_attempts раз с паузой 2 с.
    """
    import time

    for attempt in range(max_attempts):
        last = _last_request_time.get(domain)
        now = time.time()
        if last is not None and now - last < _RATE_LIMIT_SECONDS:
            sleep(_RATE_LIMIT_SECONDS - (now - last))

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
        except requests.RequestException:
            if attempt < max_attempts - 1:
                sleep(2)
                continue
            return None

        _last_request_time[domain] = time.time()
        if resp.status_code != 200:
            if attempt < max_attempts - 1:
                sleep(2)
                continue
            return None
        return resp.text
    return None


def _normalize_search_key(name: str) -> str:
    """
    Нормализует исходное имя опоры до краткого ключа для поиска по сайтам.

    Примеры:
    - "57-КХ-А11" -> "57-КХ-А11"
    - "Опора 57 КХ-А11 ст.12Х18Н10Т ОСТ 36-146-88" -> "57-КХ-А11"
    - "Опора 18 ТХ-АС10 ст.12Х18Н10Т ОСТ 36-146-88" -> "18-ТХ-АС10"
    """
    import re

    s = name.strip()

    # Убираем префикс "Опора"
    if s.startswith("Опора "):
        s = s[len("Опора ") :].strip()

    # Отрезаем всё после маркеров стали/стандарта
    for marker in (" ст.", " ст ", " ОСТ", " OST", " ГОСТ"):
        idx = s.find(marker)
        if idx != -1:
            s = s[:idx].strip()
            break

    # Схлопываем пробелы
    s = re.sub(r"\s+", " ", s)

    # Если обозначение уже близко к краткому формату, оставляем его,
    # но нормализуем частый вариант "57 КХ-А11" -> "57-КХ-А11".
    if "-" in s and any(t in s for t in ("КХ", "КП", "ХБ", "ТХ", "ТР", "ТО")):
        parts = s.split(" ")
        if len(parts) == 2 and parts[0].isdigit():
            return f"{parts[0]}-{parts[1]}"
        return s

    # Попробуем собрать ключ в формате "<диаметр>-<тип>-<исполнение>"
    parts = s.split(" ")
    if len(parts) >= 2 and parts[0].isdigit():
        diameter = parts[0]
        rest = parts[1:]
        key = diameter + "-" + "-".join(rest)
        return key

    return s


def _build_search_context(name: str) -> SearchContext:
    """
    Строит SearchContext из произвольной строки с именем опоры.
    """
    import re

    orig = name.strip()
    norm_key = _normalize_search_key(name)

    m_d = re.search(r"\b(\d+)\b", norm_key)
    diameter = m_d.group(1) if m_d else ""

    m_t = re.search(r"\b(ТХ|КХ|КП|ХБ|ТО|ТР|ТП|ВП|УП|ШП|КН)\b", norm_key)
    type_code = m_t.group(1) if m_t else ""

    # Исполнение:
    # - для ОСТ 36-146-88: если есть пара "тип-исполнение" (ХБ-А, ТХ-АС10), берём исполнение из неё,
    #   иначе конец norm_key может дать марку стали (12Х18Н10Т → "Т") вместо исполнения;
    # - для ОСТ 24.125.158-01 — цифровой индекс ("01", "02", ...).
    exec_code = ""
    if type_code:
        m_exec = re.search(
            r"\b" + re.escape(type_code) + r"-([А-ЯA-Z]\d*)\b",
            norm_key,
        )
        if m_exec:
            exec_code = m_exec.group(1)
    if not exec_code:
        m_e = re.search(r"([А-ЯA-Z]{1,3}\d*)$", norm_key)
        exec_code = m_e.group(1) if m_e else ""
    if not exec_code:
        m_idx = re.search(r"\b(\d{1,3})\b$", norm_key)
        exec_code = m_idx.group(1) if m_idx else ""

    ost_match = re.search(r"(ОСТ\s*\d[\d\.\-]*|\bГОСТ\s*\d[\d\.\-]*)", orig)
    ost_gost = ost_match.group(1) if ost_match else ""

    m_t6 = re.search(r"(Т6\.\d+)", orig)
    t6_code = m_t6.group(1) if m_t6 else ""

    clean_for_search = orig
    for marker in (" ст.", " ст ", " ОСТ", " OST", " ГОСТ"):
        idx = clean_for_search.find(marker)
        if idx != -1:
            clean_for_search = clean_for_search[:idx].strip()
            break

    no_opora = clean_for_search.replace("Опора ", "").strip()

    return SearchContext(
        orig=orig,
        norm_key=norm_key,
        diameter=diameter,
        type_code=type_code,
        exec_code=exec_code,
        ost_gost=ost_gost,
        t6_code=t6_code,
        clean_for_search=clean_for_search,
        no_opora=no_opora,
    )


def _extract_weight_by_label(text: str) -> Optional[float]:
    """
    Ищет шаблон вида 'Масса ... = 2,8 кг' в сплошном тексте.
    """
    import re

    # Ищем сначала по слову "Масса"
    m = re.search(r"Масса[^0-9]{0,40}(\d+(?:[.,]\d+)?)\s*кг", text)
    if not m:
        # fallback: любая конструкция "<число> кг"
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*кг", text)
    if not m:
        return None
    raw = m.group(1).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_weight_from_oporytrub(
    html: str, name: Optional[str] = None, ctx: Optional[SearchContext] = None
) -> Optional[float]:
    """
    Заготовка парсера для сайта опор труб.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Если есть контекст (имя или SearchContext) и на странице таблица с массами,
    # пробуем найти строку по диаметру/исполнению/серии.
    saw_mass_table = False
    if name is not None or ctx is not None:
        import re

        if ctx is not None:
            diameter = ctx.diameter
            exec_code = ctx.exec_code
            t6_code = ctx.t6_code
            orig = ctx.orig
        else:
            # fallback на старое поведение, если ctx не передан
            norm_key = _normalize_search_key(name or "")
            # Диаметр — первое встреченное целое число в нормализованном обозначении
            m_d = re.search(r"\b(\d+)\b", norm_key)
            diameter = m_d.group(1) if m_d else ""
            # Исполнение для ОСТ 36-146-88 (например, А11, АС11, ХБ-А)
            m_e = re.search(r"([А-ЯA-Z]{1,3}\d*)$", norm_key)
            exec_code = m_e.group(1) if m_e else ""
            # Обозначение типа для серии 4.903-10 (например, Т6.11)
            m_t6 = re.search(r"(Т6\.\d+)", name or "")
            t6_code = m_t6.group(1) if m_t6 else ""
            orig = name or ""

        # Частный, но важный случай: опоры по ОСТ 24.125.158-01.
        # Для них на opora-trub.ru есть таблицы вида:
        # Исполнение | Дн | Теоретическая масса | ...
        is_ost_24_125_158 = "24.125.158-01" in orig

        for table in soup.find_all("table"):
            header_cells = [
                th.get_text(" ", strip=True) for th in table.find_all("th")
            ]
            if not header_cells:
                first_row = table.find("tr")
                if first_row:
                    header_cells = [
                        td.get_text(" ", strip=True)
                        for td in first_row.find_all("td")
                    ]

            if not header_cells:
                continue

            # Специальная обработка таблиц для ОСТ 24.125.158-01:
            # если на странице есть таблица с колонками
            # "Исполнение" / "Наружный диаметр трубопровода Дн" / "Теоретическая масса",
            # привязываемся к ней напрямую.
            if is_ost_24_125_158 and diameter and exec_code:
                saw_mass_table = True
                for tr in table.find_all("tr"):
                    cells = tr.find_all("td")
                    if len(cells) < 3:
                        continue

                    exec_cell = cells[0].get_text(" ", strip=True)
                    d_cell = cells[1].get_text(" ", strip=True)
                    if exec_cell == exec_code and d_cell == diameter:
                        mass_text = cells[2].get_text(" ", strip=True)
                        mass = _extract_weight_by_label(mass_text)
                        if mass is not None:
                            return mass

                # Для таблиц по ОСТ 24.125.158-01 дальше по этому table идти не нужно.
                continue

            # Общий случай: ищем таблицы, где явно есть колонка "Теоретическая масса"
            if any("Теоретическая масса" in h for h in header_cells):
                saw_mass_table = True

                # Определяем индекс колонки массы, чтобы не гадать,
                # в каком именно столбце лежит значение.
                mass_col_idx: Optional[int] = None
                for idx, h in enumerate(header_cells):
                    if "Теоретическая масса" in h or "Масса" in h:
                        mass_col_idx = idx
                        break

                for tr in table.find_all("tr"):
                    cells = tr.find_all("td")
                    if len(cells) < 3:
                        continue

                    # Вариант 1: таблица по серии 4.903-10 с обозначением вида "Т6.11"
                    # Для таких таблиц дополнительно учитываем толщину стенки S,
                    # которую стараемся вытащить из исходного имени опоры.
                    if t6_code:
                        code_cell = cells[0].get_text(" ", strip=True)
                        if code_cell == t6_code:
                            # Попробуем сузить поиск по серии Т6: диаметр + толщина стенки.
                            # Примеры исходных имён:
                            # "Опора 530х8-II-Т6.11 с.4.903-10 вып.4"
                            desired_dn: Optional[str] = None
                            desired_s: Optional[str] = None
                            if ctx is not None:
                                # Ищем паттерн "<dn>х<s>" в оригинальном имени.
                                m_ds = re.search(
                                    r"(\\d+)\\s*[xх]\\s*(\\d+)", ctx.orig
                                )
                                if m_ds:
                                    desired_dn = m_ds.group(1)
                                    desired_s = m_ds.group(2)

                            dn_cell = cells[1].get_text(" ", strip=True)
                            s_cell = (
                                cells[3].get_text(" ", strip=True)
                                if len(cells) > 3
                                else ""
                            )

                            dn_ok = True
                            s_ok = True
                            if desired_dn:
                                dn_ok = dn_cell == desired_dn
                            if desired_s:
                                # S ячейка может содержать текст вроде "8" или "8 мм."
                                s_token = s_cell.split()[0]
                                s_ok = s_token == desired_s

                            if dn_ok and s_ok:
                                idx = (
                                    mass_col_idx
                                    if mass_col_idx is not None
                                    else len(cells) - 1
                                )
                                if 0 <= idx < len(cells):
                                    mass_text = cells[idx].get_text(
                                        " ", strip=True
                                    )
                                    mass = _extract_weight_by_label(mass_text)
                                    if mass is not None:
                                        return mass

                    # Вариант 2: таблица с явным диаметром и исполнением
                    # (ОСТ 36-146-88, ОСТ 24.125.158-01 и подобные).
                    if diameter and exec_code:
                        # Считаем строку совпавшей, если в ней
                        # одновременно встречаются наш диаметр и исполнение,
                        # независимо от порядка колонок.
                        row_texts = [c.get_text(" ", strip=True) for c in cells]

                        has_diameter = any(t == diameter for t in row_texts)
                        exec_norm = exec_code.replace(" ", "")
                        has_exec = any(
                            exec_norm and exec_norm in t.replace(" ", "")
                            for t in row_texts
                        )

                        if has_diameter and has_exec:
                            idx = mass_col_idx if mass_col_idx is not None else len(cells) - 1
                            if 0 <= idx < len(cells):
                                mass_text = cells[idx].get_text(" ", strip=True)
                                mass = _extract_weight_by_label(mass_text)
                                if mass is not None:
                                    return mass

                    # Вариант 3: только диаметр (для таблиц, где нет явного "исполнения").
                    if diameter and not exec_code:
                        d = cells[0].get_text(" ", strip=True)
                        if d == diameter:
                            idx = mass_col_idx if mass_col_idx is not None else len(cells) - 1
                            if 0 <= idx < len(cells):
                                mass_text = cells[idx].get_text(" ", strip=True)
                                mass = _extract_weight_by_label(mass_text)
                                if mass is not None:
                                    return mass

        # Если мы видели таблицу с "Теоретической массой", но не нашли подходящую строку
        # по диаметру/исполнению/серии, лучше вернуть None, чем брать первое "X кг"
        # из текста страницы (это и был твой кейс с 27.78).
        if saw_mass_table:
            return None

    # У многих страниц масса встречается в тексте; пытаемся найти число с 'кг'
    text = soup.get_text(" ", strip=True)
    if not text:
        return None

    return _extract_weight_by_label(text)


def _parse_weight_from_awstroy(html: str, ctx: Optional[SearchContext] = None) -> Optional[float]:
    """
    Парсер массы для awstroy.ru.

    Стратегия:
    1. Сначала пытаемся вытащить вес из блока
       `<div class="product-feature" data-feature-code="weight">`.
    2. Если не нашли — ищем по всему тексту страницы конструкцию "<число> кг".
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Приоритетный вариант: специальный блок характеристики с кодом "weight"
    feature_div = soup.find(
        "div",
        class_="product-feature",
        attrs={"data-feature-code": "weight"},
    )
    if feature_div is not None:
        value_div = feature_div.find(class_="product-feature__value")
        if value_div is not None:
            text = value_div.get_text(" ", strip=True)
            weight = _extract_weight_by_label(text)
            if weight is not None:
                return weight

    # 2. Фоллбэк: любой "<число> кг" по всей странице
    full_text = soup.get_text(" ", strip=True)
    if not full_text:
        return None
    return _extract_weight_by_label(full_text)


def _score_awstroy_candidate(text: str, href: str, ctx: SearchContext) -> int:
    """
    Чем выше score, тем релевантнее ссылка нашей опоре.
    """
    score = 0
    haystack = f"{text} {href}"

    # Бонус за «похожесть» на карточку товара
    if "/catalog/" in href or "/product/" in href:
        score += 2

    # Текстовые совпадения
    if "Опора" in text or "опора" in text:
        score += 1
    if ctx.norm_key and ctx.norm_key in haystack:
        score += 4
    if ctx.clean_for_search and ctx.clean_for_search in text:
        score += 3
    if ctx.no_opora and ctx.no_opora in text:
        score += 2
    if ctx.diameter and ctx.diameter in haystack:
        score += 1
    if ctx.type_code and ctx.type_code in haystack:
        score += 1
    if ctx.exec_code and ctx.exec_code in haystack:
        score += 1
    if ctx.ost_gost and ctx.ost_gost in haystack:
        score += 2

    # Усиление для опор по сериям (4.903-10 и т.п.) и кода Т6.xx:
    # если в запросе есть код Т6.xx и/или серия, сильно предпочитаем
    # ссылки, в которых они встречаются.
    if ctx.t6_code and ctx.t6_code in haystack:
        score += 4

    import re

    series_match = re.search(r"(\d\.\d{3}-\d{2})", ctx.orig)
    series_code = series_match.group(1) if series_match else ""
    if series_code and series_code in haystack:
        score += 6

    # Если в исходном запросе явно указан стандарт (ОСТ/ГОСТ),
    # не допускаем карточки с другим или отсутствующим стандартом.
    # Это критично для кейсов вроде:
    #   - запрос:  «Опора Дн 720 02 ОСТ 24.125.158-01 ...»
    #   - карточка: «Опора Дн 720 02 ОСТ 108.275-47-80 ...»
    # Без этого фильтра awstroy ошибочно подсовывает вес с другой серии.
    if ctx.ost_gost:
        norm_ost = ctx.ost_gost.replace(" ", "")
        norm_hay = haystack.replace(" ", "")
        if norm_ost not in norm_hay:
            return 0

    # Аналогично, если есть явное исполнение, требуем его присутствия
    # в ссылке/тексте, чтобы не путать 02, 03 и т.п.
    if ctx.exec_code:
        exec_norm = ctx.exec_code.replace(" ", "")
        if exec_norm and exec_norm not in haystack.replace(" ", ""):
            return 0

    return score


def _scrape_oporytrub(name: str) -> List[ScrapeResult]:
    """
    Универсальный поиск массы опоры на сайте opora-trub.ru.

    Стратегия:
    1. Разбираем запрос (диаметр, тип, исполнение, стандарт) через SearchContext.
    2. Открываем каталог опор трубопроводов:
       https://www.opora-trub.ru/produkciya/opory-truboprovodov/
    3. Находим ссылку на нужный тип/стандарт (ТХ, КХ, ХБ и т.п. + ОСТ/ГОСТ).
    4. Переходим в карточку типа и ищем в таблице строку с нужным диаметром
       и исполнением, вытаскивая «Теоретическую массу» через
       `_parse_weight_from_oporytrub`.
    5. Если по каталогу найти не удалось — используем старый поисковый
       сценарий (?s=...) как безопасный фоллбек.
    """
    from urllib.parse import urljoin, quote_plus

    results: List[ScrapeResult] = []
    ctx = _build_search_context(name)

    # --- 1. Попытка через каталог опор трубопроводов ---
    catalog_url = "https://www.opora-trub.ru/produkciya/opory-truboprovodov/"
    catalog_html = _rate_limited_get("opora-trub.ru", catalog_url)
    if catalog_html:
        soup = BeautifulSoup(catalog_html, "html.parser")

        best_href: Optional[str] = None
        best_score = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            haystack = f"{text} {href}"

            score = 0

            # Ссылки на типы опор внутри каталога
            if "/produkciya/opory-truboprovodov/" in href:
                score += 2

            # Стандарт (ОСТ/ГОСТ) из запроса
            if ctx.ost_gost:
                norm_ost = ctx.ost_gost.replace(" ", "")
                if norm_ost and norm_ost in haystack.replace(" ", ""):
                    score += 5

            # Тип опоры (ТХ, КХ, ХБ, ...), если удалось вытащить
            if ctx.type_code and ctx.type_code in haystack:
                score += 3

            # Слово «Опора» в тексте
            if "опора" in text.lower() or "опоры" in text.lower():
                score += 1

            # Усиление для опор серии 4.903-10 типа Т6:
            # хотим максимально предпочитать страницу
            # opory-t6-nepodvizhnye-...-serii-4-903-10-vypusk-4.
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

        if best_href and best_score > 0:
            detail_url = urljoin(catalog_url, best_href)
            detail_html = _rate_limited_get("opora-trub.ru", detail_url)
            if detail_html:
                weight = _parse_weight_from_oporytrub(detail_html, name, ctx=ctx)
                results.append(
                    ScrapeResult(
                        domain="opora-trub.ru",
                        url=detail_url,
                        weight=weight,
                    )
                )
                if weight is not None:
                    return results

    # --- 2. Фоллбек: старый поиск по сайту (?s=...) на случай,
    # что нужный тип/стандарт не нашли в каталоге или таблица другая. ---
    # (Логика оставлена, чтобы не ломать другие стандарты/серии.)

    # Собираем варианты строк для поиска
    queries: List[str] = []
    if ctx.orig:
        queries.append(ctx.orig)
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
    if ctx.t6_code and ctx.t6_code not in queries:
        queries.append(ctx.t6_code)

    def _score_candidate(text: str, href: str) -> int:
        """
        Чем выше score, тем релевантнее ссылка нашей опоре.
        """
        score = 0
        haystack = f"{text} {href}"

        # Карточки продукции
        if "/produkciya/opory-truboprovodov/" in href:
            score += 3

        # Текстовые совпадения
        if "Опора" in text or "Опоры" in text:
            score += 1
        if ctx.norm_key and ctx.norm_key in haystack:
            score += 4
        if ctx.clean_for_search and ctx.clean_for_search in text:
            score += 3
        if ctx.no_opora and ctx.no_opora in text:
            score += 2

        # Параметры
        if ctx.diameter and ctx.diameter in haystack:
            score += 1
        if ctx.type_code and ctx.type_code in haystack:
            score += 1
        if ctx.exec_code and ctx.exec_code in haystack:
            score += 1
        if ctx.ost_gost and ctx.ost_gost in haystack:
            score += 2
        if "4.903-10" in haystack:
            score += 2
        if ctx.t6_code and ctx.t6_code in haystack:
            score += 3

        return score

    # Основной цикл по запросам
    for q in queries:
        search_url = f"https://www.opora-trub.ru/?s={quote_plus(q)}"
        html = _rate_limited_get("opora-trub.ru", search_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        best_url: Optional[str] = None
        best_score = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            s = _score_candidate(text, href)
            if s > best_score:
                best_score = s
                best_url = href

        # Если карточку не нашли – пробуем вытащить массу прямо со страницы поиска
        if not best_url or best_score <= 0:
            weight = _parse_weight_from_oporytrub(html, name, ctx=ctx)
            results.append(
                ScrapeResult(
                    domain="opora-trub.ru",
                    url=search_url,
                    weight=weight,
                )
            )
            if weight is not None:
                return results
            continue

        product_html = _rate_limited_get("opora-trub.ru", best_url)
        if not product_html:
            continue

        weight = _parse_weight_from_oporytrub(product_html, name, ctx=ctx)
        results.append(
            ScrapeResult(
                domain="opora-trub.ru",
                url=best_url,
                weight=weight,
            )
        )
        if weight is not None:
            return results

    return results


def _scrape_awstroy(name: str) -> List[ScrapeResult]:
    """
    Скрейпер для awstroy.ru, основанный ТОЛЬКО на поиске.

    Стратегия:
    1. Строим несколько поисковых строк (полное имя, без «Опора», без хвоста стали/ОСТ, нормализованный ключ).
    2. По каждой строке открываем `/search/?query=...` и среди ссылок на товары выбираем лучшую по сходству.
    3. Заходим в карточку и вытаскиваем вес через `_parse_weight_from_awstroy`.
    4. Если карточку не нашли, пробуем извлечь вес прямо со страницы поиска.
    """
    from urllib.parse import quote_plus

    results: List[ScrapeResult] = []

    ctx = _build_search_context(name)

    # Собираем варианты строк для поиска.
    # Главная идея: короткий, "человеческий" запрос без лишнего шмурдяка
    # типа марки стали, но с ключевыми частями (Опора, диаметр, модель, ОСТ/ГОСТ, серия).
    queries: List[str] = []

    # 1. Канонический запрос вида:
    #    "Опора 57 КХ-А11 ОСТ 36-146-88"
    main_parts: List[str] = []
    if "Опора" in ctx.orig:
        main_parts.append("Опора")
    if ctx.diameter:
        main_parts.append(ctx.diameter)

    # Модель: КХ-А11, ТХ-АС10 и т.п.
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

    # 2. Дополнительные варианты, чтобы не быть слишком жёсткими:
    #    - имя без хвоста стали/ОСТ
    #    - имя без "Опора"
    #    - краткий нормализованный ключ
    #    - связка "ОСТ/ГОСТ + диаметр"
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

    # 3. Дополнительные запросы для опор по сериям (4.903-10, 5.903-13 и т.п.).
    #    Например, из "Опора 530х8-II-Т6.11 с.4.903-10 вып.4" хотим получить
    #    запрос вида: "Опора Т6.11 530 Серия 4.903-10".
    import re

    series_match = re.search(r"(\d\.\d{3}-\d{2})", ctx.orig)
    series_code = series_match.group(1) if series_match else ""
    if series_code and ctx.t6_code and ctx.diameter:
        series_query_1 = f"Опора {ctx.t6_code} {ctx.diameter} Серия {series_code}"
        series_query_2 = f"Опора {ctx.diameter} {ctx.t6_code} Серия {series_code}"
        for sq in (series_query_1, series_query_2):
            if sq not in queries:
                queries.append(sq)

    # Перебираем запросы и пытаемся найти КАРТОЧКУ товара.
    # Вес ищем ТОЛЬКО внутри карточки, а не на странице поиска.
    for q in queries:
        search_url = f"https://awstroy.ru/search/?query={quote_plus(q)}"
        html = _rate_limited_get("awstroy.ru", search_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        target_url: Optional[str] = None
        best_score = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            score = _score_awstroy_candidate(text, href, ctx)
            if score > best_score:
                best_score = score
                target_url = href

        if not target_url or best_score <= 0:
            # По этому запросу ничего внятного не нашли – пробуем следующий.
            continue

        # Нормализуем ссылку на карточку до полного URL.
        if target_url.startswith("http://") or target_url.startswith("https://"):
            product_url = target_url
        else:
            # На awstroy ссылки обычно относительные вида "/catalog/..."
            product_url = f"https://awstroy.ru{target_url}"

        product_html = _rate_limited_get("awstroy.ru", product_url)
        if not product_html:
            continue

        weight = _parse_weight_from_awstroy(product_html, ctx)
        results.append(
            ScrapeResult(domain="awstroy.ru", url=product_url, weight=weight)
        )
        if weight is not None:
            return results

    return results

ALL_SOURCES = [
    # Основные активные источники веса:
    _scrape_oporytrub,
    _scrape_awstroy,
    # pkfdetal/prommashzavod можно вернуть в список позже,
    # когда будет подтверждено, что по ним стабильно находятся веса
]


def fetch_sources_for_position(name: str) -> List[SourceRecord]:
    """
    Вызывает все зарегистрированные скрейперы и возвращает список SourceRecord.

    Реализация построена так, чтобы можно было легко добавлять новые сайты
    через список ALL_SOURCES.
    """
    scrape_results: List[ScrapeResult] = []
    for scraper in ALL_SOURCES:
        scrape_results.extend(scraper(name))

    sources: List[SourceRecord] = []
    for r in scrape_results:
        sources.append(
            SourceRecord(
                domain=r.domain,
                url=r.url,
                weight=r.weight,
                unit="kg",
                fetched_at=_now_iso() if r.weight is not None else "",
            )
        )

    return sources

