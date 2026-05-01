"""
Data loaders for IVC Pharma Executive Dashboard.
Adapted from the Streamlit version — no st.cache_data, no streamlit imports.
"""

import re
import pandas as pd
from io import BytesIO
import warnings
import logging

from constants import DISTRIBUTORS, FCFA_TO_EUR
from utils import safe_num
from name_map import (
    normalize_mr, mr_display_name,
    normalize_product, parse_multi_products,
    normalize_activity, activity_display_name,
    normalize_territory,
    normalize_doctor,
    build_doctor_index,
)

logger = logging.getLogger(__name__)

def _parse_visit_date(series: pd.Series) -> pd.Series:
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", 
        "%d/%m/%y", "%d-%b-%y", "%d-%b-%Y", "%d %b %Y"
    ]
    result = pd.Series(pd.NaT, index=series.index)
    unparsed_mask = series.notna() & (series != "")

    for fmt in formats:
        if not unparsed_mask.any():
            break
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(series[unparsed_mask], format=fmt, errors="coerce")
        mask_success = parsed.notna()
        result.update(parsed[mask_success])
        unparsed_mask &= ~mask_success

    if unparsed_mask.any():
        logger.info(f"[loaders] Falling back to dayfirst=True for {unparsed_mask.sum()} dates")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed_fallback = pd.to_datetime(series[unparsed_mask], errors="coerce", dayfirst=True)
        result.update(parsed_fallback)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# SAFE SHEET HELPER
# ─────────────────────────────────────────────────────────────────────────────

def safe_sheet(xl, sheet_name: str, header=None):
    """
    Tries to read `sheet_name` from an ExcelFile.
    Returns (DataFrame, None) on success.
    Returns (None, sheet_name) if the sheet doesn't exist.
    """
    if sheet_name not in xl.sheet_names:
        return None, sheet_name
    return pd.read_excel(xl, sheet_name=sheet_name, header=header), None


# ─────────────────────────────────────────────────────────────────────────────
# SALES
# ─────────────────────────────────────────────────────────────────────────────

def load_sales(file_bytes: bytes = None, current_sheet: str = None,
               prev_sheet: str = None, df: pd.DataFrame = None,
               prev_df: pd.DataFrame = None) -> dict:
    """
    Returns dict with keys 'current' and 'prev', each a DataFrame:
    columns: Product, Category, RATE,
             UBIPHARM/LABOREX_SALES, COPHARMED/LABOREX_SALES, TEDIS_SALES, DPCI_SALES,
             UBIPHARM/LABOREX_CLOSING, ...  TOTAL_SALES, TOTAL_VALUE_EUR

    Google Sheets path: pass df= (current tab) and optionally prev_df= (previous tab).
    Local Excel path:   pass file_bytes=, current_sheet=, prev_sheet=.
    """
    results = {}

    if df is not None:
        # ── Sheets path: DataFrames already built by caller ──
        pairs = [("current", df)]
        if prev_df is not None:
            pairs.append(("prev", prev_df))
        else:
            results["prev"] = pd.DataFrame()
    else:
        # ── Local Excel path ──
        xl = pd.ExcelFile(BytesIO(file_bytes))
        pairs = []
        if current_sheet in xl.sheet_names:
            pairs.append(("current", pd.read_excel(xl, sheet_name=current_sheet, header=None)))
        else:
            results["current"] = pd.DataFrame()
        if prev_sheet:
            if prev_sheet in xl.sheet_names:
                pairs.append(("prev", pd.read_excel(xl, sheet_name=prev_sheet, header=None)))
            else:
                results["prev"] = pd.DataFrame()
        else:
            results["prev"] = pd.DataFrame()

    for key, raw in pairs:
        rows = []
        current_category = "TABLET"
        for i, row in raw.iterrows():
            if i < 4:
                continue
            sr = row.iloc[1]
            # gspread returns strings — try converting
            if isinstance(sr, str):
                try:
                    sr = float(sr)
                except (ValueError, TypeError):
                    sr = float('nan')
            product = str(row.iloc[2]).strip()
            cat_label = str(row.iloc[0]).strip().upper()
            if "INJECTABLE" in cat_label:
                current_category = "INJECTABLE"
            elif "TABLET" in cat_label:
                current_category = "TABLET"
            if not isinstance(sr, (int, float)) or pd.isna(sr):
                continue
            if sr > 17:
                continue
            if "TOTAL" in str(product).upper() or str(product).upper() in ("NAN", ""):
                continue
            rate = safe_num(row.iloc[3])
            rec = {
                "Product": product,
                "Category": current_category,
                "RATE": rate,
            }
            base = 4
            for dist in DISTRIBUTORS:
                rec[f"{dist}_SALES"]   = safe_num(row.iloc[base])
                rec[f"{dist}_CLOSING"] = safe_num(row.iloc[base + 1])
                rec[f"{dist}_ORDER"]   = safe_num(row.iloc[base + 2])
                base += 3
            rec["TOTAL_SALES"] = sum(rec[f"{d}_SALES"] for d in DISTRIBUTORS)
            rec["TOTAL_VALUE_EUR"] = safe_num(row.iloc[-1])
            rows.append(rec)
        results[key] = pd.DataFrame(rows)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION & ACTIVITY PLAN
