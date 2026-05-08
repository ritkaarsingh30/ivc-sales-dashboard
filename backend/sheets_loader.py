"""
sheets_loader.py — Fetch all IVC data from Google Sheets.

Key design decisions:
  1. Batch fetch: each spreadsheet uses spreadsheets.values.batchGet to pull all
     needed tabs in a single API call (2 calls per spreadsheet: open + batchGet).
  2. Dynamic months: the MONTHS list is built from what's actually on Drive (sales
     tab names + per-month files). New months added to Drive are picked up
     automatically on next startup or /api/data/refresh.
  3. Redis-backed month config: MONTHS is cached in Redis so restarts don't need
     to re-open the sales/copy spreadsheets just to discover tab names.
"""

import re
import json
import asyncio
from datetime import datetime
from storage.sheets import SheetStorage
from storage.sheet_discovery import MONTH_ALIASES, ALL_MONTH_KEYS, get_discovered_months
from loaders import (
    load_sales,
    load_projection,
    load_monthly_reports,
    load_visit_tracker,
    load_tour_plan,
)
from cache.redis_client import get_sheet_metadata, set_sheet_metadata, redis_client
import pandas as pd


# ── Month metadata ────────────────────────────────────────────────────────────

MONTH_ORDER: list[str] = ALL_MONTH_KEYS  # ["jan", "feb", ..., "dec"]

MONTH_FULL_NAMES: dict[str, str] = {
    "jan": "January",   "feb": "February",  "mar": "March",     "apr": "April",
    "may": "May",       "jun": "June",      "jul": "July",      "aug": "August",
    "sep": "September", "oct": "October",   "nov": "November",  "dec": "December",
}

# Active months config — set by init_months_config(), used throughout
MONTHS: list[dict] = []

_MONTHS_REDIS_KEY = "config:months_config"
_MONTHS_REDIS_TTL = 26 * 3600  # 26h (slightly longer than 25h sheet metadata TTL)


# ── Tab name detection from spreadsheet worksheet titles ──────────────────────

def _detect_sales_tabs(worksheet_titles: list[str]) -> dict[str, str]:
    """
    Return {month_key: tab_title} for all month tabs found in the sales spreadsheet.
    Handles: 'JAN-26', 'FEB-26', 'MAR-2026', etc.
    """
    pattern = re.compile(r'^([A-Z]{3})-(\d{2,4})$')
    abbr_to_tab: dict[str, str] = {}
    for title in worksheet_titles:
        m = pattern.match(title.strip().upper())
        if m:
            abbr = m.group(1).lower()
            if abbr in MONTH_ORDER:
                abbr_to_tab[abbr] = title
    return abbr_to_tab


def build_months_config(
    sheet_map: dict,
    sales_ws_titles: list[str],
) -> list[dict]:
    """
    Build the active MONTHS config from:
    - sheet_map: {logical_key: spreadsheet_id} from Drive discovery
    - sales_ws_titles: worksheet titles in the sales spreadsheet

    A month is included if it has a sales tab OR at least one per-month file on Drive.
    """
    sales_tabs = _detect_sales_tabs(sales_ws_titles)
    discovered = set(get_discovered_months(sheet_map))

    months_config: list[dict] = []
    for i, mon in enumerate(MONTH_ORDER):
        mon_up = mon.upper()
        if not (mon in sales_tabs or mon in discovered):
            continue

        prev_mon = MONTH_ORDER[i - 1] if i > 0 else None

        months_config.append({
            "key":            mon,
            "sales_tab":      sales_tabs.get(mon, f"{mon_up}-26"),
            "prev_sales_tab": sales_tabs.get(prev_mon) if prev_mon else None,
            "expense_key":    f"SHEET_{mon_up}_EXPENSE",
            "monthly_key":    f"SHEET_{mon_up}_MONTHLY",
            "projection_key": f"SHEET_{mon_up}_PROJECTION",
            "tour_key":       f"SHEET_{mon_up}_TOUR",
            "visits_key":     f"SHEET_{mon_up}_VISITS",
            "visits_label":   mon.capitalize(),
            "label":          MONTH_FULL_NAMES[mon],
        })

    return months_config


