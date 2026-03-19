from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import Settings
from app.recognizers.base import Recognizer
from app.sheets_gateway import SheetsGateway


@dataclass
class PdfZmk2Result:
    tool: str
    status: str
    input_path: str
    rows_count: int
    sheet_written: bool


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
        values.append(
            [
                str(item.get("elem", "")),
                str(item.get("det", "")),
                str(item.get("t", "")),
                str(item.get("n", "")),
                str(item.get("section", "")),
                str(item.get("length", "")),
                str(item.get("mass_sht", "")),
                str(item.get("mass_total", "")),
                str(item.get("mass_elem", "")),
                str(item.get("steel", "")),
                str(item.get("note", "")),
            ]
        )
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

