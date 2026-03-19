from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.use_cases import pdf_zmk


class FakeRecognizer:
    def recognize_pdf_zmk(self, input_path: Path) -> dict:  # noqa: ARG002
        return {
            "drawing_name": "530-12",
            "items": [
                {
                    "poz": "1",
                    "designation": "490x275x8",
                    "name": "Основание",
                    "qty": "1",
                    "weight": "8,41",
                }
            ],
        }

    def recognize_pdf_zmk2(self, input_path: Path) -> dict:  # pragma: no cover
        raise NotImplementedError


def test_build_pdf_zmk_values_from_payload() -> None:
    values = pdf_zmk.build_pdf_zmk_values_from_payload(
        {
            "drawing_name": "530-12",
            "items": [
                {
                    "poz": "1",
                    "designation": "490x275x8",
                    "name": "Основание",
                    "qty": "1",
                    "weight": "8,41",
                }
            ],
        }
    )
    assert len(values) == 4
    assert values[3][0] == "1"
    assert values[3][1] == "530-12"


def test_run_pdf_zmk_dry_run_and_report(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    result = pdf_zmk.run_pdf_zmk(
        input_path=tmp_path / "payload.json",
        recognizer=FakeRecognizer(),
        settings=Settings.from_env(),
        sheet_write=True,
        dry_run=True,
        output_json=output,
    )
    assert result.status == "ok"
    assert result.sheet_written is False
    assert output.exists()

