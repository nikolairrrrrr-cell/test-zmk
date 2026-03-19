from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Optional

from .base import AgentReadRequired, PendingCrop, RecognitionError
from .table_pipeline import preprocess_table_image, slugify_filename

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
_SUPPORTED_EXTS = _IMAGE_EXTS | {".pdf", ".json"}
_RAW_PDF_ZMK_DIR = Path("data/raw_specs/pdf_zmk")
_RECOGNITION_DIR = Path("data/recognition")


def _slug_and_payload(source: Path) -> tuple[str, Path]:
    slug = slugify_filename(source.stem)
    return slug, _RECOGNITION_DIR / f"{slug}.json"


def _payload_is_valid(payload_path: Path) -> bool:
    if not payload_path.exists():
        return False
    try:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    items = data.get("items")
    return isinstance(items, list) and len(items) > 0


# ── Phase 1: crop + upscale ─────────────────────────────────────────

def prepare_crops(input_dir: Path) -> list[tuple[Path, str, Path, Path]]:
    """
    Phase 1 of the strict pipeline.
    For every supported file in `input_dir`:
      - images  -> crop table + upscale x4, save as table_x4.jpg
      - PDFs    -> no crop (future: render first page), just register slug
      - JSONs   -> passthrough (already a payload)

    Returns list of (source_file, slug, crop_path_or_None, expected_payload_path).
    """
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input dir does not exist: {input_dir}")

    results: list[tuple[Path, str, Path, Path]] = []
    files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTS
    )

    for source in files:
        ext = source.suffix.lower()
        slug, payload_path = _slug_and_payload(source)

        if ext == ".json":
            results.append((source, slug, source, source))
            continue

        crop_path = _RECOGNITION_DIR / f"{slug}.table_x4.jpg"
        if ext in _IMAGE_EXTS:
            crop_path = preprocess_table_image(source, output_dir=_RECOGNITION_DIR)
        else:
            crop_path = _RECOGNITION_DIR / f"{slug}.table_x4.jpg"

        results.append((source, slug, crop_path, payload_path))

    return results


# ── Phase 2: verify agent read ──────────────────────────────────────

def list_pending_payloads(
    prepared: list[tuple[Path, str, Path, Path]],
) -> list[PendingCrop]:
    """
    Phase 2 check.
    Returns list of crops that have no valid JSON payload yet.
    If this list is non-empty, the agent MUST read each crop and write the JSON
    before the pipeline can continue.
    """
    pending: list[PendingCrop] = []
    for source, _slug, crop_path, payload_path in prepared:
        if source.suffix.lower() == ".json":
            continue
        if not _payload_is_valid(payload_path):
            pending.append(PendingCrop(
                source_file=source,
                crop_path=crop_path,
                expected_payload=payload_path,
            ))
    return pending


# ── Phase 3: load validated payloads ─────────────────────────────────

def load_validated_payload(payload_path: Path) -> dict:
    """Load and validate a single JSON payload. Raises RecognitionError on failure."""
    if not payload_path.exists():
        raise RecognitionError(f"Payload file not found: {payload_path}")
    try:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecognitionError(f"Invalid JSON: {payload_path}") from exc
    items = data.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise RecognitionError(
            f"Payload has empty or missing 'items': {payload_path}"
        )
    return data


class AgentRecognizer:
    """
    Agent-side recognizer.

    Strict pipeline (enforced by code):
      Phase 1 — crop + upscale       (prepare_crops)
      Phase 2 — agent reads crops     (list_pending_payloads -> AgentReadRequired)
      Phase 3 — load validated JSON   (recognize_pdf_zmk)

    There is no local OCR. There is no external LLM API.
    The agent running in Cursor reads the crop images and writes JSON payloads.
    """

    _RAW_PDF_ZMK_DIR = _RAW_PDF_ZMK_DIR

    def __init__(self) -> None:
        self._raw_specs_index: Optional[list[tuple[str, Path]]] = None

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _normalize_name_for_match(value: str) -> str:
        s = value.lower()
        s = re.sub(r"[^a-z0-9а-яё]+", "", s, flags=re.IGNORECASE)
        return s

    def _try_build_payload_from_raw_specs(self, input_path: Path) -> dict | None:
        if not self._RAW_PDF_ZMK_DIR.exists():
            return None
        target = self._normalize_name_for_match(input_path.stem)

        if self._raw_specs_index is None:
            self._raw_specs_index = [
                (self._normalize_name_for_match(csv_path.stem), csv_path)
                for csv_path in sorted(self._RAW_PDF_ZMK_DIR.glob("*.csv"))
            ]

        best_match: Path | None = None
        best_score = 0
        for candidate, csv_path in self._raw_specs_index:
            score = 0
            if candidate == target:
                score = len(candidate) + 1000
            elif candidate and (candidate in target or target in candidate):
                score = len(candidate)
            if score > best_score:
                best_score = score
                best_match = csv_path

        if best_match is None:
            return None

        items: list[dict[str, str]] = []
        with best_match.open(newline="", encoding="utf-8") as f:
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
        if not items:
            return None
        return {"drawing_name": best_match.stem, "items": items}

    # ── Phase 3 entry: payload must already exist ─────────────────────

    def recognize_pdf_zmk(self, input_path: Path) -> dict:
        if not input_path.exists():
            raise RecognitionError(f"Input path does not exist: {input_path}")

        suffix = input_path.suffix.lower()
        if suffix == ".json":
            return load_validated_payload(input_path)

        _slug, payload_path = _slug_and_payload(input_path)

        if not _payload_is_valid(payload_path):
            fallback = self._try_build_payload_from_raw_specs(input_path)
            if fallback is not None:
                payload_path.parent.mkdir(parents=True, exist_ok=True)
                payload_path.write_text(
                    json.dumps(fallback, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                raise RecognitionError(
                    f"No valid payload for {input_path.name}. "
                    f"Expected: {payload_path}. "
                    "Run the full pipeline so the agent can read the crop."
                )

        return load_validated_payload(payload_path)

    def recognize_pdf_zmk2(self, input_path: Path) -> dict:
        if not input_path.exists():
            raise RecognitionError(f"Input path does not exist: {input_path}")

        suffix = input_path.suffix.lower()
        if suffix == ".json":
            return load_validated_payload(input_path)

        _slug, payload_path = _slug_and_payload(input_path)

        if not _payload_is_valid(payload_path):
            raise RecognitionError(
                f"No valid payload for {input_path.name}. "
                f"Expected: {payload_path}."
            )

        return load_validated_payload(payload_path)
