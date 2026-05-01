import os
import time
import asyncio
from datetime import datetime
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
from cache.redis_client import get_sheet_metadata, set_sheet_metadata
import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_sheet_cached(storage: SheetStorage, logical_key: str, sheet_id: str):
    """
    Checks Redis metadata. If unchanged, returns (True, None, drive_modified).
    If changed or missed, fetches from API, updates Redis, and returns (False, spreadsheet object, drive_modified).
    """
    if not sheet_id:
        return True, None
        
    try:
        drive_modified = await asyncio.get_event_loop().run_in_executor(None, storage.get_modified_time, sheet_id)
        if not drive_modified:
            drive_modified = datetime.utcnow().isoformat()
            
        meta = await get_sheet_metadata(sheet_id)
        if meta and meta.get("drive_modified") == drive_modified:
            print(f"[cache HIT] {logical_key}")
            return True, None, drive_modified
            
        print(f"[cache MISS] {logical_key}")
        await asyncio.sleep(1.2)
        
        spreadsheet = await asyncio.get_event_loop().run_in_executor(None, storage.client.open_by_key, sheet_id)
        return False, spreadsheet, drive_modified
    except Exception as exc:
        print(f"[sheets_loader] Could not access sheet {logical_key} ({sheet_id!r}): {exc}")
        return False, None, None


async def _get_tab_df(spreadsheet, tab_name: str = None) -> tuple[pd.DataFrame | None, bool]:
    if not spreadsheet:
        return None, False
    try:
        def fetch():
            if tab_name:
                ws = spreadsheet.worksheet(tab_name)
            else:
                ws = spreadsheet.get_worksheet(0)
            return pd.DataFrame(ws.get_all_values())
        return await asyncio.get_event_loop().run_in_executor(None, fetch), False
    except Exception as exc:
        print(f"[sheets_loader] Could not fetch tab {tab_name!r}: {exc}")
        import gspread
        is_quota = isinstance(exc, gspread.exceptions.APIError)
        return None, is_quota


async def _get_all_tabs_dfs(spreadsheet) -> tuple[list, bool]:
    if not spreadsheet:
        return [], False
    try:
        def fetch():
            result = []
            for ws in spreadsheet.worksheets():
                result.append((ws.title, pd.DataFrame(ws.get_all_values())))
            return result
        return await asyncio.get_event_loop().run_in_executor(None, fetch), False
    except Exception as exc:
        print(f"[sheets_loader] Could not fetch all tabs: {exc}")
        import gspread
        is_quota = isinstance(exc, gspread.exceptions.APIError)
        return [], is_quota


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

