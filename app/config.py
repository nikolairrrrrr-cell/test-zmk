from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str
    sheet_pdf_zmk: str = "База2"
    sheet_pdf_zmk2: str = "СЕ1"
    sheet_pdf_zmk_ves: str = "Масса"
    # Каталог входных файлов для pdf-zmk2 full (изображения, PDF, JSON); переопределение: PDF_ZMK2_INPUT_DIR
    pdf_zmk2_input_dir: Path = Path("СЕ1")
    credentials_path: Path = Path("credentials.json")
    token_path: Path = Path("token.json")

    @staticmethod
    def from_env() -> "Settings":
        spreadsheet_id = os.getenv(
            "GOOGLE_SPREADSHEET_ID", "1QIjweQBuESwrwnID0wr9RtNdkOfNJWQ2kfZ-c9CH_4I"
        )
        credentials_path = Path(
            os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))
        sheet_pdf_zmk = os.getenv("GOOGLE_SHEET_PDF_ZMK", "База2")
        sheet_pdf_zmk2 = os.getenv("GOOGLE_SHEET_PDF_ZMK2", "СЕ1")
        sheet_pdf_zmk_ves = os.getenv("GOOGLE_SHEET_PDF_ZMK_VES", "Масса")
        pdf_zmk2_input_dir = Path(
            os.getenv("PDF_ZMK2_INPUT_DIR", "СЕ1")
        )
        return Settings(
            spreadsheet_id=spreadsheet_id,
            sheet_pdf_zmk=sheet_pdf_zmk,
            sheet_pdf_zmk2=sheet_pdf_zmk2,
            sheet_pdf_zmk_ves=sheet_pdf_zmk_ves,
            pdf_zmk2_input_dir=pdf_zmk2_input_dir,
            credentials_path=credentials_path,
            token_path=token_path,
        )