# ─────────────────────────────────────────────────────────────────────────────

def load_projection(file_bytes: bytes = None, df: pd.DataFrame = None,
                    activity_df: pd.DataFrame = None) -> dict:
    """
    Returns dict:
      'projection': DataFrame — Product, RATE, Target_Units, Target_Value_EUR
      'activity_plan': DataFrame — SN, Doctor, Hospital, Speciality, Delegate, Area, Activity, Amount_FCFA, Focus_Products

    Google Sheets path: pass df= (PROJECTION tab) and activity_df= (ACTIVITY PLAN tab).
    Local Excel path:   pass file_bytes= (workbook containing both sheets).
    """
    missing_sheets = []

    if df is not None or activity_df is not None:
        # ── Sheets path ──
        raw_p = df if df is not None else pd.DataFrame()
        raw_a = activity_df
    elif file_bytes is not None:
        # ── Local Excel path ──
        xl = pd.ExcelFile(BytesIO(file_bytes))
        raw_p, miss = safe_sheet(xl, "PROJECTION")
        if miss:
            missing_sheets.append(miss)
        raw_a = None
        activity_sheet_names = [s for s in xl.sheet_names if "ACTIVITY" in s.upper()]
        if not activity_sheet_names:
            missing_sheets.append("ACTIVITY PLAN")
        else:
            raw_a = pd.read_excel(xl, sheet_name=activity_sheet_names[0], header=None)
    else:
        return {"projection": None, "activity_plan": None, "missing_sheets": ["ALL"]}

    # ── PROJECTION ──
    proj_df = None
    if raw_p is not None:
        proj_rows = []
        for i, row in raw_p.iterrows():
            if i < 3:
                continue
            sn = row.iloc[0]
            if not isinstance(sn, (int, float)) or pd.isna(sn):
                try:
                    sn = float(sn)
                except (ValueError, TypeError):
                    continue
            if pd.isna(sn):
                continue
            product = str(row.iloc[1]).strip()
            if not product or product.upper() in ("NAN",):
                continue
            proj_rows.append({
                "Product": product,
                "RATE": safe_num(row.iloc[2]),
                "Target_Units": safe_num(row.iloc[3]),
                "Target_Value_EUR": safe_num(row.iloc[4]),
            })
        proj_df = pd.DataFrame(proj_rows)

    # ── ACTIVITY PLAN ──
    act_df = None
    if raw_a is None:
        if df is None:  # local path already appended above
            pass
        else:
            missing_sheets.append("ACTIVITY PLAN")
    else:
        act_rows = []
        for i, row in raw_a.iterrows():
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
            act_rows.append({
                "SN": int(sn),
                "Doctor": normalize_doctor(str(row.iloc[1]).strip()),
                "Hospital": str(row.iloc[2]).strip(),
                "Speciality": str(row.iloc[3]).strip(),
                "Delegate": normalize_mr(str(row.iloc[4]).strip()),
                "Area": normalize_territory(str(row.iloc[5]).strip()),
                "Activity": normalize_activity(str(row.iloc[6]).strip()),
                "Amount_FCFA": safe_num(row.iloc[7]),
                "Focus_Products": parse_multi_products(str(row.iloc[8]).strip()),
            })
        act_df = pd.DataFrame(act_rows)

    return {"projection": proj_df, "activity_plan": act_df, "missing_sheets": missing_sheets}