async def load_all_from_sheets(storage: SheetStorage) -> dict:
    """
    Fetch every required DataFrame from Google Sheets and pass them to
    the standard loaders via the df= parameter path.
    """
    data = {}

    sales_id = storage.sheet_id("SHEET_SALES")
    hit, sales_ss, sales_mod = await _fetch_sheet_cached(storage, "SHEET_SALES", sales_id)
    
    copy_id = storage.sheet_id("SHEET_COPY_REPORT")
    hit, copy_ss, copy_mod = await _fetch_sheet_cached(storage, "SHEET_COPY_REPORT", copy_id)

    for m in MONTHS:
        key = m["key"]
        print(f"[sheets_loader] Loading {key.upper()} data from Google Sheets…")

        # ── Sales ──────────────────────────────────────────────────────────
        sales_df, s_err1 = await _get_tab_df(sales_ss, m["sales_tab"])
        prev_sales_df, s_err2 = await _get_tab_df(sales_ss, m["prev_sales_tab"]) if m["prev_sales_tab"] else (None, False)
        
        if sales_df is not None:
            sales = load_sales(df=sales_df, prev_df=prev_sales_df)
        else:
            sales = {"current": pd.DataFrame(), "prev": pd.DataFrame()}
            
        if not hit and not s_err1 and not s_err2:
            await set_sheet_metadata(sales_id, datetime.utcnow().isoformat(), sales_mod)

        # ── Projection + Activity Plan ─────────────────────────────────────
        proj_id = storage.sheet_id(m["projection_key"])
        hit, proj_ss, proj_mod = await _fetch_sheet_cached(storage, m["projection_key"], proj_id)
        proj_df, p_err1 = await _get_tab_df(proj_ss, "PROJECTION")
        activity_df, p_err2 = await _get_tab_df(proj_ss, "ACTIVITY PLAN")
        if proj_id and (proj_df is not None or activity_df is not None):
            projection = load_projection(df=proj_df, activity_df=activity_df)
            if not hit and not p_err1 and not p_err2:
                await set_sheet_metadata(proj_id, datetime.utcnow().isoformat(), proj_mod)
        else:
            projection = {"projection": None, "activity_plan": None, "missing_sheets": ["ALL"]}

        # ── Expense ────────────────────────────────────────────────────────
        exp_id = storage.sheet_id(m["expense_key"])
        hit, exp_ss, exp_mod = await _fetch_sheet_cached(storage, m["expense_key"], exp_id)
        if exp_ss:
            mr_df, e_err1 = await _get_tab_df(exp_ss, "MONEY RECEIVED")
            ae_df, e_err2 = await _get_tab_df(exp_ss, "ACTIVITY EXP.")
            oe_df, e_err3 = await _get_tab_df(exp_ss, "OTHER EXP.")
            expense = _load_expense_from_sheets(mr_df, ae_df, oe_df)
            if not hit and not (e_err1 or e_err2 or e_err3) and (mr_df is not None or ae_df is not None or oe_df is not None):
                await set_sheet_metadata(exp_id, datetime.utcnow().isoformat(), exp_mod)
        else:
            expense = {
                "activity_exp": None, "other_exp": None, "money_received": None,
                "opening_balance_fcfa": 0, "new_budget_fcfa": 0,
                "total_received_fcfa": 0, "total_spent_fcfa": 0,
                "balance_fcfa": 0, "missing_sheets": ["ALL"],
            }

        # ── Monthly Reports ────────────────────────────────────────────────
        monthly_id = storage.sheet_id(m["monthly_key"])
        hit, monthly_ss, monthly_mod = await _fetch_sheet_cached(storage, m["monthly_key"], monthly_id)
        if monthly_ss:
            del_df, m_err1 = await _get_tab_df(monthly_ss, "Delegates Reports")
            budget_df, m_err2 = await _get_tab_df(monthly_ss, "Budget Analysis")
            monthly = load_monthly_reports(df=del_df, budget_df=budget_df)
            if not hit and not (m_err1 or m_err2) and (del_df is not None or budget_df is not None):
                await set_sheet_metadata(monthly_id, datetime.utcnow().isoformat(), monthly_mod)
        else:
            monthly = {"delegates": None, "budget_analysis": None, "missing_sheets": ["ALL"]}

        # ── Copy Report ────────────────────────────────────────────────────
        copy_df, c_err = await _get_tab_df(copy_ss, m["copy_tab"])
        if copy_df is not None:
            copy = load_copy_report(df=copy_df)
            if not hit and not c_err:
                await set_sheet_metadata(copy_id, datetime.utcnow().isoformat(), copy_mod)
        else:
            copy = {
                "product_perf": pd.DataFrame(),
                "plan_activities": pd.DataFrame(),
                "actual_activities": pd.DataFrame(),
                "missing_sheets": ["ALL"],
            }

        # ── Tour Plan ──────────────────────────────────────────────────────
        tour_id = storage.sheet_id(m["tour_key"])
        hit, tour_ss, tour_mod = await _fetch_sheet_cached(storage, m["tour_key"], tour_id)
        tour_df, t_err = await _get_tab_df(tour_ss)
        if tour_df is not None:
            tour = load_tour_plan(df=tour_df)
            if not hit and not t_err: await set_sheet_metadata(tour_id, datetime.utcnow().isoformat(), tour_mod)
        else:
            tour = pd.DataFrame()

        # ── Visit Tracker ──────────────────────────────────────────────────
        visits_id = storage.sheet_id(m["visits_key"])
        hit, visits_ss, visits_mod = await _fetch_sheet_cached(storage, m["visits_key"], visits_id)
        if visits_ss:
            tab_dfs, v_err = await _get_all_tabs_dfs(visits_ss)
            sheets_arg = [(df, m["visits_label"]) for _, df in tab_dfs]
            visits = load_visit_tracker(sheets=sheets_arg)
            if not hit and tab_dfs and not v_err:
                await set_sheet_metadata(visits_id, datetime.utcnow().isoformat(), visits_mod)
        else:
            visits = pd.DataFrame(columns=["MR_ID", "MR", "Doctor", "Speciality", "Clinic", "Visit_Date", "Month"])

        data[key] = {
            "sales": sales, "projection": projection, "expense": expense,
            "monthly": monthly, "copy": copy, "tour": tour, "visits": visits,
        }
        print(f"[sheets_loader] {key.upper()} loaded OK.")

    return data


