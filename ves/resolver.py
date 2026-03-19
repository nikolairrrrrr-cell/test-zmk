from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional

from .scraper import SourceRecord, fetch_sources_for_position


Status = Literal["confirmed", "single_source", "conflict", "not_found", "weak_match"]


@dataclass
class ResolvedPosition:
    name: str
    weights_by_domain: Dict[str, Optional[float]]
    status: Status
    note: str
    updated_at: str
    sources: List[SourceRecord] = field(default_factory=list)


DB_PATH = Path("ves") / "weights_db.json"
DEBUG_LAST_RUN_PATH = Path("ves") / "debug_last_run.json"

# Срок актуальности кэша (по умолчанию 365 дней)
CACHE_TTL_DAYS = 365

# Активные домены-источники, которые участвуют в агрегации и попадают в Google Sheet
ACTIVE_DOMAINS: List[str] = [
    "opora-trub.ru",
    "awstroy.ru",
]

# Приоритет доменов при конфликте (от более доверенного к менее)
SOURCE_PRIORITY: List[str] = [
    "opora-trub.ru",
    "awstroy.ru",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _current_db_path(path: Path | None = None) -> Path:
    return path if path is not None else DB_PATH


def _load_db(path: Path | None = None) -> Dict[str, dict]:
    path = _current_db_path(path)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except json.JSONDecodeError:
        # Повреждённый файл кэша не должен ломать всю выгрузку
        return {}


def _save_db(db: Dict[str, dict], path: Path | None = None) -> None:
    path = _current_db_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _is_cache_entry_valid(entry: dict) -> bool:
    """
    Проверяет, не протухла ли запись кэша по updated_at.
    """
    status = entry.get("status")
    # Записи, где вес не был найден, считаем невалидными и пробуем искать заново
    if status == "not_found":
        return False

    # Если в записи присутствуют домены, которых больше нет в ACTIVE_DOMAINS
    # (например, detalneftehim.ru), или для активного домена вес отсутствует,
    # форсируем обновление.
    weights_by_domain = entry.get("weights_by_domain", {}) or {}
    for domain, weight in weights_by_domain.items():
        if domain and domain not in ACTIVE_DOMAINS:
            return False
        if domain in ACTIVE_DOMAINS and weight is None:
            return False

    updated_at = entry.get("updated_at")
    if not updated_at:
        return False
    try:
        ts = datetime.fromisoformat(updated_at)
    except ValueError:
        return False
    return ts >= datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)


def _aggregate_sources(name: str, sources: List[SourceRecord]) -> ResolvedPosition:
    """
    Агрегирует список источников в итоговый статус, мапу весов по доменам и примечание.

    Логика упрощённая, но расширяема:
    - если нет ни одного источника с числовым весом -> status = not_found;
    - если есть только один домен с числовым весом -> single_source;
    - если несколько доменов дали один и тот же вес (с учётом небольшой погрешности) -> confirmed;
    - если домены дали существенно разные веса -> conflict.
    """
    weights_by_domain: Dict[str, Optional[float]] = {}
    numeric_by_domain: Dict[str, float] = {}

    # Учитываем только активные домены
    filtered_sources = [s for s in sources if s.domain in ACTIVE_DOMAINS]

    for src in filtered_sources:
        weights_by_domain[src.domain] = src.weight
        if src.weight is not None:
            numeric_by_domain[src.domain] = src.weight

    numeric_weights: List[float] = list(numeric_by_domain.values())

    if not numeric_weights:
        status: Status = "not_found"
        note = "Вес не найден ни на одном из доверенных сайтов."
    else:
        unique_weights = sorted(set(round(w, 3) for w in numeric_weights))
        domains_with_weight = [d for d, w in numeric_by_domain.items() if w is not None]

        # Описание по доменам для note
        domain_parts = [f"{d}: {numeric_by_domain[d]} кг" for d in domains_with_weight]
        domain_desc = "; ".join(domain_parts)

        if len(unique_weights) == 1 and len(domains_with_weight) >= 2:
            status = "confirmed"
            note = f"Подтверждён одинаковый вес {unique_weights[0]} кг на нескольких источниках ({domain_desc})."
        elif len(unique_weights) == 1 and len(domains_with_weight) == 1:
            status = "single_source"
            note = f"Вес {unique_weights[0]} кг найден только на одном сайте ({domain_desc})."
        elif len(unique_weights) == 2 and abs(unique_weights[0] - unique_weights[1]) <= 0.05:
            status = "confirmed"
            note = (
                "Несколько источников дали близкие значения веса "
                f"({domain_desc}); считаем подтверждённым в пределах погрешности."
            )
        elif len(domains_with_weight) == 1:
            # Один домен, но при этом веса как-то различаются (теоретически)
            status = "single_source"
            note = f"Вес найден только на одном сайте ({domain_desc})."
        else:
            # Есть несколько разных значений веса
            # Выбираем наиболее приоритетный домен и считаем остальные как конфликтующие
            sorted_domains = sorted(
                domains_with_weight,
                key=lambda d: SOURCE_PRIORITY.index(d) if d in SOURCE_PRIORITY else len(SOURCE_PRIORITY),
            )
            main_domain = sorted_domains[0]
            main_weight = numeric_by_domain[main_domain]
            status = "conflict"
            note = (
                "Источники дают разные значения веса "
                f"({domain_desc}); используем значение {main_weight} кг с {main_domain} как приоритетное."
            )
            # В качестве веса по доменам мы не трогаем, но статус сигнализирует о конфликте

    return ResolvedPosition(
        name=name,
        weights_by_domain=weights_by_domain,
        status=status,
        note=note,
        updated_at=_now_iso(),
        sources=filtered_sources,
    )


