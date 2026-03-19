from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.use_cases import pdf_zmk2


class FakeRecognizer:
    def recognize_pdf_zmk(self, input_path: Path) -> dict:  # pragma: no cover
        raise NotImplementedError

    def recognize_pdf_zmk2(self, input_path: Path) -> dict:  # noqa: ARG002
        return {
            "drawing_name": "630-13",
            "items": [
                {
                    "elem": "",
                    "det": "8",
                    "t": "4",
                    "n": "",
                    "section": "Шайба 30 ГОСТ 11371-78*",
                    "length": "",
                    "mass_sht": "0,053",
                    "mass_total": "0,21",
                    "note": "",
                }
            ],
        }


def test_build_pdf_zmk2_values_from_payload() -> None:
    values = pdf_zmk2.build_pdf_zmk2_values_from_payload(
        {
            "items": [
                {
                    "elem": "",
                    "det": "8",
                    "t": "4",
                    "n": "",
                    "section": "Шайба 30 ГОСТ 11371-78*",
                    "length": "",
                    "mass_sht": "0,053",
                    "mass_total": "0,21",
                    "note": "",
                }
            ]
        }
    )
    assert len(values) == 3
    assert values[2][1] == "8"
    assert values[2][4].startswith("Шайба")


def test_run_pdf_zmk2_dry_run_and_report(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    result = pdf_zmk2.run_pdf_zmk2(
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