# ── MONTHS initialisation (Redis-cached) ─────────────────────────────────────

async def init_months_config(storage: SheetStorage) -> None:
    """
    Populate the module-level MONTHS list. Tries Redis first to avoid extra
    API calls on every restart. Falls back to opening the sales spreadsheet
    to detect available month tabs.

    Call once on startup before load_all_from_sheets().
    """
    global MONTHS

    try:
        cached = await redis_client.get(_MONTHS_REDIS_KEY)
        if cached:
            MONTHS = json.loads(cached)
            print(f"[sheets_loader] Months from Redis: {[m['key'] for m in MONTHS]}")
            return
    except Exception as exc:
        print(f"[sheets_loader] Redis months read failed: {exc}")

    # Open the sales spreadsheet to detect available month tabs
    sales_id = storage.sheet_id("SHEET_SALES")

    def _list_titles(sheet_id: str) -> list[str]:
        if not sheet_id:
            return []
        try:
            ss = storage.client.open_by_key(sheet_id)
            return [ws.title for ws in ss.worksheets()]
        except Exception as exc:
            print(f"[sheets_loader] Could not list tabs for {sheet_id!r}: {exc}")
            return []

    loop = asyncio.get_event_loop()
    sales_titles = await loop.run_in_executor(None, _list_titles, sales_id)

    MONTHS = build_months_config(storage._sheet_map, sales_titles)
    print(f"[sheets_loader] Discovered months: {[m['key'] for m in MONTHS]}")

    try:
        await redis_client.setex(_MONTHS_REDIS_KEY, _MONTHS_REDIS_TTL, json.dumps(MONTHS))
    except Exception as exc:
        print(f"[sheets_loader] Redis months write failed: {exc}")


async def invalidate_months_cache() -> None:
    """Remove the cached MONTHS config from Redis so next call re-discovers."""
    try:
        await redis_client.delete(_MONTHS_REDIS_KEY)
    except Exception:
        pass


# ── Batch fetch helpers ───────────────────────────────────────────────────────

def _esc_tab(name: str) -> str:
    """Escape single quotes in tab names for A1 notation."""
    return name.replace("'", "''")


def _batch_get_tabs_sync(
    spreadsheet,
    tab_names: list[str] | None,
) -> dict[str, pd.DataFrame]:
    """
    Synchronous: fetch one or more worksheet tabs in a single values_batch_get call.

    If tab_names is None, fetches ALL worksheets in the spreadsheet.
    Returns {tab_title: DataFrame}. Tabs not found return an empty DataFrame.
    """
    ws_list = spreadsheet.worksheets()
    available = {ws.title for ws in ws_list}

    if tab_names is None:
        valid = [ws.title for ws in ws_list]
    else:
        valid = [n for n in tab_names if n in available]

    if not valid:
        return {n: pd.DataFrame() for n in (tab_names or [])}

    ranges = [f"'{_esc_tab(n)}'!A:ZZ" for n in valid]
    try:
        result = spreadsheet.values_batch_get(ranges)
    except Exception as exc:
        print(f"[sheets_loader] values_batch_get failed: {exc}")
        return {n: pd.DataFrame() for n in valid}

    dfs: dict[str, pd.DataFrame] = {}
    for i, vr in enumerate(result.get("valueRanges", [])):
        values = vr.get("values", [])
        dfs[valid[i]] = pd.DataFrame(values) if values else pd.DataFrame()

    # Fill any missing entries
    for n in valid:
        dfs.setdefault(n, pd.DataFrame())

    return dfs


