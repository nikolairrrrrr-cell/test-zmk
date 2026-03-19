from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.recognizers.agent import AgentRecognizer, prepare_crops, list_pending_payloads
from app.recognizers.base import AgentReadRequired


def test_prepare_crops_creates_table_crop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    img_path = input_dir / "sample.jpg"
    Image.new("RGB", (1000, 700), color="white").save(img_path)

    prepared = prepare_crops(input_dir)
    assert len(prepared) == 1
    _source, slug, crop_path, _payload_path = prepared[0]
    assert slug == "sample"
    assert crop_path.exists()
    assert crop_path.name == "sample.table_x4.jpg"


def test_list_pending_payloads_detects_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    Image.new("RGB", (1000, 700), color="white").save(input_dir / "a.jpg")

    prepared = prepare_crops(input_dir)
    pending = list_pending_payloads(prepared)
    assert len(pending) == 1
    assert pending[0].expected_payload.name == "a.json"


def test_list_pending_payloads_empty_when_payload_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    Image.new("RGB", (1000, 700), color="white").save(input_dir / "b.jpg")

    rec = tmp_path / "data" / "recognition"
    rec.mkdir(parents=True, exist_ok=True)
    (rec / "b.json").write_text(
        json.dumps({"drawing_name": "B", "items": [{"poz": "1", "designation": "x", "name": "y", "qty": "1", "weight": "0,1"}]}),
        encoding="utf-8",
    )

    prepared = prepare_crops(input_dir)
    pending = list_pending_payloads(prepared)
    assert len(pending) == 0


def test_recognizer_pdf_zmk2_loads_existing_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    img_path = tmp_path / "sample.jpg"
    Image.new("RGB", (1000, 700), color="white").save(img_path)

    recognition_dir = tmp_path / "data" / "recognition"
    recognition_dir.mkdir(parents=True, exist_ok=True)
    (recognition_dir / "sample.json").write_text(
        json.dumps(
            {
                "drawing_name": "SAMPLE",
                "items": [
                    {"elem": "", "det": "1", "t": "1", "n": "", "section": "Test",
                     "length": "", "mass_sht": "1", "mass_total": "1", "note": ""}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    recognizer = AgentRecognizer()
    payload = recognizer.recognize_pdf_zmk2(img_path)
    assert payload["drawing_name"] == "SAMPLE"