# ─────────────────────────────────────────────────────────────────────────────
# EXPENSE
# ─────────────────────────────────────────────────────────────────────────────

def load_expense(file_bytes: bytes = None, df: pd.DataFrame = None) -> dict:
    """
    Returns dict:
      'activity_exp': DataFrame
      'other_exp': DataFrame
      'money_received': DataFrame
      'total_received_fcfa', 'total_spent_fcfa', 'balance_fcfa'

    Google Sheets path: pass df= (workbook flattened into a single DataFrame,
      or None — see sheets_loader which calls loaders per sheet).
    Local Excel path:   pass file_bytes=.

    NOTE: For the Sheets path the expense workbook has 3 tabs; sheets_loader
    passes a single merged DataFrame via df= containing all rows with a
    __sheet__ sentinel column. This loader uses safe_sheet_from_df() below.
    """
    missing_sheets = []
    if df is not None:
        # ── Sheets path: df is the "MONEY RECEIVED" tab; other tabs passed separately ──
        # sheets_loader wraps each tab individually, so we receive one tab at a time.
        # We reuse the same parsing by converting the df into a fake xl that safe_sheet can use.
        raw_mr = df
        raw_ae = None
        raw_oe = None
    else:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        raw_mr_r, miss = safe_sheet(xl, "MONEY RECEIVED")
        if miss:
            missing_sheets.append(miss)
        raw_mr = raw_mr_r
        raw_ae_r, miss = safe_sheet(xl, "ACTIVITY EXP.")
        if miss:
            missing_sheets.append(miss)
        raw_ae = raw_ae_r
        raw_oe_r, miss = safe_sheet(xl, "OTHER EXP.")
        if miss:
            missing_sheets.append(miss)
        raw_oe = raw_oe_r

    # ── MONEY RECEIVED ──
    mr_df = None
    total_received_fcfa = 0
    total_spent_fcfa = 0
    balance_fcfa = 0
    opening_balance_fcfa = 0
    new_budget_fcfa = 0

    if raw_mr is not None:
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
            col5  = str(row.iloc[5]).upper() if len(row) > 5 else ""
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
    if raw_ae is not None:
        ae_rows = []
        for i, row in raw_ae.iterrows():
            if i < 2:
                continue
            sn = row.iloc[0]
            if not isinstance(sn, (int, float)) or pd.isna(sn):
                continue
            raw_resp = str(row.iloc[8]).strip()
            if "/" in raw_resp:
                mr_ids = ",".join(normalize_mr(p.strip()) for p in raw_resp.split("/"))
            else:
                mr_ids = normalize_mr(raw_resp)
            num_mrs = len([i.strip() for i in mr_ids.split(",") if i.strip()])
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
        ae_df["Activity"] = ae_df["Activity_ID"].apply(activity_display_name)

    # ── OTHER EXP ──
    oe_df = None
    if raw_oe is not None:
        oe_rows = []
        for i, row in raw_oe.iterrows():
            if i < 2:
                continue
            sn = row.iloc[0]
            if not isinstance(sn, (int, float)) or pd.isna(sn):
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


# ─────────────────────────────────────────────────────────────────────────────
# MONTHLY REPORTS
# ─────────────────────────────────────────────────────────────────────────────

