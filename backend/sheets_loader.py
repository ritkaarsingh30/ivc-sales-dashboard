"""
sheets_loader.py — Google Sheets equivalent of load_all_data().

Reads spreadsheet IDs from the SheetStorage sheet_map (auto-discovered via
Drive API) rather than from individual .env variables. Falls back gracefully
when a sheet is not found (same behaviour as a missing local file).
"""

import os
from storage.sheets import SheetStorage
from loaders import (
    load_sales,
    load_projection,
    load_expense,
    load_monthly_reports,
    load_visit_tracker,
    load_copy_report,
    load_tour_plan,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_df(storage: SheetStorage, sheet_id: str, tab_name: str = None):
    """Return a DataFrame or None when the sheet_id is not configured."""
    if not sheet_id:
        return None
    try:
        return storage.get_sheet_as_df(sheet_id, tab_name)
    except Exception as exc:
        print(f"[sheets_loader] Could not fetch sheet {sheet_id!r} tab {tab_name!r}: {exc}")
        return None


def _all_tabs_as_dfs(storage: SheetStorage, sheet_id: str):
    """
    Returns a list of (tab_name, DataFrame) for every worksheet in the
    spreadsheet.  Used to read visit-tracker workbooks that have one tab
    per MR.
    """
    if not sheet_id:
        return []
    try:
        spreadsheet = storage.client.open_by_key(sheet_id)
        result = []
        for ws in spreadsheet.worksheets():
            records = ws.get_all_values()
            import pandas as pd
            df = pd.DataFrame(records)
            result.append((ws.title, df))
        return result
    except Exception as exc:
        print(f"[sheets_loader] Could not open multi-tab workbook {sheet_id!r}: {exc}")
        return []


# ---------------------------------------------------------------------------
# Month configuration
# ---------------------------------------------------------------------------

MONTHS = [
    {
        "key": "jan",
        "sales_tab": "JAN-26",
        "prev_sales_tab": None,
        "copy_tab": "jan 2026",
        "expense_key": "SHEET_JAN_EXPENSE",
        "monthly_key": "SHEET_JAN_MONTHLY",
        "projection_key": "SHEET_JAN_PROJECTION",
        "tour_key": "SHEET_JAN_TOUR",
        "visits_key": "SHEET_JAN_VISITS",
        "visits_label": "Jan",
    },
    {
        "key": "feb",
        "sales_tab": "FEB-26",
        "prev_sales_tab": "JAN-26",
        "copy_tab": "feb 2026",
        "expense_key": "SHEET_FEB_EXPENSE",
        "monthly_key": "SHEET_FEB_MONTHLY",
        "projection_key": "SHEET_FEB_PROJECTION",
        "tour_key": "SHEET_FEB_TOUR",
        "visits_key": "SHEET_FEB_VISITS",
        "visits_label": "Feb",
    },
    {
        "key": "mar",
        "sales_tab": "MAR-26",
        "prev_sales_tab": "FEB-26",
        "copy_tab": "march 2026",
        "expense_key": "SHEET_MAR_EXPENSE",
        "monthly_key": "SHEET_MAR_MONTHLY",
        "projection_key": "SHEET_MAR_PROJECTION",
        "tour_key": "SHEET_MAR_TOUR",
        "visits_key": "SHEET_MAR_VISITS",
        "visits_label": "Mar",
    },
]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_all_from_sheets(storage: SheetStorage) -> dict:
    """
    Fetch every required DataFrame from Google Sheets and pass them to
    the standard loaders via the df= parameter path.

    Returns the same dict structure as load_all_data():
      { "jan": { "sales": ..., "projection": ..., ... }, "feb": ..., "mar": ... }

    Sheet IDs come from storage.sheet_id() which checks the auto-discovered
    _sheet_map first, then falls back to env vars of the same name.
    """
    import pandas as pd

    data = {}

    # ── Master spreadsheet IDs (auto-discovered or env fallback) ────────────
    sales_id = storage.sheet_id("SHEET_SALES")
    copy_id  = storage.sheet_id("SHEET_COPY_REPORT")

    for m in MONTHS:
        key = m["key"]
        print(f"[sheets_loader] Loading {key.upper()} data from Google Sheets…")

        # ── Sales ──────────────────────────────────────────────────────────
        sales_df = _safe_df(storage, sales_id, m["sales_tab"])
        prev_sales_df = (
            _safe_df(storage, sales_id, m["prev_sales_tab"])
            if m["prev_sales_tab"]
            else None
        )
        if sales_df is not None:
            sales = load_sales(df=sales_df, prev_df=prev_sales_df)
        else:
            sales = {"current": pd.DataFrame(), "prev": pd.DataFrame()}


        # ── Projection + Activity Plan ─────────────────────────────────────
        proj_id = storage.sheet_id(m["projection_key"])
        proj_df = _safe_df(storage, proj_id, "PROJECTION")
        activity_df = _safe_df(storage, proj_id, "ACTIVITY PLAN")
        if proj_id:
            projection = load_projection(df=proj_df, activity_df=activity_df)
        else:
            projection = {"projection": None, "activity_plan": None, "missing_sheets": ["ALL"]}

        # ── Expense (3 tabs from one workbook) ─────────────────────────────
        exp_id = storage.sheet_id(m["expense_key"])
        if exp_id:
            mr_df  = _safe_df(storage, exp_id, "MONEY RECEIVED")
            ae_df  = _safe_df(storage, exp_id, "ACTIVITY EXP.")
            oe_df  = _safe_df(storage, exp_id, "OTHER EXP.")
            expense = _load_expense_from_sheets(mr_df, ae_df, oe_df)
        else:
            expense = {
                "activity_exp": None, "other_exp": None, "money_received": None,
                "opening_balance_fcfa": 0, "new_budget_fcfa": 0,
                "total_received_fcfa": 0, "total_spent_fcfa": 0,
                "balance_fcfa": 0, "missing_sheets": ["ALL"],
            }

        # ── Monthly Reports ────────────────────────────────────────────────
        monthly_id = storage.sheet_id(m["monthly_key"])
        if monthly_id:
            del_df    = _safe_df(storage, monthly_id, "Delegates Reports")
            budget_df = _safe_df(storage, monthly_id, "Budget Analysis")
            monthly = load_monthly_reports(df=del_df, budget_df=budget_df)
        else:
            monthly = {"delegates": None, "budget_analysis": None, "missing_sheets": ["ALL"]}

        # ── Copy Report ────────────────────────────────────────────────────
        copy_df = _safe_df(storage, copy_id, m["copy_tab"])
        copy = (
            load_copy_report(df=copy_df)
            if copy_df is not None
            else {
                "product_perf": pd.DataFrame(),
                "plan_activities": pd.DataFrame(),
                "actual_activities": pd.DataFrame(),
                "missing_sheets": [],
            }
        )

        # ── Tour Plan ──────────────────────────────────────────────────────
        tour_id = storage.sheet_id(m["tour_key"])
        tour_df = _safe_df(storage, tour_id)
        tour = load_tour_plan(df=tour_df) if tour_df is not None else pd.DataFrame()

        # ── Visit Tracker (one tab per MR) ─────────────────────────────────
        visits_id = storage.sheet_id(m["visits_key"])
        if visits_id:
            tab_dfs   = _all_tabs_as_dfs(storage, visits_id)
            sheets_arg = [(df, m["visits_label"]) for _, df in tab_dfs]
            visits    = load_visit_tracker(sheets=sheets_arg)
        else:
            visits = pd.DataFrame(
                columns=["MR_ID", "MR", "Doctor", "Speciality", "Clinic", "Visit_Date", "Month"]
            )

        data[key] = {
            "sales": sales, "projection": projection, "expense": expense,
            "monthly": monthly, "copy": copy, "tour": tour, "visits": visits,
        }
        print(f"[sheets_loader] {key.upper()} loaded OK.")

    return data


# ---------------------------------------------------------------------------
# Expense helper — runs the same parsing as load_expense but with pre-built DFs
# ---------------------------------------------------------------------------

def _load_expense_from_sheets(raw_mr, raw_ae, raw_oe):
    """
    Replicates load_expense parsing using three pre-fetched DataFrames
    (one per tab: MONEY RECEIVED, ACTIVITY EXP., OTHER EXP.).
    This avoids duplicating the parsing logic while still supporting the
    three-tab structure that load_expense normally reads from a single workbook.
    """
    from constants import FCFA_TO_EUR
    from utils import safe_num
    from name_map import normalize_mr, normalize_doctor, normalize_activity, parse_multi_products, activity_display_name
    import pandas as pd

    missing_sheets = []
    mr_df = None
    total_received_fcfa = 0
    total_spent_fcfa = 0
    balance_fcfa = 0
    opening_balance_fcfa = 0
    new_budget_fcfa = 0

    # ── MONEY RECEIVED ──
    if raw_mr is None:
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
            label = str(row.iloc[0]).upper()
            col1_label = str(row.iloc[1]).upper() if len(row) > 1 else ""
            col5 = str(row.iloc[5]).upper() if len(row) > 5 else ""
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

    # ── ACTIVITY EXP ──
    ae_df = None
    if raw_ae is None:
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
            num_mrs = len([x.strip() for x in mr_ids.split(",") if x.strip()])
            num_mrs = max(1, num_mrs)
            amount_fcfa = safe_num(row.iloc[6])
            ae_rows.append({
                "SN": int(sn),
                "Doctor": normalize_doctor(str(row.iloc[1]).strip()),
                "Hospital": str(row.iloc[2]).strip(),
                "Speciality": str(row.iloc[3]).strip(),
                "Activity": str(row.iloc[4]).strip(),
                "Activity_ID": normalize_activity(str(row.iloc[4]).strip()),
                "Products": parse_multi_products(str(row.iloc[5]).strip()),
                "Amount_FCFA": amount_fcfa,
                "Amount_EUR": round(amount_fcfa / FCFA_TO_EUR, 2),
                "Amount_FCFA_Share": amount_fcfa / num_mrs,
                "Contact": str(row.iloc[7]).strip(),
                "Responsible": raw_resp,
                "MR_IDs": mr_ids,
                "Num_MRs": num_mrs,
            })
        ae_df = pd.DataFrame(ae_rows)
        if not ae_df.empty:
            ae_df["Activity"] = ae_df["Activity_ID"].apply(activity_display_name)

    # ── OTHER EXP ──
    oe_df = None
    if raw_oe is None:
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
                "SN": int(sn),
                "Country": str(row.iloc[1]).strip(),
                "Details": str(row.iloc[2]).strip(),
                "Amount_FCFA": amount_fcfa,
                "Amount_EUR": safe_num(row.iloc[4]),
                "Comments": str(row.iloc[5]).strip(),
                "Category": str(row.iloc[6]).strip(),
            })
        oe_df = pd.DataFrame(oe_rows)

    return {
        "activity_exp": ae_df,
        "other_exp": oe_df,
        "money_received": mr_df,
        "opening_balance_fcfa": opening_balance_fcfa,
        "new_budget_fcfa": new_budget_fcfa,
        "total_received_fcfa": total_received_fcfa,
        "total_spent_fcfa": total_spent_fcfa,
        "balance_fcfa": balance_fcfa,
        "missing_sheets": missing_sheets,
    }