async def _open_and_batch_fetch(
    storage: SheetStorage,
    logical_key: str,
    sheet_id: str,
    tab_names: list[str] | None,
) -> tuple[dict[str, pd.DataFrame], str | None, bool]:
    """
    Check Drive modified time vs Redis cache. If the sheet is unchanged, return
    ({}, drive_modified, True). If changed (or never cached), open the spreadsheet
    and batch-fetch the requested tabs, returning (dfs, drive_modified, False).

    tab_names=None fetches ALL tabs (used for tour plan and visits tracker).
    """
    if not sheet_id:
        return {}, None, True

    loop = asyncio.get_event_loop()

    # Check Drive modified time
    try:
        drive_modified: str | None = await loop.run_in_executor(
            None, storage.get_modified_time, sheet_id
        )
    except Exception as exc:
        print(f"[sheets_loader] get_modified_time failed for {logical_key}: {exc}")
        drive_modified = None

    # Compare with Redis-cached modified time
    is_cached = False
    if drive_modified:
        meta = await get_sheet_metadata(sheet_id)
        is_cached = bool(meta and meta.get("drive_modified") == drive_modified)

    if is_cached:
        print(f"[cache HIT]  {logical_key}")
        return {}, drive_modified, True

    print(f"[cache MISS] {logical_key}")

    def _fetch() -> dict[str, pd.DataFrame]:
        ss = storage.client.open_by_key(sheet_id)
        return _batch_get_tabs_sync(ss, tab_names)

    try:
        dfs = await loop.run_in_executor(None, _fetch)
    except Exception as exc:
        print(f"[sheets_loader] Could not fetch {logical_key} ({sheet_id!r}): {exc}")
        dfs = {}

    return dfs, drive_modified, False


# ── Default empty data structures ─────────────────────────────────────────────

def _empty_month_data() -> dict:
    return {
        "sales":      {"current": pd.DataFrame(), "prev": pd.DataFrame()},
        "projection": {"projection": None, "activity_plan": None, "missing_sheets": ["ALL"]},
        "expense":    {
            "activity_exp": None, "other_exp": None, "money_received": None,
            "opening_balance_fcfa": 0, "new_budget_fcfa": 0,
            "total_received_fcfa": 0, "total_spent_fcfa": 0,
            "balance_fcfa": 0, "missing_sheets": ["ALL"],
        },
        "monthly":    {"delegates": None, "budget_analysis": None, "missing_sheets": ["ALL"]},
        "tour":       pd.DataFrame(),
        "visits":     pd.DataFrame(
            columns=["MR_ID", "MR", "Doctor", "Speciality", "Clinic", "Visit_Date", "Month"]
        ),
    }


# ── Main load entry point ─────────────────────────────────────────────────────