def load_monthly_reports(file_bytes: bytes = None, df: pd.DataFrame = None,
                         budget_df: pd.DataFrame = None) -> dict:
    """
    Returns dict:
      'delegates': DataFrame
      'budget_analysis': DataFrame

    Google Sheets path: pass df= (Delegates Reports tab) and budget_df= (Budget Analysis tab).
    Local Excel path:   pass file_bytes=.
    """
    missing_sheets = []

    if df is not None or budget_df is not None:
        # ── Sheets path ──
        raw_d = df if df is not None else pd.DataFrame()
        raw_b = budget_df if budget_df is not None else pd.DataFrame()
    elif file_bytes is not None:
        # ── Local Excel path ──
        xl = pd.ExcelFile(BytesIO(file_bytes))
        raw_d, miss = safe_sheet(xl, "Delegates Reports")
        if miss:
            missing_sheets.append(miss)
        raw_b, miss = safe_sheet(xl, "Budget Analysis")
        if miss:
            missing_sheets.append(miss)
    else:
        return {"delegates": None, "budget_analysis": None, "missing_sheets": ["ALL"]}

    # ── DELEGATES REPORTS ──

    del_df = None
    if raw_d is not None and not raw_d.empty:
        del_rows = []
        for i, row in raw_d.iterrows():
            if i < 3:
                continue
            sn_raw = row.iloc[0]
            # gspread returns all values as strings — coerce to numeric
            try:
                sn = float(str(sn_raw).strip())
            except (ValueError, TypeError):
                continue
            if pd.isna(sn):
                continue
            delegate = str(row.iloc[1]).strip()
            if not delegate or any(k in delegate.upper() for k in ("TOTAL", "TARGET")):
                continue
            del_rows.append({
                "SN": int(sn),
                "Delegate": delegate,
                "Territory": str(row.iloc[2]).strip(),
                "NonPrescriber": safe_num(row.iloc[3]),
                "Prescriber": safe_num(row.iloc[4]),
                "DrsConverted": safe_num(row.iloc[5]),
                "TotalCalls": safe_num(row.iloc[6]),
                "PharmacyCalls": safe_num(row.iloc[7]),
                "DaysTarget": safe_num(row.iloc[8]),
                "DaysWorked": safe_num(row.iloc[9]),
                "AvgCallsPerDay": safe_num(row.iloc[10]),
                "TotalOrders": safe_num(row.iloc[11]),
                "CTC": safe_num(row.iloc[12]),
            })
        del_df = pd.DataFrame(del_rows)

    # ── BUDGET ANALYSIS ──
    ba_df = None
    if raw_b is not None and not raw_b.empty:
        ba_rows = []
        for i, row in raw_b.iterrows():
            if i < 2:
                continue
            doctor = str(row.iloc[0]).strip()
            if not doctor or doctor.upper() in ("NAN", "DR. NAME", ""):
                continue
            # Skip rows where col0 is purely numeric (malformed row)
            try:
                float(doctor)
                continue  # it's a number, not a doctor name
            except ValueError:
                pass
            ba_rows.append({
                "Doctor": normalize_doctor(doctor),
                "Area": normalize_territory(str(row.iloc[1]).strip()),
                "MR": normalize_mr(str(row.iloc[2]).strip()),
                "ActivityType": normalize_activity(str(row.iloc[3]).strip()),
                "Value_FCFA": safe_num(row.iloc[4]),
            })
        ba_df = pd.DataFrame(ba_rows)

    return {"delegates": del_df, "budget_analysis": ba_df, "missing_sheets": missing_sheets}


# ─────────────────────────────────────────────────────────────────────────────
# VISIT TRACKER
# ─────────────────────────────────────────────────────────────────────────────

