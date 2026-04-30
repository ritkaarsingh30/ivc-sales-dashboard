"""
storage/sheet_discovery.py — Auto-discover IVC spreadsheets from a Google Drive folder.

The user shares ONE folder with the service account and sets GOOGLE_DRIVE_FOLDER_ID.
This module lists every spreadsheet in that folder (recursively into subfolders) and
matches filenames to the known logical keys using keyword heuristics.

Returned dict shape (same keys sheets_loader uses):
  {
    "SHEET_SALES":          "<spreadsheet_id>",
    "SHEET_COPY_REPORT":    "<spreadsheet_id>",
    "SHEET_JAN_EXPENSE":    "<spreadsheet_id>",
    "SHEET_JAN_MONTHLY":    "<spreadsheet_id>",
    ...
  }

Any unmatched files are logged but ignored; any unmatched logical keys come back as
empty strings so sheets_loader can skip them gracefully (same as an unset env var).
"""

import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ── Matching rules ───────────────────────────────────────────────────────────
#
# Each rule is (logical_key, required_all, month_aliases, forbidden).
#   required_all  — ALL of these keywords must appear in the normalised filename (AND)
#   month_aliases — at least ONE of these must appear (OR). Empty list = no month check.
#   forbidden     — NONE of these may appear (AND NOT)

MONTH_ALIASES = {
    "jan": ["jan", "january"],
    "feb": ["feb", "february"],
    "mar": ["mar", "march"],
}

def _make_rules():
    rules = [
        # Master files — no month alias check
        ("SHEET_SALES",       ["sales", "2026"], [],       ["monthly", "visit", "expense", "projection", "copy"]),
        ("SHEET_COPY_REPORT", ["copy"],           [],       ["expense", "visit", "monthly", "projection", "tour"]),
    ]
    for mon, aliases in MONTH_ALIASES.items():
        mon_up = mon.upper()
        rules += [
            (f"SHEET_{mon_up}_EXPENSE",    ["expense"],    aliases, []),
            (f"SHEET_{mon_up}_MONTHLY",    ["monthly"],    aliases, ["expense", "visit", "projection", "tour"]),
            (f"SHEET_{mon_up}_PROJECTION", ["projection"], aliases, []),
            (f"SHEET_{mon_up}_TOUR",       ["tour"],       aliases, ["expense", "visit"]),
            (f"SHEET_{mon_up}_VISITS",     ["visit"],      aliases, ["expense", "monthly", "tour", "projection"]),
        ]
    return rules

RULES = _make_rules()


def _normalise(name: str) -> str:
    """Lowercase, replace non-alphanumeric with space."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower())


def _matches(name_norm: str, required_all: list, month_aliases: list, forbidden: list) -> bool:
    """
    Returns True when:
      - ALL keywords in required_all are present (AND)
      - At least ONE alias in month_aliases is present (OR). Skipped when list is empty.
      - NONE of the forbidden keywords are present
    """
    if not all(kw in name_norm for kw in required_all):
        return False
    if month_aliases and not any(alias in name_norm for alias in month_aliases):
        return False
    if any(kw in name_norm for kw in forbidden):
        return False
    return True


# ── Drive file listing ───────────────────────────────────────────────────────

def _list_spreadsheets_in_folder(drive_service, folder_id: str) -> list[dict]:
    """
    Returns a flat list of {'id': ..., 'name': ...} for every Google Spreadsheet
    inside folder_id, including files in direct subfolders (one level of recursion
    is enough for the Jan / Feb / March structure, but we recurse fully).
    """
    results = []

    def _recurse(fid):
        page_token = None
        while True:
            try:
                resp = drive_service.files().list(
                    q=f"'{fid}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                    pageSize=200,
                ).execute()
            except HttpError as exc:
                print(f"[sheet_discovery] Drive API error listing folder {fid!r}: {exc}")
                break

            for f in resp.get("files", []):
                mime = f.get("mimeType", "")
                if mime == "application/vnd.google-apps.spreadsheet":
                    results.append({"id": f["id"], "name": f["name"]})
                elif mime == "application/vnd.google-apps.folder":
                    # recurse into subfolders (Jan, Feb, March, etc.)
                    _recurse(f["id"])

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    _recurse(folder_id)
    return results


# ── Public API ───────────────────────────────────────────────────────────────

def discover_sheets(credentials, folder_id: str) -> dict:
    """
    Uses the Drive API to list all spreadsheets in folder_id (recursively),
    then matches each file to a logical key using RULES.

    Returns dict {logical_key: spreadsheet_id}. Keys with no match map to "".
    """
    drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    files = _list_spreadsheets_in_folder(drive_service, folder_id)

    if not files:
        print("[sheet_discovery] WARNING: No spreadsheets found in the Drive folder. "
              "Make sure the folder is shared with the service account.")
        return {key: "" for key, *_ in RULES}

    print(f"[sheet_discovery] Found {len(files)} spreadsheet(s) in Drive folder:")
    for f in files:
        print(f"  · {f['name']}  ({f['id']})")

    sheet_map: dict[str, str] = {}

    for logical_key, required_all, month_aliases, forbidden in RULES:
        matched = [
            f for f in files
            if _matches(_normalise(f["name"]), required_all, month_aliases, forbidden)
        ]
        if len(matched) == 1:
            sheet_map[logical_key] = matched[0]["id"]
            print(f"[sheet_discovery]  {logical_key} → \"{matched[0]['name']}\"")
        elif len(matched) > 1:
            # Prefer the most recently-named file (alphabetical last) as a tiebreak
            best = sorted(matched, key=lambda x: x["name"])[-1]
            sheet_map[logical_key] = best["id"]
            names = [m["name"] for m in matched]
            print(f"[sheet_discovery]  {logical_key} → \"{best['name']}\" "
                  f"(ambiguous match from: {names}; picked last alphabetically)")
        else:
            sheet_map[logical_key] = ""
            print(f"[sheet_discovery]  {logical_key} → NOT FOUND")

    return sheet_map