def resolve_position(name: str, force_refresh: bool = False, online: bool = True) -> ResolvedPosition:
    """
    Главная точка входа для получения веса по одной позиции.

    - Проверяет локальный кэш в ves/weights_db.json.
    - При необходимости обращается к веб-скрейперам.
    - Обновляет кэш и возвращает агрегированный результат.
    """
    db = _load_db()
    cached = db.get(name)

    if cached and not force_refresh and _is_cache_entry_valid(cached):
        # Преобразуем кэшированную запись в ResolvedPosition
        sources = [
            SourceRecord(
                domain=s.get("domain", ""),
                url=s.get("url", ""),
                weight=s.get("weight"),
                unit=s.get("unit", "kg"),
                fetched_at=s.get("fetched_at", ""),
            )
            for s in cached.get("sources", [])
        ]
        return ResolvedPosition(
            name=cached.get("name", name),
            weights_by_domain=cached.get("weights_by_domain", {}),
            status=cached.get("status", "not_found"),  # type: ignore[arg-type]
            note=cached.get("note", ""),
            updated_at=cached.get("updated_at", ""),
            sources=sources,
        )

    if not online:
        # В оффлайн-режиме, если валидной записи нет, возвращаем not_found без попытки скрейпа
        return ResolvedPosition(
            name=name,
            weights_by_domain={},
            status="not_found",
            note="Оффлайн-режим: в кэше нет валидной записи для этой позиции.",
            updated_at=_now_iso(),
            sources=[],
        )

    # Идём в интернет за свежими данными
    sources = fetch_sources_for_position(name)
    resolved = _aggregate_sources(name, sources)

    # Обновляем кэш
    db[name] = {
        "name": resolved.name,
        "weights_by_domain": resolved.weights_by_domain,
        "status": resolved.status,
        "note": resolved.note,
        "updated_at": resolved.updated_at,
        "sources": [asdict(s) for s in resolved.sources],
    }
    _save_db(db)

    return resolved


def load_positions(path: Path | str) -> List[str]:
    """
    Утилита для чтения списка позиций (по одной на строку) из текстового файла.
    Пустые строки и чистые комментарии (# ...) игнорируются.
    """
    p = Path(path)
    if not p.exists():
        return []

    positions: List[str] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            positions.append(raw)
    return positions


def generate_pdf_zmk_ves_values(
    positions: List[str], online: bool = True, force_refresh: bool = False
) -> List[List[str]]:
    """
    Формирует двумерный массив значений для листа PDF_ZMK_VES.

    Алгоритм:
    - сначала резолвит все позиции, чтобы понять полный набор доменов;
    - строит шапку: Позиция, <domain1>, <domain2>, ..., Примечание;
    - для каждой позиции заполняет веса по доменам и примечание.
    """
    # Резолвим все позиции; при force_refresh=True всегда идём в интернет
    resolved_list: List[ResolvedPosition] = [
        resolve_position(pos, force_refresh=force_refresh, online=online)
        for pos in positions
    ]

    # Для стабильности структуры Google Sheet всегда используем ACTIVE_DOMAINS
    # в фиксированном порядке, независимо от того, нашлись ли по ним веса.
    domains: List[str] = list(ACTIVE_DOMAINS)

    header = ["Позиция", *domains, "Примечание"]
    values: List[List[str]] = [header]

    debug_payload = []
    for r in resolved_list:
        row: List[str] = [r.name]
        for domain in domains:
            weight = r.weights_by_domain.get(domain)
            row.append("" if weight is None else str(weight))
        row.append(r.note)
        values.append(row)
        debug_payload.append(
            {
                "name": r.name,
                "status": r.status,
                "note": r.note,
                "weights_by_domain": r.weights_by_domain,
                "sources": [asdict(s) for s in r.sources],
            }
        )

    # Сохраняем отладочный отчёт по последнему прогону
    try:
        DEBUG_LAST_RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LAST_RUN_PATH.open("w", encoding="utf-8") as f:
            json.dump(debug_payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # Отладочный отчёт не должен ломать основной пайплайн
        pass

    return values