def load_visit_tracker(files_and_months: list = None,
                       sheets: list = None) -> pd.DataFrame:
    """
    files_and_months: list of (file_bytes, month_label) tuples  — local Excel path.
    sheets:           list of (df, month_label) tuples          — Google Sheets path.

    Returns flat DataFrame: MR_ID, MR, Doctor, Speciality, Clinic, Visit_Date, Month
    """
    all_rows = []

    if sheets is not None:
        # ── Sheets path: each entry is (DataFrame, month_label) ──
        for raw, month_label in sheets:
            if raw is None or raw.empty:
                continue
            # The visit tracker has one tab per MR; gspread gives us one sheet at a
            # time. We treat the whole df as if it were a single sheet.
            if len(raw) < 4:
                continue
            try:
                mr_name = str(raw.iloc[0, 2]).strip()
            except Exception:
                mr_name = month_label
            if not mr_name or mr_name.upper() in ("NAN", ""):
                mr_name = month_label
            mr_id = normalize_mr(mr_name)

            header_row = raw.iloc[3]
            candidate_visit_cols = [c for c in raw.columns if "visit" in str(header_row[c]).lower()]
            for vc in candidate_visit_cols:
                raw[vc] = _parse_visit_date(raw[vc])
            visit_cols = [c for c in candidate_visit_cols if raw[vc].notna().any()]

            doc_col = next(
                (c for c in raw.columns if any(
                    kw in str(header_row[c]).upper()
                    for kw in ("NOM", "DR NAME", "DR. NAME", "DOCTOR NAME", "NAME OF")
                )),
                None
            )
            spec_col   = next((c for c in raw.columns if "SPEC"   in str(header_row[c]).upper()), None)
            clinic_col = next((c for c in raw.columns
                               if "CLINIC"   in str(header_row[c]).upper()
                               or "HOSPITAL" in str(header_row[c]).upper()
                               or "CSPS"     in str(header_row[c]).upper()), None)

            for i, row in raw.iterrows():
                if i <= 3:
                    continue
                doctor = str(row[doc_col]).strip() if doc_col is not None else ""
                if not doctor or doctor.upper() in ("NAN", "NOM /PERNOM", "DR NAME", "NAME", ""):
                    continue
                speciality = str(row[spec_col]).strip() if spec_col is not None else ""
                clinic     = str(row[clinic_col]).strip() if clinic_col is not None else ""
                for vc in visit_cols:
                    vdate = row[vc]
                    if pd.isna(vdate):
                        continue
                    all_rows.append({
                        "MR_ID":      mr_id,
                        "MR":         mr_display_name(mr_id) if mr_id not in ("UNKNOWN",) else mr_name,
                        "Doctor":     doctor,
                        "Speciality": speciality,
                        "Clinic":     clinic,
                        "Visit_Date": vdate,
                        "Month":      month_label,
                    })
        if all_rows:
            df = pd.DataFrame(all_rows)
            df["Visit_Date"] = pd.to_datetime(df["Visit_Date"])
            return df
        return pd.DataFrame(columns=["MR_ID","MR","Doctor","Speciality","Clinic","Visit_Date","Month"])

    # ── Local Excel path ──
    for file_bytes, month_label in (files_and_months or []):
        xl = pd.ExcelFile(BytesIO(file_bytes))
        for sheet in xl.sheet_names:
            raw = pd.read_excel(xl, sheet_name=sheet, header=None)
            if len(raw) < 4:
                continue
            try:
                mr_name = str(raw.iloc[0, 2]).strip()
            except Exception:
                mr_name = sheet
            if not mr_name or mr_name.upper() in ("NAN", ""):
                mr_name = sheet
            mr_id = normalize_mr(mr_name)

            header_row = raw.iloc[3]
            candidate_visit_cols = [c for c in raw.columns if "visit" in str(header_row[c]).lower()]
            for vc in candidate_visit_cols:
                raw[vc] = _parse_visit_date(raw[vc])
            visit_cols = [c for c in candidate_visit_cols if raw[c].notna().any()]

            doc_col = next(
                (c for c in raw.columns if any(
                    kw in str(header_row[c]).upper()
                    for kw in ("NOM", "DR NAME", "DR. NAME", "DOCTOR NAME", "NAME OF")
                )),
                None
            )
            spec_col   = next((c for c in raw.columns if "SPEC"   in str(header_row[c]).upper()), None)
            clinic_col = next((c for c in raw.columns
                               if "CLINIC"   in str(header_row[c]).upper()
                               or "HOSPITAL" in str(header_row[c]).upper()
                               or "CSPS"     in str(header_row[c]).upper()), None)

            for i, row in raw.iterrows():
                if i <= 3:
                    continue
                doctor = str(row[doc_col]).strip() if doc_col is not None else ""
                if not doctor or doctor.upper() in ("NAN", "NOM /PERNOM", "DR NAME", "NAME", ""):
                    continue
                speciality = str(row[spec_col]).strip() if spec_col is not None else ""
                clinic     = str(row[clinic_col]).strip() if clinic_col is not None else ""
                for vc in visit_cols:
                    vdate = row[vc]
                    if pd.isna(vdate):
                        continue
                    all_rows.append({
                        "MR_ID":      mr_id,
                        "MR":         mr_display_name(mr_id) if mr_id not in ("UNKNOWN",) else mr_name,
                        "Doctor":     doctor,
                        "Speciality": speciality,
                        "Clinic":     clinic,
                        "Visit_Date": vdate,
                        "Month":      month_label,
                    })
    if all_rows:
        df = pd.DataFrame(all_rows)
        df["Visit_Date"] = pd.to_datetime(df["Visit_Date"])
        return df
    return pd.DataFrame(columns=["MR_ID","MR","Doctor","Speciality","Clinic","Visit_Date","Month"])


