from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import Settings
from app.recognizers.agent import (
    list_pending_payloads,
    load_validated_payload,
    prepare_crops,
)
from app.recognizers.base import AgentReadRequired, RecognitionError, Recognizer
from app.sheets_gateway import SheetsGateway


@dataclass
class PdfZmk2Result:
    tool: str
    status: str
    input_path: str
    rows_count: int
    sheet_written: bool


@dataclass
class PdfZmk2FullResult:
    tool: str
    status: str
    input_dir: str
    total_files: int
    processed_files: int
    skipped_files: int
    rows_count: int
    sheet_written: bool
    elapsed_seconds: float
    processed: list[str]
    skipped: list[dict[str, str]]


def _pdf_zmk2_item_to_row(item: dict) -> list[str]:
    """
    Map JSON item fields to sheet columns (отпр. элем., дет., т., н., …).

    Canonical payload (preferred): ``elem`` = отпр. элем., ``det`` = дет.,
    ``t`` / ``n`` = развёртка КОЛ.

    Legacy payloads (e.g. ``data/raw_specs/pdf_zmk2/*.csv``): when ``elem`` is
    empty, ``det`` / ``t`` hold отпр. элем. / дет. (see docs/nonstandard-rules.md).
    Then ``n`` is treated as the first КОЛ column (т.); second part (н.) requires
    a canonical payload with ``elem`` set.
    """
    elem = (item.get("elem") or "").strip()
    det = item.get("det", "")
    t = item.get("t", "")
    n = item.get("n", "")

    if elem:
        ship = elem
        part = str(det)
        kol_t = str(t)
        kol_n = str(n)
    else:
        ship = str(det)
        part = str(t)
        kol_t = str(n)
        kol_n = ""

    return [
        ship,
        part,
        kol_t,
        kol_n,
        str(item.get("section", "")),
        str(item.get("length", "")),
        str(item.get("mass_sht", "")),
        str(item.get("mass_total", "")),
        str(item.get("mass_elem", "")),
        str(item.get("steel", "")),
        str(item.get("note", "")),
    ]


def build_pdf_zmk2_values_from_payload(payload: dict) -> list[list[str]]:
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Payload field 'items' must be a list.")

    header_group = [
        "отпр. элем.",
        "дет.",
        "КОЛ.",
        "",
        "",
        "",
        "МАССА В КГ",
        "",
        "",
        "марка стали",
        "примечания",
    ]
    header_columns = [
        "отпр. элем.",
        "дет.",
        "т.",
        "н.",
        "сечение",
        "длина",
        "шт.",
        "общ.",
        "элем.",
        "марка стали",
        "примечания",
    ]

    values = [header_group, header_columns]
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each item must be an object.")
        values.append(_pdf_zmk2_item_to_row(item))
    return values


def run_pdf_zmk2(
    input_path: Path,
    recognizer: Recognizer,
    settings: Settings,
    sheet_write: bool = False,
    dry_run: bool = False,
    output_json: Path | None = None,
) -> PdfZmk2Result:
    payload = recognizer.recognize_pdf_zmk2(input_path)
    values = build_pdf_zmk2_values_from_payload(payload)

    sheet_written = False
    if sheet_write and not dry_run:
        SheetsGateway(settings).write_values(settings.sheet_pdf_zmk2, values)
        sheet_written = True

    result = PdfZmk2Result(
        tool="pdf-zmk2",
        status="ok",
        input_path=str(input_path),
        rows_count=max(0, len(values) - 2),
        sheet_written=sheet_written,
    )
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def run_pdf_zmk2_full(
    input_dir: Path,
    settings: Settings,
    sheet_write: bool = False,
    dry_run: bool = False,
    output_json: Path | None = None,
    workers: int = 6,  # noqa: ARG001 — parity with pdf-zmk full CLI
) -> PdfZmk2FullResult:
    """
    Strict pipeline for PDF_ZMK2 — ровно как у pdf-zmk (База2). Ни один этап не пропускается.

    ┌─────────────────────────────────────────────────────────────────┐
    │ PHASE 1  CROP + UPSCALE                                          │
    │   CLI берёт каждое изображение из input_dir, находит таблицу,   │
    │   кропает, увеличивает x4 → data/recognition/<slug>.table_x4.jpg │
    ├─────────────────────────────────────────────────────────────────┤
    │ PHASE 2  AGENT READ (гейт)                                       │
    │   CLI проверяет: для каждого кропа есть <slug>.json с items?    │
    │   Если нет → AgentReadRequired (exit 3), список «что прочитать».  │
    ├─────────────────────────────────────────────────────────────────┤
    │ PHASE 3  WRITE JSON                                              │
    │   Агент открывает каждый кроп, читает таблицу (отпр/дет, сечение,│
    │   длина, массы, примечания), пишет data/recognition/<slug>.json  │
    ├─────────────────────────────────────────────────────────────────┤
    │ PHASE 4  NORMALIZE + SHEETS                                      │
    │   Повторный запуск: CLI загружает все JSON, раскладывает по     │
    │   колонкам PDF_ZMK2, склеивает блоки → лист Google «СЕ1»        │
    └─────────────────────────────────────────────────────────────────┘
    """
    start = time.perf_counter()

    # ── PHASE 1: crop + upscale ──────────────────────────────────────
    prepared = prepare_crops(input_dir)
    total_files = len(prepared)

    # ── PHASE 2: agent read gate (never skipped) ──────────────────────
    pending = list_pending_payloads(prepared)
    if pending:
        raise AgentReadRequired(pending)

    # ── PHASE 3/4: load payloads, normalize, merge, (optional) sheets ──
    processed: list[tuple[str, list[list[str]]]] = []
    skipped: list[dict[str, str]] = []

    for source, _slug, _crop, payload_path in prepared:
        try:
            if source.suffix.lower() == ".json":
                payload = load_validated_payload(source)
            else:
                payload = load_validated_payload(payload_path)
            values = build_pdf_zmk2_values_from_payload(payload)
            processed.append((source.name, values))
        except (RecognitionError, ValueError) as exc:
            skipped.append({"file": source.name, "reason": str(exc)})

    if skipped:
        sample = "; ".join(f"{s['file']}: {s['reason']}" for s in skipped[:3])
        raise RuntimeError(
            f"pdf-zmk2 full failed: {len(skipped)} file(s) with errors. "
            f"Examples: {sample}"
        )

    processed.sort(key=lambda x: x[0])
    merged_values: list[list[str]] = []
    rows_count = 0
    for idx, (_name, block) in enumerate(processed):
        if idx == 0:
            merged_values.extend(block)
        else:
            merged_values.append([])
            merged_values.extend(block[2:])
        rows_count += max(0, len(block) - 2)

    sheet_written = False
    if merged_values and sheet_write and not dry_run:
        SheetsGateway(settings).write_values(settings.sheet_pdf_zmk2, merged_values)
        sheet_written = True

    elapsed_seconds = round(time.perf_counter() - start, 3)
    result = PdfZmk2FullResult(
        tool="pdf-zmk2-full",
        status="ok",
        input_dir=str(input_dir),
        total_files=total_files,
        processed_files=len(processed),
        skipped_files=len(skipped),
        rows_count=rows_count,
        sheet_written=sheet_written,
        elapsed_seconds=elapsed_seconds,
        processed=[name for name, _ in processed],
        skipped=skipped,
    )
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result
