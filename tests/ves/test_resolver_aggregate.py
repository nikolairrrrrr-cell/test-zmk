from ves import resolver
from ves.scraper import SourceRecord


def _src(domain: str, weight):  # type: ignore[no-untyped-def]
    return SourceRecord(
        domain=domain,
        url="https://example.test",
        weight=weight,
        unit="kg",
        fetched_at="2026-03-13T00:00:00Z" if weight is not None else "",
    )


def test_aggregate_sources_confirmed() -> None:
    sources = [
        _src("opora-trub.ru", 2.5),
        _src("awstroy.ru", 2.5),
    ]
    r = resolver._aggregate_sources("Опора 57 КХ-А11", sources)
    assert r.status == "confirmed"
    assert r.weights_by_domain["opora-trub.ru"] == 2.5
    assert r.weights_by_domain["awstroy.ru"] == 2.5


def test_aggregate_sources_conflict_uses_priority() -> None:
    sources = [
        _src("opora-trub.ru", 2.5),
        _src("awstroy.ru", 3.0),
    ]
    r = resolver._aggregate_sources("Опора 57 КХ-А11", sources)
    assert r.status == "conflict"
    # Приоритет у opora-trub.ru, но оба значения сохраняются
    assert r.weights_by_domain["opora-trub.ru"] == 2.5
    assert r.weights_by_domain["awstroy.ru"] == 3.0

