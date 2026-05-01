"""
storage/sheets.py — Google Sheets storage backend using gspread.

Sheet data is cached in-memory after the first fetch.
Call clear_cache() to force a re-pull (used by the /api/data/refresh endpoint).
"""
import gspread
import json
import os
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from .base import StorageBackend

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetStorage(StorageBackend):
    def __init__(self):
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            raise ValueError(
                "GOOGLE_CREDENTIALS_JSON is not set in .env. "
                "Paste the full service-account JSON as a single line."
            )
        creds_dict = json.loads(creds_json)
        self.creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        self.client = gspread.authorize(self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)
        self._sheet_map: dict[str, str] = {}  # logical_key → spreadsheet_id

    def discover(self, folder_id: str) -> dict:
        """
        Auto-discover all IVC spreadsheets in the given Drive folder and cache
        the resulting logical_key → spreadsheet_id map on self._sheet_map.
        Returns the map so callers can inspect it.
        """
        from .sheet_discovery import discover_sheets
        self._sheet_map = discover_sheets(self.creds, folder_id)
        return self._sheet_map

    def sheet_id(self, logical_key: str) -> str:
        """
        Return the spreadsheet ID for a logical key (e.g. 'SHEET_JAN_EXPENSE').
        Falls back to the env var of the same name, then empty string.
        """
        return (
            self._sheet_map.get(logical_key)
            or os.getenv(logical_key, "")
        )

    def get_modified_time(self, sheet_id: str) -> str | None:
        """Fetch the latest modifiedTime from Drive API."""
        try:
            file_meta = self.drive_service.files().get(fileId=sheet_id, fields="modifiedTime").execute()
            return file_meta.get("modifiedTime")
        except Exception as e:
            print(f"[sheets] Could not get modified time for {sheet_id}: {e}")
            return None

    def get_sheet_as_df(self, sheet_id: str, tab_name: str = None) -> pd.DataFrame:
        """
        Opens a Google Sheet by its spreadsheet ID, reads the specified tab
        (or the first tab when tab_name is None), and returns the data as a
        pandas DataFrame with integer column indices (no header row assumed).

        All cell values come back as strings from gspread. The existing
        safe_num() helper in the loaders already converts strings to floats
        gracefully, so no extra coercion is needed here.
        """
        spreadsheet = self.client.open_by_key(sheet_id)
        if tab_name:
            worksheet = spreadsheet.worksheet(tab_name)
        else:
            worksheet = spreadsheet.get_worksheet(0)

        records = worksheet.get_all_values()  # list[list[str]], no header assumption
        return pd.DataFrame(records)

    # ── StorageBackend contract ──────────────────────────────────────────────
    # SheetStorage does not serve raw bytes or enumerate files; those
    # operations are not meaningful for a Sheets-backed system.

    def get_file_bytes(self, relative_path: str) -> bytes:
        raise NotImplementedError(
            "SheetStorage does not serve raw bytes. Use get_sheet_as_df()."
        )

    def list_files(self, folder: str) -> list:
        raise NotImplementedError(
            "SheetStorage does not list files. Sheet IDs come from .env variables."
        )

    def exists(self, relative_path: str) -> bool:
        raise NotImplementedError(
            "SheetStorage does not check file paths. Sheet IDs come from .env variables."
        )