async def load_all_from_sheets(storage: SheetStorage) -> dict:
    """
    Fetch all IVC data from Google Sheets using batch fetching.
    MONTHS must be initialised first via init_months_config().
    """
    data: dict = {}

    # ── Sales file: all month tabs in ONE batchGet call ───────────────────────
    all_sales_tabs = list(dict.fromkeys(
        [m["sales_tab"] for m in MONTHS]
        + [m["prev_sales_tab"] for m in MONTHS if m["prev_sales_tab"]]
    ))
    sales_id = storage.sheet_id("SHEET_SALES")
    sales_dfs, sales_mod, sales_cached = await _open_and_batch_fetch(
        storage, "SHEET_SALES", sales_id, all_sales_tabs
    )

    # Persist cache metadata for sales sheet
    if not sales_cached and sales_mod and sales_dfs:
        await set_sheet_metadata(sales_id, datetime.utcnow().isoformat(), sales_mod)

    # ── Per-month data ─────────────────────────────────────────────────────────
    for m in MONTHS:
        key = m["key"]
        print(f"[sheets_loader] Loading {key.upper()}…")

        # Sales
        sales_df     = sales_dfs.get(m["sales_tab"])
        prev_sales_df = sales_dfs.get(m["prev_sales_tab"]) if m["prev_sales_tab"] else None
        sales = (
            load_sales(df=sales_df, prev_df=prev_sales_df)
            if sales_df is not None and not sales_df.empty
            else {"current": pd.DataFrame(), "prev": pd.DataFrame()}
        )

        # Projection (PROJECTION + ACTIVITY PLAN tabs — one batchGet)
        proj_id = storage.sheet_id(m["projection_key"])
        proj_dfs, proj_mod, proj_cached = await _open_and_batch_fetch(
            storage, m["projection_key"], proj_id, ["PROJECTION", "ACTIVITY PLAN"]
        )
        if proj_dfs:
            projection = load_projection(
                df=proj_dfs.get("PROJECTION"),
                activity_df=proj_dfs.get("ACTIVITY PLAN"),
            )
            if not proj_cached and proj_mod:
                await set_sheet_metadata(proj_id, datetime.utcnow().isoformat(), proj_mod)
        else:
            projection = _empty_month_data()["projection"]

        # Expense (3 tabs — one batchGet)
        exp_id = storage.sheet_id(m["expense_key"])
        exp_dfs, exp_mod, exp_cached = await _open_and_batch_fetch(
            storage, m["expense_key"], exp_id,
            ["MONEY RECEIVED", "ACTIVITY EXP.", "OTHER EXP."]
        )
        if exp_dfs:
            expense = _load_expense_from_sheets(
                exp_dfs.get("MONEY RECEIVED"),
                exp_dfs.get("ACTIVITY EXP."),
                exp_dfs.get("OTHER EXP."),
            )
            if not exp_cached and exp_mod:
                await set_sheet_metadata(exp_id, datetime.utcnow().isoformat(), exp_mod)
        else:
            expense = _empty_month_data()["expense"]

        # Monthly reports (2 tabs — one batchGet)
        monthly_id = storage.sheet_id(m["monthly_key"])
        monthly_dfs, monthly_mod, monthly_cached = await _open_and_batch_fetch(
            storage, m["monthly_key"], monthly_id,
            ["Delegates Reports", "Budget Analysis"]
        )
        if monthly_dfs:
            monthly = load_monthly_reports(
                df=monthly_dfs.get("Delegates Reports"),
                budget_df=monthly_dfs.get("Budget Analysis"),
            )
            if not monthly_cached and monthly_mod:
                await set_sheet_metadata(monthly_id, datetime.utcnow().isoformat(), monthly_mod)
        else:
            monthly = _empty_month_data()["monthly"]

        # Tour plan (first tab — fetch all, take first)
        tour_id = storage.sheet_id(m["tour_key"])
        tour_dfs, tour_mod, tour_cached = await _open_and_batch_fetch(
            storage, m["tour_key"], tour_id, None  # None = all tabs
        )
        if tour_dfs:
            first_df = next(iter(tour_dfs.values()), pd.DataFrame())
            tour = load_tour_plan(df=first_df) if not first_df.empty else pd.DataFrame()
            if not tour_cached and tour_mod:
                await set_sheet_metadata(tour_id, datetime.utcnow().isoformat(), tour_mod)
        else:
            tour = pd.DataFrame()

        # Visit tracker (all tabs — one batchGet)
        visits_id = storage.sheet_id(m["visits_key"])
        visits_dfs, visits_mod, visits_cached = await _open_and_batch_fetch(
            storage, m["visits_key"], visits_id, None  # None = all tabs
        )
        if visits_dfs:
            sheets_arg = [
                (df, m["visits_label"])
                for df in visits_dfs.values()
                if not df.empty
            ]
            visits = load_visit_tracker(sheets=sheets_arg)
            if not visits_cached and visits_mod:
                await set_sheet_metadata(visits_id, datetime.utcnow().isoformat(), visits_mod)
        else:
            visits = _empty_month_data()["visits"]

        data[key] = {
            "sales": sales, "projection": projection, "expense": expense,
            "monthly": monthly, "tour": tour, "visits": visits,
        }
        print(f"[sheets_loader] {key.upper()} OK.")

    return data


# ── Incremental refresh ───────────────────────────────────────────────────────