async def refresh_changed_from_sheets(storage: SheetStorage, existing_data: dict) -> tuple[dict, list[str]]:
    """
    Check all sheets for modifications. Only refetch the ones that changed.
    Updates existing_data in-place and returns (updated_data, changed_env_keys).
    """
    changed_env_keys = []
    
    # Check master sheets
    sales_id = storage.sheet_id("SHEET_SALES")
    hit, sales_ss, sales_mod = await _fetch_sheet_cached(storage, "SHEET_SALES", sales_id)
    if not hit and sales_id:
        changed_env_keys.append("SHEET_SALES")
        any_sales_success = False
        for m in MONTHS:
            sales_df, s_err = await _get_tab_df(sales_ss, m["sales_tab"])
            prev_sales_df, p_err = await _get_tab_df(sales_ss, m["prev_sales_tab"]) if m["prev_sales_tab"] else (None, False)
            existing_data[m["key"]]["sales"] = load_sales(df=sales_df, prev_df=prev_sales_df) if sales_df is not None else {"current": pd.DataFrame(), "prev": pd.DataFrame()}
            if sales_df is not None: any_sales_success = True
            if s_err or p_err: any_sales_success = False
        if any_sales_success:
            await set_sheet_metadata(sales_id, datetime.utcnow().isoformat(), sales_mod)

    copy_id = storage.sheet_id("SHEET_COPY_REPORT")
    hit, copy_ss, copy_mod = await _fetch_sheet_cached(storage, "SHEET_COPY_REPORT", copy_id)
    if not hit and copy_id:
        changed_env_keys.append("SHEET_COPY_REPORT")
        any_copy_success = False
        for m in MONTHS:
            copy_df, c_err = await _get_tab_df(copy_ss, m["copy_tab"])
            existing_data[m["key"]]["copy"] = load_copy_report(df=copy_df) if copy_df is not None else {"product_perf": pd.DataFrame(), "plan_activities": pd.DataFrame(), "actual_activities": pd.DataFrame(), "missing_sheets": ["ALL"]}
            if copy_df is not None: any_copy_success = True
            if c_err: any_copy_success = False
        if any_copy_success:
            await set_sheet_metadata(copy_id, datetime.utcnow().isoformat(), copy_mod)

    # Check monthly sheets
    for m in MONTHS:
        k = m["key"]
        
        proj_id = storage.sheet_id(m["projection_key"])
        hit, proj_ss, proj_mod = await _fetch_sheet_cached(storage, m["projection_key"], proj_id)
        if not hit and proj_id:
            changed_env_keys.append(m["projection_key"])
            proj_df, p_err1 = await _get_tab_df(proj_ss, "PROJECTION")
            activity_df, p_err2 = await _get_tab_df(proj_ss, "ACTIVITY PLAN")
            if proj_df is not None or activity_df is not None:
                existing_data[k]["projection"] = load_projection(df=proj_df, activity_df=activity_df)
                if not hit and not p_err1 and not p_err2:
                    await set_sheet_metadata(proj_id, datetime.utcnow().isoformat(), proj_mod)
                
        exp_id = storage.sheet_id(m["expense_key"])
        hit, exp_ss, exp_mod = await _fetch_sheet_cached(storage, m["expense_key"], exp_id)
        if not hit and exp_id:
            changed_env_keys.append(m["expense_key"])
            if exp_ss:
                mr_df, e_err1 = await _get_tab_df(exp_ss, "MONEY RECEIVED")
                ae_df, e_err2 = await _get_tab_df(exp_ss, "ACTIVITY EXP.")
                oe_df, e_err3 = await _get_tab_df(exp_ss, "OTHER EXP.")
                existing_data[k]["expense"] = _load_expense_from_sheets(mr_df, ae_df, oe_df)
                if not hit and not (e_err1 or e_err2 or e_err3) and (mr_df is not None or ae_df is not None or oe_df is not None):
                    await set_sheet_metadata(exp_id, datetime.utcnow().isoformat(), exp_mod)
                
        monthly_id = storage.sheet_id(m["monthly_key"])
        hit, monthly_ss, monthly_mod = await _fetch_sheet_cached(storage, m["monthly_key"], monthly_id)
        if not hit and monthly_id:
            changed_env_keys.append(m["monthly_key"])
            if monthly_ss:
                del_df, m_err1 = await _get_tab_df(monthly_ss, "Delegates Reports")
                budget_df, m_err2 = await _get_tab_df(monthly_ss, "Budget Analysis")
                existing_data[k]["monthly"] = load_monthly_reports(df=del_df, budget_df=budget_df)
                if not hit and not (m_err1 or m_err2) and (del_df is not None or budget_df is not None):
                    await set_sheet_metadata(monthly_id, datetime.utcnow().isoformat(), monthly_mod)
                
        tour_id = storage.sheet_id(m["tour_key"])
        hit, tour_ss, tour_mod = await _fetch_sheet_cached(storage, m["tour_key"], tour_id)
        if not hit and tour_id:
            changed_env_keys.append(m["tour_key"])
            tour_df, t_err = await _get_tab_df(tour_ss)
            existing_data[k]["tour"] = load_tour_plan(df=tour_df) if tour_df is not None else pd.DataFrame()
            if tour_df is not None and not hit and not t_err:
                await set_sheet_metadata(tour_id, datetime.utcnow().isoformat(), tour_mod)
            
        visits_id = storage.sheet_id(m["visits_key"])
        hit, visits_ss, visits_mod = await _fetch_sheet_cached(storage, m["visits_key"], visits_id)
        if not hit and visits_id:
            changed_env_keys.append(m["visits_key"])
            if visits_ss:
                tab_dfs, v_err = await _get_all_tabs_dfs(visits_ss)
                sheets_arg = [(df, m["visits_label"]) for _, df in tab_dfs]
                existing_data[k]["visits"] = load_visit_tracker(sheets=sheets_arg)
                if not hit and tab_dfs and not v_err:
                    await set_sheet_metadata(visits_id, datetime.utcnow().isoformat(), visits_mod)

    return existing_data, changed_env_keys


# ---------------------------------------------------------------------------
# Expense helper — runs the same parsing as load_expense but with pre-built DFs
# ---------------------------------------------------------------------------

def _load_expense_from_sheets(raw_mr, raw_ae, raw_oe):
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
