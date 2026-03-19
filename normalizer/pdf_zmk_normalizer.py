from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Tuple


RAW_PDF_ZMK_DIR = Path("data/raw_specs/pdf_zmk")
OUTPUT_CSV_PATH = Path("data/pdf_zmk_baza2.csv")


def _split_size_and_thickness(size: str) -> Tuple[str, str]:
    """
    Разделяет строку вида '490x275x8' на:
    - '490x275x8' как размер листовой детали
    - '8' как толщину.
    Если формат другой или пусто, возвращает (size, '').
    """
    size = size.strip()
    if not size:
        return "", ""
    if "x" not in size and "х" not in size:
        return size, ""
    # Нормализуем латинскую/кириллическую x
    size_norm = size.replace("х", "x")
    # Специальный случай круглого проката: d10x1150, Ø20x1130 и т.п.
    if size_norm[0] in ("d", "D", "Ø", "ø"):
        try:
            first, _rest = size_norm[1:].split("x", 1)
            thickness = first
            return size, thickness
        except ValueError:
            return size, ""
    parts = size_norm.split("x")
    if len(parts) < 2:
        return size, ""
    thickness = parts[-1].lstrip("dDØø")
    return size, thickness


def _classify_item(name: str) -> str:
    """
    Возвращает тип детали:
    - 'sheet'  -> Лист
    - 'circle' -> Круг (используем для хомутов)
    - 'fastener' -> Метизы (болты, гайки, шайбы и т.п.)
    """
    name = name.strip()
    if not name:
        return "sheet"

    if name.startswith(("Болт", "Гайка", "Шайба", "Гровер", "Шплинт")):
        return "fastener"
    if name == "Хомут":
        return "circle"
    return "sheet"


def _transform_item(
    drawing_name: str, raw: Dict[str, str]
) -> List[str]:
    poz = raw["poz"]
    designation = (raw.get("designation") or "").strip()
    part_name = (raw.get("name") or "").strip()
    qty = (raw.get("qty") or "").strip()
    weight = (raw.get("weight") or "").strip()

    sheet_size = ""
    thickness = ""
    circle_size = ""
    circle_qty = ""
    fastener_name = ""
    fastener_qty = ""
    short_part_name = part_name

    kind = _classify_item(part_name)

    if kind == "sheet":
        sheet_size, thickness = _split_size_and_thickness(designation)
    elif kind == "circle":
        circle_qty = qty
        thickness = "—"
        if designation:
            size_body = designation.lstrip("dDØø").replace("x", "х")
            circle_size = f"М{size_body}"
    elif kind == "fastener":
        short_part_name = part_name.split()[0] if part_name else ""
        fastener_name = part_name
        fastener_qty = qty
        thickness = "—"

    return [
        poz,
        drawing_name,
        sheet_size,
        qty if kind in {"sheet", "circle"} and sheet_size else "",
        weight,
        short_part_name,
        thickness,
        circle_size,
        circle_qty,
        fastener_name,
        fastener_qty,
    ]


def _load_raw_items(path: Path) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            poz = (row.get("poz") or "").strip()
            if not poz:
                continue
            items.append(
                {
                    "poz": poz,
                    "designation": (row.get("designation") or "").strip(),
                    "name": (row.get("name") or "").strip(),
                    "qty": (row.get("qty") or "").strip(),
                    "weight": (row.get("weight") or "").strip(),
                }
            )
    return items


def generate_pdf_zmk_values() -> List[List[str]]:
    """
    Строит нормализованные значения для листа PDF_ZMK
    по всем raw-спецификациям в data/raw_specs/pdf_zmk.
    Одновременно перезаписывает data/pdf_zmk_baza2.csv.
    """
    header_group = [
        "",
        "",
        "Лист",
        "",
        "",
        "",
        "",
        "Круг",
        "",
        "Метизы",
        "",
    ]

    header_columns = [
        "поз",
        "имя чертежа",
        "размер дет. (лист)",
        "колич дет.",
        "вес 1 дет.",
        "имя дет.",
        "толщ-диам",
        "размер дет. из круга",
        "колич дет. круг",
        "метизы",
        "колич метизов",
    ]

    values: List[List[str]] = [
        ["" for _ in header_columns],
        header_group,
        header_columns,
    ]

    raw_files = sorted(RAW_PDF_ZMK_DIR.glob("*.csv"))
    for idx, raw_path in enumerate(raw_files):
        drawing_name = raw_path.stem
        items = _load_raw_items(raw_path)
        for item in items:
            values.append(_transform_item(drawing_name, item))
        if idx != len(raw_files) - 1:
            values.append([])

    # Перезаписываем csv
    OUTPUT_CSV_PATH.parent.mkdir(exist_ok=True)
    with OUTPUT_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        for row in values:
            writer.writerow(row)

    return values