async def refresh_changed_from_sheets(
    storage: SheetStorage,
    existing_data: dict,
) -> tuple[dict, list[str]]:
    """
    Check all sheets for modifications. Only refetch sheets that changed.
    Updates existing_data in-place and returns (updated_data, changed_env_keys).
    """
    changed_env_keys: list[str] = []

    # ── Check master sheets ───────────────────────────────────────────────────
    sales_id = storage.sheet_id("SHEET_SALES")

    loop = asyncio.get_event_loop()
    sales_mod = await (
        loop.run_in_executor(None, storage.get_modified_time, sales_id) if sales_id
        else asyncio.sleep(0)
    )

    sales_cached = bool(sales_mod and (await get_sheet_metadata(sales_id) or {}).get("drive_modified") == sales_mod)

    # Re-discover months if sales sheet changed (new tabs may have been added)
    if not sales_cached:
        await invalidate_months_cache()
        await init_months_config(storage)

    # Fetch changed sales sheet
    if not sales_cached and sales_id:
        all_sales_tabs = list(dict.fromkeys(
            [m["sales_tab"] for m in MONTHS]
            + [m["prev_sales_tab"] for m in MONTHS if m["prev_sales_tab"]]
        ))
        def _fetch_sales():
            ss = storage.client.open_by_key(sales_id)
            return _batch_get_tabs_sync(ss, all_sales_tabs)
        try:
            sales_dfs = await loop.run_in_executor(None, _fetch_sales)
            changed_env_keys.append("SHEET_SALES")
            if sales_mod:
                await set_sheet_metadata(sales_id, datetime.utcnow().isoformat(), sales_mod)
        except Exception as exc:
            print(f"[refresh] Failed to fetch sales: {exc}")
            sales_dfs = {}
    else:
        sales_dfs = {}

    # ── Per-month data ────────────────────────────────────────────────────────
    for m in MONTHS:
        key = m["key"]
        existing_data.setdefault(key, _empty_month_data())

        # Sales (already fetched above)
        if sales_dfs:
            s_df  = sales_dfs.get(m["sales_tab"])
            p_df  = sales_dfs.get(m["prev_sales_tab"]) if m["prev_sales_tab"] else None
            existing_data[key]["sales"] = (
                load_sales(df=s_df, prev_df=p_df)
                if s_df is not None and not s_df.empty
                else {"current": pd.DataFrame(), "prev": pd.DataFrame()}
            )

        # Projection
        proj_id = storage.sheet_id(m["projection_key"])
        proj_dfs, proj_mod, proj_cached = await _open_and_batch_fetch(
            storage, m["projection_key"], proj_id, ["PROJECTION", "ACTIVITY PLAN"]
        )
        if not proj_cached:
            changed_env_keys.append(m["projection_key"])
            existing_data[key]["projection"] = (
                load_projection(df=proj_dfs.get("PROJECTION"), activity_df=proj_dfs.get("ACTIVITY PLAN"))
                if proj_dfs else _empty_month_data()["projection"]
            )
            if proj_mod:
                await set_sheet_metadata(proj_id, datetime.utcnow().isoformat(), proj_mod)

        # Expense
        exp_id = storage.sheet_id(m["expense_key"])
        exp_dfs, exp_mod, exp_cached = await _open_and_batch_fetch(
            storage, m["expense_key"], exp_id,
            ["MONEY RECEIVED", "ACTIVITY EXP.", "OTHER EXP."]
        )
        if not exp_cached:
            changed_env_keys.append(m["expense_key"])
            existing_data[key]["expense"] = (
                _load_expense_from_sheets(
                    exp_dfs.get("MONEY RECEIVED"),
                    exp_dfs.get("ACTIVITY EXP."),
                    exp_dfs.get("OTHER EXP."),
                )
                if exp_dfs else _empty_month_data()["expense"]
            )
            if exp_mod:
                await set_sheet_metadata(exp_id, datetime.utcnow().isoformat(), exp_mod)

        # Monthly reports
        monthly_id = storage.sheet_id(m["monthly_key"])
        monthly_dfs, monthly_mod, monthly_cached = await _open_and_batch_fetch(
            storage, m["monthly_key"], monthly_id,
            ["Delegates Reports", "Budget Analysis"]
        )
        if not monthly_cached:
            changed_env_keys.append(m["monthly_key"])
            existing_data[key]["monthly"] = (
                load_monthly_reports(
                    df=monthly_dfs.get("Delegates Reports"),
                    budget_df=monthly_dfs.get("Budget Analysis"),
                )
                if monthly_dfs else _empty_month_data()["monthly"]
            )
            if monthly_mod:
                await set_sheet_metadata(monthly_id, datetime.utcnow().isoformat(), monthly_mod)

        # Tour plan
        tour_id = storage.sheet_id(m["tour_key"])
        tour_dfs, tour_mod, tour_cached = await _open_and_batch_fetch(
            storage, m["tour_key"], tour_id, None
        )
        if not tour_cached:
            changed_env_keys.append(m["tour_key"])
            first_df = next(iter(tour_dfs.values()), pd.DataFrame()) if tour_dfs else pd.DataFrame()
            existing_data[key]["tour"] = (
                load_tour_plan(df=first_df) if not first_df.empty else pd.DataFrame()
            )
            if tour_mod:
                await set_sheet_metadata(tour_id, datetime.utcnow().isoformat(), tour_mod)

        # Visits
        visits_id = storage.sheet_id(m["visits_key"])
        visits_dfs, visits_mod, visits_cached = await _open_and_batch_fetch(
            storage, m["visits_key"], visits_id, None
        )
        if not visits_cached:
            changed_env_keys.append(m["visits_key"])
            if visits_dfs:
                sheets_arg = [(df, m["visits_label"]) for df in visits_dfs.values() if not df.empty]
                existing_data[key]["visits"] = (
                    load_visit_tracker(sheets=sheets_arg) if sheets_arg
                    else _empty_month_data()["visits"]
                )
            else:
                existing_data[key]["visits"] = _empty_month_data()["visits"]
            if visits_mod:
                await set_sheet_metadata(visits_id, datetime.utcnow().isoformat(), visits_mod)

    return existing_data, changed_env_keys