# ─────────────────────────────────────────────────────────────────────────────
# COPY REPORT
# ─────────────────────────────────────────────────────────────────────────────

def load_copy_report(file_bytes: bytes = None, current_month: str = None,
                     df: pd.DataFrame = None) -> dict:
    """
    Returns dict:
      'product_perf': DataFrame
      'plan_activities': DataFrame
      'actual_activities': DataFrame

    Google Sheets path: pass df= (the correct month tab already selected by caller).
    Local Excel path:   pass file_bytes= and current_month= (used to find the right tab).
    """
    if df is not None:
        # ── Sheets path ──
        raw = df
    elif file_bytes is not None:
        # ── Local Excel path ──
        xl = pd.ExcelFile(BytesIO(file_bytes))
        sheet_name = f"{current_month[:3].lower()} 2026"
        if sheet_name not in [s.lower() for s in xl.sheet_names]:
            sheet_name = 0
        else:
            sheet_name = next(s for s in xl.sheet_names if s.lower() == sheet_name)
        raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)
    else:
        return {
            "product_perf": pd.DataFrame(),
            "plan_activities": pd.DataFrame(),
            "actual_activities": pd.DataFrame(),
            "missing_sheets": ["ALL"],
        }
    prod_rows, plan_rows, actual_rows = [], [], []

    for i, row in raw.iterrows():
        if i < 2:
            continue
        sn = row.iloc[0]
        if isinstance(sn, (int, float)) and not pd.isna(sn):
            product = str(row.iloc[1]).strip()
            if product and product.upper() not in ("NAN", "PRODUCTS"):
                prod_rows.append({
                    "Product": product,
                    "RATE": safe_num(row.iloc[2]),
                    "Target_Units": safe_num(row.iloc[3]),
                    "Achieved_Units": safe_num(row.iloc[4]),
                })

        doc_plan = str(row.iloc[5]).strip()
        if doc_plan and doc_plan.upper() not in ("NAN", "NAME OF DOCTOR", ""):
            plan_rows.append({
                "Doctor": normalize_doctor(doc_plan),
                "Hospital": str(row.iloc[6]).strip(),
                "Speciality": str(row.iloc[7]).strip(),
                "Activity": normalize_activity(str(row.iloc[8]).strip()),
                "Amount_FCFA": safe_num(row.iloc[9]),
            })

        doc_actual = str(row.iloc[10]).strip() if len(row) > 10 else ""
        if doc_actual and doc_actual.upper() not in ("NAN", "DOCTOR NAME", ""):
            actual_rows.append({
                "Doctor":     normalize_doctor(doc_actual),
                "Hospital":   str(row.iloc[11]).strip()  if len(row) > 11 else "",
                "Speciality": str(row.iloc[12]).strip()  if len(row) > 12 else "",
                "Activity":   normalize_activity(str(row.iloc[13]).strip()) if len(row) > 13 else "",
                "Amount_FCFA": safe_num(row.iloc[14])    if len(row) > 14 else 0,
                "Remarks":    str(row.iloc[15]).strip()  if len(row) > 15 else "",
                "VisitedBy":  normalize_mr(str(row.iloc[16]).strip()) if len(row) > 16 else "",
                "NoOfVisits": safe_num(row.iloc[17])     if len(row) > 17 else 0,
            })

    return {
        "product_perf": pd.DataFrame(prod_rows),
        "plan_activities": pd.DataFrame(plan_rows),
        "actual_activities": pd.DataFrame(actual_rows),
        "missing_sheets": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOUR PLAN
# ─────────────────────────────────────────────────────────────────────────────

def is_covered(plan, actual) -> bool:
    if not plan or not actual or str(plan).strip() in ('nan', '') or str(actual).strip() in ('nan', ''):
        return False
    p_up = str(plan).upper()
    a_up = str(actual).upper()
    stopwords = {"ZONE", "DE", "DU", "LA", "LE", "LES"}
    p_words = set(w for w in re.findall(r'[A-Z0-9]{3,}', p_up) if w not in stopwords)
    a_words = set(w for w in re.findall(r'[A-Z0-9]{3,}', a_up) if w not in stopwords)
    if not p_words or not a_words:
        return p_up == a_up
    return len(p_words & a_words) > 0


def load_tour_plan(file_bytes: bytes = None, df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Google Sheets path: pass df= (the single tour-plan sheet as a DataFrame).
    Local Excel path:   pass file_bytes=.
    """
    if df is not None:
        raw = df
    elif file_bytes is not None:
        raw = pd.read_excel(BytesIO(file_bytes), sheet_name=0, header=None)
    else:
        return pd.DataFrame()

    header_idx = 0
    for i, row in raw.iterrows():
        str_row = " ".join(str(v).upper() for v in row.values)
        if "DATE" in str_row and "NAME" in str_row and ("PLAN" in str_row or "AREA" in str_row):
            header_idx = i
            break

    if header_idx >= len(raw):
        return pd.DataFrame()

    header_row = raw.iloc[header_idx]
    date_col = name_col = joint_col = plan_col = actual_col = -1
    for c in raw.columns:
        val = str(header_row[c]).upper()
        if "DATE" in val:           date_col = c
        elif "NAME" in val:         name_col = c
        elif "JOINT" in val:        joint_col = c
        elif "TOUR PLAN" in val or "PLANNED" in val or "PLAN" in val:
            plan_col = c
        elif "WORKING" in val or "ACTUAL" in val or "AREA" in val:
            actual_col = c

    if name_col   == -1: name_col   = 2
    if plan_col   == -1: plan_col   = 4
    if actual_col == -1: actual_col = 5

    rows = []
    for i, row in raw.iterrows():
        if i <= header_idx:
            continue
        name = str(row[name_col]).strip() if name_col != -1 else ""
        if not name or name.upper() in ("NAN", "NAME", "NONE", ""):
            continue
        date   = row[date_col]   if date_col   != -1 else None
        plan   = str(row[plan_col]).strip()   if plan_col   != -1 else ""
        actual = str(row[actual_col]).strip() if actual_col != -1 else ""
        joint  = str(row[joint_col]).strip()  if joint_col  != -1 else ""
        rows.append({
            "Date":         pd.to_datetime(date, errors='coerce'),
            "MR":           normalize_mr(name),
            "Joint_Working": joint,
            "Planned_Area": plan,
            "Actual_Area":  actual,
            "Covered":      is_covered(plan, actual),
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD ALL DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_all_data(storage) -> dict:
    """Load all monthly and master data from storage backend."""
    data = {}

    # Master files
    sales_bytes = storage.get_file_bytes("IVC_Sales_Data_2026.xlsx")
    copy_bytes = storage.get_file_bytes("IVC_Copy_Of_Report_2026.xlsx")

    months = [
        # (key, folder, sales_sheet, prev_sales_sheet, copy_month_label)
        ("jan",  "Jan",   "JAN-26", None,      "Jan"),
        ("feb",  "Feb",   "FEB-26", "JAN-26",  "Feb"),
        ("mar",  "March", "MAR-26", "FEB-26",  "Mar"),
    ]

    # Actual filenames verified from directory listing:
    # Jan/: IVC_Projection_Activity_Jan_2026.xlsx, IVC_EXPENSE_&_ACTIVITY_SHEET_Jan-2026.xlsx,
    #        IVC_MONTHLY_REPORTS_Jan-2026.xlsx, IVC_TOUR_PLAN_VS_WORKING_AREA_Jan_2026.xlsx,
    #        IVC_Visit_Tracker_Jan_2026.xlsx
    # Feb/: IVC_Projection_Activity_Feb_2026.xlsx, IVC_EXPENSE_&_ACTIVITY_SHEET_Feb-2026.xlsx,
    #        IVC_MONTHLY_REPORTS_Feb-2026.xlsx, IVC_TOUR_PLAN_VS_WORKING_AREA_Feb_2026.xlsx,
    #        IVC_Visit_Tracker_Feb_2026.xlsx
    # March/: IVC_Projection_Activity_Mar_2026.xlsx, IVC_EXPENSE_&_ACTIVITY_SHEET_Mar-2026.xlsx,
    #          IVC_MONTHLY_REPORTS_Mar-2026.xlsx, IVC_TOUR_PLAN_VS_WORKING_AREA_Mar_2026.xlsx,
    #          IVC_Visit_Tracker_Mar_2026.xlsx

    expense_suffix = {
        "Jan": "Jan-2026",
        "Feb": "Feb-2026",
        "March": "Mar-2026",
    }
    proj_suffix = {
        "Jan": "Jan_2026",
        "Feb": "Feb_2026",
        "March": "Mar_2026",
    }
    visit_suffix = {
        "Jan": "Jan_2026",
        "Feb": "Feb_2026",
        "March": "Mar_2026",
    }
    tour_suffix = {
        "Jan": "Jan_2026",
        "Feb": "Feb_2026",
        "March": "Mar_2026",
    }
    monthly_suffix = {
        "Jan": "Jan-2026",
        "Feb": "Feb-2026",
        "March": "Mar-2026",
    }

    for key, folder, sales_sheet, prev_sheet, copy_label in months:
        base = f"{folder}/"
        esuf = expense_suffix[folder]
        psuf = proj_suffix[folder]
        vsuf = visit_suffix[folder]
        tsuf = tour_suffix[folder]
        msuf = monthly_suffix[folder]

        try:
            proj_bytes = storage.get_file_bytes(f"{base}IVC_Projection_Activity_{psuf}.xlsx")
        except Exception:
            proj_bytes = None

        try:
            exp_bytes = storage.get_file_bytes(f"{base}IVC_EXPENSE_&_ACTIVITY_SHEET_{esuf}.xlsx")
        except Exception:
            exp_bytes = None

        try:
            monthly_bytes = storage.get_file_bytes(f"{base}IVC_MONTHLY_REPORTS_{msuf}.xlsx")
        except Exception:
            monthly_bytes = None

        try:
            tour_bytes = storage.get_file_bytes(f"{base}IVC_TOUR_PLAN_VS_WORKING_AREA_{tsuf}.xlsx")
        except Exception:
            tour_bytes = None

        try:
            visit_bytes = storage.get_file_bytes(f"{base}IVC_Visit_Tracker_{vsuf}.xlsx")
        except Exception:
            visit_bytes = None

        data[key] = {
            "sales":     load_sales(sales_bytes, sales_sheet, prev_sheet),
            "projection": load_projection(proj_bytes) if proj_bytes else {"projection": None, "activity_plan": None, "missing_sheets": ["ALL"]},
            "expense":   load_expense(exp_bytes) if exp_bytes else {"activity_exp": None, "other_exp": None, "money_received": None, "total_received_fcfa": 0, "total_spent_fcfa": 0, "balance_fcfa": 0, "missing_sheets": ["ALL"]},
            "monthly":   load_monthly_reports(monthly_bytes) if monthly_bytes else {"delegates": None, "budget_analysis": None, "missing_sheets": ["ALL"]},
            "copy":      load_copy_report(copy_bytes, copy_label),
            "tour":      load_tour_plan(tour_bytes) if tour_bytes else pd.DataFrame(),
            "visits":    load_visit_tracker([(visit_bytes, key[:3])]) if visit_bytes else pd.DataFrame(),
        }

    return data
