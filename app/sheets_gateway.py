from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.config import Settings


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class SheetsGateway:
    settings: Settings
    _service: Optional[Any] = None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        # Lazy imports keep non-sheets commands test-friendly.
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds: Optional[Credentials] = None
        if self.settings.token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self.settings.token_path), scopes=SCOPES
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.settings.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            self.settings.token_path.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def _sheet_ids_by_title(self) -> dict[str, int]:
        service = self._get_service()
        spreadsheet = (
            service.spreadsheets()
            .get(
                spreadsheetId=self.settings.spreadsheet_id,
                fields="sheets(properties.sheetId,properties.title)",
            )
            .execute()
        )
        mapping: dict[str, int] = {}
        for sh in spreadsheet.get("sheets", []):
            props = sh.get("properties", {})
            title = props.get("title")
            sheet_id = props.get("sheetId")
            if isinstance(title, str) and isinstance(sheet_id, int):
                mapping[title] = sheet_id
        return mapping

    def ensure_sheet_exists(self, title: str) -> int:
        service = self._get_service()
        ids = self._sheet_ids_by_title()
        if title in ids:
            return ids[title]

        response = (
            service.spreadsheets()
            .batchUpdate(
                spreadsheetId=self.settings.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
            )
            .execute()
        )
        for reply in response.get("replies", []):
            props = reply.get("addSheet", {}).get("properties", {})
            if props.get("title") == title and isinstance(props.get("sheetId"), int):
                return props["sheetId"]

        return self._sheet_ids_by_title()[title]

    def write_values(self, title: str, values: list[list[str]], clear_range: str = "A:Z") -> None:
        service = self._get_service()
        self.ensure_sheet_exists(title)
        (
            service.spreadsheets()
            .values()
            .clear(
                spreadsheetId=self.settings.spreadsheet_id,
                range=f"{title}!{clear_range}",
                body={},
            )
            .execute()
        )
        (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.settings.spreadsheet_id,
                range=f"{title}!A1",
                valueInputOption="RAW",
                body={"values": values},
            )
            .execute()
        )