# ── Expense helper (unchanged from before) ────────────────────────────────────

def _load_expense_from_sheets(raw_mr, raw_ae, raw_oe):
    from constants import FCFA_TO_EUR
    from utils import safe_num
    from name_map import normalize_mr, normalize_doctor, normalize_activity, parse_multi_products, activity_display_name

    missing_sheets = []
    mr_df = None
    total_received_fcfa = 0
    total_spent_fcfa = 0
    balance_fcfa = 0
    opening_balance_fcfa = 0
    new_budget_fcfa = 0

    if raw_mr is None or (hasattr(raw_mr, "empty") and raw_mr.empty):
        missing_sheets.append("MONEY RECEIVED")
    else:
        mr_rows = []
        for i, row in raw_mr.iterrows():
            if i < 2:
                continue
            date_val = row.iloc[0]
            if pd.isna(date_val) or str(date_val).strip() in ("", "NaN", "Date"):
                continue
            if "TOTAL" in str(date_val).upper():
                continue
            try:
                date_val = pd.to_datetime(date_val)
            except Exception:
                continue
            mr_rows.append({
                "Date": date_val,
                "Source": str(row.iloc[1]).strip(),
                "Amount_FCFA": safe_num(row.iloc[2]),
                "Amount_EUR": safe_num(row.iloc[3]),
                "Description": str(row.iloc[4]).strip(),
            })
        mr_df = pd.DataFrame(mr_rows)

        for i, row in raw_mr.iterrows():
            label     = str(row.iloc[0]).upper()
            col1_label = str(row.iloc[1]).upper() if len(row) > 1 else ""
            col5      = str(row.iloc[5]).upper() if len(row) > 5 else ""
            if "OPENING BALANCE" in col1_label:
                opening_balance_fcfa = safe_num(row.iloc[2]) if len(row) > 2 else 0
            elif "RECEIVED ACTIVITY MONEY" in col1_label or "RECEIVED" in col1_label:
                new_budget_fcfa = safe_num(row.iloc[2]) if len(row) > 2 else 0
            if "TOTAL" in label and ("RECEIV" in label or "FCFA" in label):
                v = safe_num(row.iloc[2]) if len(row) > 2 else 0
                if v > 0:
                    total_received_fcfa = v
            if "TOTAL SPENT" in col5:
                total_spent_fcfa = safe_num(row.iloc[6]) if len(row) > 6 else 0
            if "BALANCE" in col5:
                balance_fcfa = safe_num(row.iloc[6]) if len(row) > 6 else 0
        if total_received_fcfa == 0 and mr_df is not None and not mr_df.empty:
            total_received_fcfa = mr_df["Amount_FCFA"].sum()

    ae_df = None
    if raw_ae is None or (hasattr(raw_ae, "empty") and raw_ae.empty):
        missing_sheets.append("ACTIVITY EXP.")
    else:
        ae_rows = []
        for i, row in raw_ae.iterrows():
            if i < 2:
                continue
            sn = row.iloc[0]
            if not isinstance(sn, (int, float)) or pd.isna(sn):
                try:
                    sn = float(sn)
                except (ValueError, TypeError):
                    continue
            if pd.isna(sn):
                continue
            raw_resp = str(row.iloc[8]).strip()
            if "/" in raw_resp:
                mr_ids = ",".join(normalize_mr(p.strip()) for p in raw_resp.split("/"))
            else:
                mr_ids = normalize_mr(raw_resp)
            num_mrs = max(1, len([x.strip() for x in mr_ids.split(",") if x.strip()]))
            amount_fcfa = safe_num(row.iloc[6])
            ae_rows.append({
                "SN": int(sn),
                "Doctor":         normalize_doctor(str(row.iloc[1]).strip()),
                "Hospital":       str(row.iloc[2]).strip(),
                "Speciality":     str(row.iloc[3]).strip(),
                "Activity":       str(row.iloc[4]).strip(),
                "Activity_ID":    normalize_activity(str(row.iloc[4]).strip()),
                "Products":       parse_multi_products(str(row.iloc[5]).strip()),
                "Amount_FCFA":    amount_fcfa,
                "Amount_EUR":     round(amount_fcfa / FCFA_TO_EUR, 2),
                "Amount_FCFA_Share": amount_fcfa / num_mrs,
                "Contact":        str(row.iloc[7]).strip(),
                "Responsible":    raw_resp,
                "MR_IDs":         mr_ids,
                "Num_MRs":        num_mrs,
            })
        ae_df = pd.DataFrame(ae_rows)
        if not ae_df.empty:
            ae_df["Activity"] = ae_df["Activity_ID"].apply(activity_display_name)

    oe_df = None
    if raw_oe is None or (hasattr(raw_oe, "empty") and raw_oe.empty):
        missing_sheets.append("OTHER EXP.")
    else:
        oe_rows = []
        for i, row in raw_oe.iterrows():
            if i < 2:
                continue
            sn = row.iloc[0]
            if not isinstance(sn, (int, float)) or pd.isna(sn):
                try:
                    sn = float(sn)
                except (ValueError, TypeError):
                    continue
            if pd.isna(sn):
                continue
            amount_fcfa = safe_num(row.iloc[3])
            if amount_fcfa == 0:
                continue
            oe_rows.append({
                "SN":          int(sn),
                "Country":     str(row.iloc[1]).strip(),
                "Details":     str(row.iloc[2]).strip(),
                "Amount_FCFA": amount_fcfa,
                "Amount_EUR":  safe_num(row.iloc[4]),
                "Comments":    str(row.iloc[5]).strip(),
                "Category":    str(row.iloc[6]).strip(),
            })
        oe_df = pd.DataFrame(oe_rows)

    return {
        "activity_exp":        ae_df,
        "other_exp":           oe_df,
        "money_received":      mr_df,
        "opening_balance_fcfa": opening_balance_fcfa,
        "new_budget_fcfa":     new_budget_fcfa,
        "total_received_fcfa": total_received_fcfa,
        "total_spent_fcfa":    total_spent_fcfa,
        "balance_fcfa":        balance_fcfa,
        "missing_sheets":      missing_sheets,
    }
