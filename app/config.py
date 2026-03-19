from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str
    sheet_pdf_zmk: str = "PDF_ZMK"
    sheet_pdf_zmk2: str = "PDF_ZMK2"
    sheet_pdf_zmk_ves: str = "PDF_ZMK_VES"
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
        return Settings(
            spreadsheet_id=spreadsheet_id,
            credentials_path=credentials_path,
            token_path=token_path,
        )

