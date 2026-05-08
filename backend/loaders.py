"""
loaders.py — IVC Pharma Executive Dashboard data loaders.

All column lookups use header names, never positional indices.
Both paths supported: file_bytes= (local Excel) and df= (Google Sheets pre-fetched DataFrame).

NOTE: sheets_loader.py fetches tab DataFrames using old tab names ("Delegates Reports",
"Budget Analysis", "ACTIVITY EXP.", "OTHER EXP."). Those need updating to match the
actual sheet names in the new files ("DELEGATES", "BUDGET ANALYSIS", "ACTIVITY EXPENSES",
"OTHER EXPENSES") when Google Sheets mode is used.
"""

import re
import logging
import warnings
import pandas as pd
from io import BytesIO

from constants import DISTRIBUTORS, FCFA_TO_EUR
from utils import safe_num
from name_map import (
    normalize_mr, mr_display_name,
    normalize_product, product_display_name, parse_multi_products,
    normalize_activity, activity_display_name,
    normalize_territory, normalize_doctor,
    build_doctor_index,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Column-header utilities
# ─────────────────────────────────────────────────────────────────────────────

def _norm_hdr(val) -> str:
    """Normalize a header cell to a lowercase, stripped, newline-collapsed key."""
    return str(val).strip().replace("\n", " ").lower()


def _parse_header(df: pd.DataFrame, header_row_idx: int) -> dict:
    """Return {normalized_header: column_label} for every non-NaN cell in the header row."""
    result = {}
    row = df.iloc[header_row_idx]
    for col_label, val in row.items():
        if pd.isna(val):
            continue
        result[_norm_hdr(val)] = col_label
    return result


def _find_col(col_map: dict, *candidates):
    """Return the first column label matching any candidate key (case-insensitive). None if absent."""
    for c in candidates:
        k = _norm_hdr(c)
        if k in col_map:
            return col_map[k]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Visit date parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_visit_date(series: pd.Series) -> pd.Series:
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
        "%d/%m/%y", "%d-%b-%y", "%d-%b-%Y", "%d %b %Y",
    ]
    result = pd.Series(pd.NaT, index=series.index)
    unparsed = series.notna() & (series.astype(str).str.strip() != "")
    for fmt in formats:
        if not unparsed.any():
            break
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(series[unparsed], format=fmt, errors="coerce")
        ok = parsed.notna()
        result.update(parsed[ok])
        unparsed &= ~ok
    if unparsed.any():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fallback = pd.to_datetime(series[unparsed], errors="coerce", dayfirst=True)
        result.update(fallback)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Safe sheet helper
# ─────────────────────────────────────────────────────────────────────────────

def safe_sheet(xl, sheet_name: str, header=None):
    if sheet_name not in xl.sheet_names:
        return None, sheet_name
    return pd.read_excel(xl, sheet_name=sheet_name, header=header), None


# ─────────────────────────────────────────────────────────────────────────────
# Canonical product rates  (built once from the Sales file)
# ─────────────────────────────────────────────────────────────────────────────

def build_canonical_rates(file_bytes: bytes) -> dict:
    """Return {product_id: rate_eur} from the first sheet of the Sales workbook."""
    rates = {}
    try:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        if not xl.sheet_names:
            return rates
        df = pd.read_excel(xl, sheet_name=xl.sheet_names[0], header=None)
        cols = _parse_header(df, 1)
        prod_col = _find_col(cols, "product")
        rate_col = _find_col(cols, "rate (eur)", "rate\n(eur)")
        if prod_col is None or rate_col is None:
            return rates
        for i, row in df.iterrows():
            if i < 2:
                continue
            raw_prod = str(row.iloc[prod_col]).strip()
            if not raw_prod or raw_prod.upper() in ("NAN", "PRODUCT"):
                continue
            pid = normalize_product(raw_prod)
            if pid not in ("UNKNOWN", "EXCLUDED"):
                rates[pid] = safe_num(row.iloc[rate_col])
    except Exception as exc:
        logger.warning(f"[loaders] build_canonical_rates failed: {exc}")
    return rates


# ─────────────────────────────────────────────────────────────────────────────
# Sales Outcome parser  ("OMECID:270 | STURIX:6" → list of dicts)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_sales_outcome(raw, canonical_rates: dict) -> list:
    if raw is None:
        return []
    if isinstance(raw, float) and pd.isna(raw):
        return []
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return []
    results = []
    for part in text.split("|"):
        part = part.strip()
        if ":" not in part:
            continue
        prod_raw, qty_str = part.split(":", 1)
        pid = normalize_product(prod_raw.strip())
        if pid in ("UNKNOWN", "EXCLUDED"):
            logger.debug(f"[loaders] sales_outcome: unrecognized product {prod_raw.strip()!r}")
            continue
        try:
            qty = int(float(qty_str.strip()))
        except (ValueError, TypeError):
            continue
        rate = canonical_rates.get(pid, 0.0)
        results.append({
            "product_id": pid,
            "product_name": product_display_name(pid),
            "qty": qty,
            "rate_eur": rate,
            "eur_value": round(qty * rate, 2),
        })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Balance validation
# ─────────────────────────────────────────────────────────────────────────────

def _validate_balances(month_label: str, opening: float, closing: float,
                        prev_closing: "float | None") -> None:
    if prev_closing is not None and abs(opening - prev_closing) > 1:
        logger.warning(
            "[DataWarning] %s: opening balance %.0f FCFA != previous closing %.0f FCFA (diff %+.0f)",
            month_label, opening, prev_closing, opening - prev_closing,
        )
    if closing < 0:
        logger.warning(
            "[DataWarning] %s: closing balance is negative (%.0f FCFA)",
            month_label, closing,
        )


# ─────────────────────────────────────────────────────────────────────────────
# SALES
# ─────────────────────────────────────────────────────────────────────────────

# Maps from the Excel column prefix (after normalisation) to the DISTRIBUTORS constant
_DIST_PREFIX = {
    "ubipharm":  "UBIPHARM/LABOREX",
    "copharmed": "COPHARMED/LABOREX",
    "tedis":     "TEDIS",
    "dpci":      "DPCI",
}


def load_sales(file_bytes: bytes = None, current_sheet: str = None,
               prev_sheet: str = None, df: pd.DataFrame = None,
               prev_df: pd.DataFrame = None) -> dict:
    """
    Returns {'current': DataFrame, 'prev': DataFrame}.
    Columns: Product, Category, RATE, {DIST}_SALES/CLOSING/ORDER, TOTAL_SALES, TOTAL_VALUE_EUR.
    """
    results = {}

    if df is not None:
        pairs = [("current", df)]
        if prev_df is not None:
            pairs.append(("prev", prev_df))
        else:
            results["prev"] = pd.DataFrame()
    else:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        pairs = []
        for key, sheet in [("current", current_sheet), ("prev", prev_sheet)]:
            if not sheet:
                results[key] = pd.DataFrame()
                continue
            if sheet in xl.sheet_names:
                pairs.append((key, pd.read_excel(xl, sheet_name=sheet, header=None)))
            else:
                results[key] = pd.DataFrame()

    for key, raw in pairs:
        cols = _parse_header(raw, 1)
        cat_col  = _find_col(cols, "category")
        sno_col  = _find_col(cols, "s.no")
        prod_col = _find_col(cols, "product")
        rate_col = _find_col(cols, "rate (eur)", "rate\n(eur)")
        tval_col = _find_col(cols, "total value\n(eur)", "total value (eur)")

        # Detect per-distributor sales/closing/order columns by header prefix
        dist_cols: dict[str, dict] = {}
        for hdr_key, col_label in cols.items():
            for prefix, dist_name in _DIST_PREFIX.items():
                if hdr_key.startswith(prefix + " "):
                    suffix = hdr_key[len(prefix):].strip().lower()
                    entry = dist_cols.setdefault(dist_name, {})
                    if "sales" in suffix:
                        entry["sales"] = col_label
                    elif "closing" in suffix:
                        entry["closing"] = col_label
                    elif "order" in suffix:
                        entry["order"] = col_label

        current_category = "TABLET"
        rows = []
        for i, row in raw.iterrows():
            if i < 2:
                continue
            # Carry forward category
            cat_raw = str(row.iloc[cat_col]).strip().upper() if cat_col is not None else ""
            if "INJECTABLE" in cat_raw:
                current_category = "INJECTABLE"
            elif "TABLET" in cat_raw:
                current_category = "TABLET"

            sn = row.iloc[sno_col] if sno_col is not None else None
            if isinstance(sn, str):
                try:
                    sn = float(sn)
                except (ValueError, TypeError):
                    sn = float("nan")
            if not isinstance(sn, (int, float)) or pd.isna(sn) or sn > 17:
                continue

            product = str(row.iloc[prod_col]).strip() if prod_col is not None else ""
            if not product or product.upper() in ("NAN", "PRODUCT", "TOTAL"):
                continue

            rate = safe_num(row.iloc[rate_col]) if rate_col is not None else 0.0
            rec = {"Product": product, "Category": current_category, "RATE": rate}
            for dist in DISTRIBUTORS:
                dc = dist_cols.get(dist, {})
                rec[f"{dist}_SALES"]   = safe_num(row.iloc[dc["sales"]])   if "sales"   in dc else 0.0
                rec[f"{dist}_CLOSING"] = safe_num(row.iloc[dc["closing"]]) if "closing" in dc else 0.0
                rec[f"{dist}_ORDER"]   = safe_num(row.iloc[dc["order"]])   if "order"   in dc else 0.0
            rec["TOTAL_SALES"]     = sum(rec[f"{d}_SALES"] for d in DISTRIBUTORS)
            rec["TOTAL_VALUE_EUR"] = safe_num(row.iloc[tval_col]) if tval_col is not None else 0.0
            rows.append(rec)

        results[key] = pd.DataFrame(rows)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION & ACTIVITY PLAN
# ─────────────────────────────────────────────────────────────────────────────

def load_projection(file_bytes: bytes = None, df: pd.DataFrame = None,
                    activity_df: pd.DataFrame = None,
                    canonical_rates: dict = None) -> dict:
    """
    Returns {'projection': DataFrame, 'activity_plan': DataFrame, 'missing_sheets': list}.

    Activity Plan columns: SN, Doctor, RowType, Hospital, Speciality, Delegate, Area,
                           Activity, Amount_FCFA, Focus_Products, Category.
    RowType column is absent in January — defaults to 'DATA' when missing.
    Product rates in Projection are overridden by canonical_rates when provided.
    """
    canonical_rates = canonical_rates or {}
    missing_sheets = []

    if df is not None or activity_df is not None:
        raw_p = df if df is not None else pd.DataFrame()
        raw_a = activity_df
    elif file_bytes is not None:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        raw_p, miss = safe_sheet(xl, "PROJECTION")
        if miss:
            missing_sheets.append(miss)
        act_sheets = [s for s in xl.sheet_names if "ACTIVITY" in s.upper()]
        if not act_sheets:
            missing_sheets.append("ACTIVITY PLAN")
            raw_a = None
        else:
            raw_a = pd.read_excel(xl, sheet_name=act_sheets[0], header=None)
    else:
        return {"projection": None, "activity_plan": None, "missing_sheets": ["ALL"]}

    # ── PROJECTION ──────────────────────────────────────────────────────────
    proj_df = None
    if raw_p is not None and not raw_p.empty:
        cols     = _parse_header(raw_p, 1)
        sno_col  = _find_col(cols, "s.no")
        prod_col = _find_col(cols, "product")
        cat_col  = _find_col(cols, "category")
        rate_col = _find_col(cols, "rate (eur)", "rate\n(eur)")
        tu_col   = _find_col(cols, "target units")
        tv_col   = _find_col(cols, "target value (eur)", "target value\n(eur)")

        proj_rows = []
        for i, row in raw_p.iterrows():
            if i < 2:
                continue
            try:
                sn = float(str(row.iloc[sno_col]).strip()) if sno_col is not None else float("nan")
            except (ValueError, TypeError):
                continue
            if pd.isna(sn):
                continue
            product = str(row.iloc[prod_col]).strip() if prod_col is not None else ""
            if not product or product.upper() in ("NAN",):
                continue
            # Skip info rows (e.g. the January placeholder)
            if product.startswith("ℹ") or product.startswith("  ℹ"):
                continue

            pid = normalize_product(product)
            # Always prefer canonical rate; fall back to sheet value for unknown products
            if pid not in ("UNKNOWN", "EXCLUDED") and pid in canonical_rates:
                rate = canonical_rates[pid]
            else:
                rate = safe_num(row.iloc[rate_col]) if rate_col is not None else 0.0

            target_units = safe_num(row.iloc[tu_col]) if tu_col is not None else 0.0
            proj_rows.append({
                "Product":         product,
                "Category":        str(row.iloc[cat_col]).strip() if cat_col is not None else "",
                "RATE":            rate,
                "Target_Units":    target_units,
                "Target_Value_EUR": round(target_units * rate, 2),
            })
        proj_df = pd.DataFrame(proj_rows)

    # ── ACTIVITY PLAN ────────────────────────────────────────────────────────
    act_df = None
    if raw_a is not None and not raw_a.empty:
        cols         = _parse_header(raw_a, 1)
        sno_col      = _find_col(cols, "s.no")
        doc_col      = _find_col(cols, "doctor / contact", "doctor/contact")
        rowtype_col  = _find_col(cols, "row type")          # absent in January
        hosp_col     = _find_col(cols, "hospital / clinic", "hospital/clinic")
        spec_col     = _find_col(cols, "speciality", "specialty")
        del_col      = _find_col(cols, "delegate")
        area_col     = _find_col(cols, "area")
        act_col      = _find_col(cols, "activity type")
        amt_col      = _find_col(cols, "amount (fcfa)", "amount(fcfa)")
        fprod_col    = _find_col(cols, "focus products", "focus product")
        cat_col      = _find_col(cols, "category")

        act_rows = []
        for i, row in raw_a.iterrows():
            if i < 2:
                continue
            # S.No must be numeric
            if sno_col is not None:
                try:
                    sn = int(float(str(row.iloc[sno_col]).strip()))
                except (ValueError, TypeError):
                    continue
            else:
                sn = i

            doctor = str(row.iloc[doc_col]).strip() if doc_col is not None else ""
            if not doctor or doctor.upper() in ("NAN", "DOCTOR / CONTACT", ""):
                continue
            if doctor.lstrip().startswith("ℹ"):
                continue  # placeholder info row

            row_type = "DATA"
            if rowtype_col is not None:
                rt_raw = row.iloc[rowtype_col]
                if not (isinstance(rt_raw, float) and pd.isna(rt_raw)):
                    row_type = str(rt_raw).strip()

            act_rows.append({
                "SN":           sn,
                "Doctor":       normalize_doctor(doctor),
                "RowType":      row_type,
                "Hospital":     str(row.iloc[hosp_col]).strip()  if hosp_col  is not None else "",
                "Speciality":   str(row.iloc[spec_col]).strip()  if spec_col  is not None else "",
                "Delegate":     normalize_mr(str(row.iloc[del_col]).strip())      if del_col  is not None else "UNKNOWN",
                "Area":         normalize_territory(str(row.iloc[area_col]).strip()) if area_col is not None else "UNKNOWN",
                "Activity":     normalize_activity(str(row.iloc[act_col]).strip()) if act_col  is not None else "UNKNOWN",
                "Amount_FCFA":  safe_num(row.iloc[amt_col])   if amt_col  is not None else 0.0,
                "Focus_Products": parse_multi_products(str(row.iloc[fprod_col]).strip()) if fprod_col is not None else "",
                "Category":     str(row.iloc[cat_col]).strip() if cat_col  is not None else "",
            })
        act_df = pd.DataFrame(act_rows) if act_rows else pd.DataFrame()

    return {"projection": proj_df, "activity_plan": act_df, "missing_sheets": missing_sheets}


# ─────────────────────────────────────────────────────────────────────────────
# EXPENSE
# ─────────────────────────────────────────────────────────────────────────────

def load_expense(file_bytes: bytes = None, df: pd.DataFrame = None,
                 month_label: str = "",
                 prev_closing_fcfa: "float | None" = None,
                 canonical_rates: dict = None) -> dict:
    """
    Returns dict with keys:
      activity_exp, other_exp, money_received (DataFrames),
      opening_balance_fcfa, new_budget_fcfa, total_received_fcfa,
      total_spent_fcfa, balance_fcfa, missing_sheets.

    Activity Expenses: Sales Outcome column is optional (absent in March).
    Negative closing balance is loaded as-is and logged as DataWarning.
    """
    canonical_rates = canonical_rates or {}
    missing_sheets = []

    if df is not None:
        # Sheets path: only MONEY RECEIVED tab passed directly
        raw_mr, raw_ae, raw_oe = df, None, None
    else:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        raw_mr, miss = safe_sheet(xl, "MONEY RECEIVED")
        if miss:
            missing_sheets.append(miss)
        raw_ae = None
        for name in ("ACTIVITY EXPENSES", "ACTIVITY EXP."):
            if name in xl.sheet_names:
                raw_ae = pd.read_excel(xl, sheet_name=name, header=None)
                break
        if raw_ae is None:
            missing_sheets.append("ACTIVITY EXPENSES")
        raw_oe = None
        for name in ("OTHER EXPENSES", "OTHER EXP."):
            if name in xl.sheet_names:
                raw_oe = pd.read_excel(xl, sheet_name=name, header=None)
                break
        if raw_oe is None:
            missing_sheets.append("OTHER EXPENSES")

    # ── MONEY RECEIVED ──────────────────────────────────────────────────────
    mr_df = None
    opening_balance_fcfa = 0.0
    new_budget_fcfa      = 0.0
    total_received_fcfa  = 0.0
    total_spent_fcfa     = 0.0
    balance_fcfa         = 0.0

    if raw_mr is not None:
        cols         = _parse_header(raw_mr, 1)
        type_col     = _find_col(cols, "type")
        date_col     = _find_col(cols, "date")
        desc_col     = _find_col(cols, "source / description", "source/description", "description")
        amt_fcfa_col = _find_col(cols, "amount (fcfa)", "amount(fcfa)")
        amt_eur_col  = _find_col(cols, "amount (eur)",  "amount(eur)")
        notes_col    = _find_col(cols, "notes")

        mr_rows = []
        for i, row in raw_mr.iterrows():
            if i < 2:
                continue
            type_val = str(row.iloc[type_col]).strip().upper() if type_col is not None else ""
            if not type_val or type_val in ("NAN", "TYPE"):
                continue
            amt = safe_num(row.iloc[amt_fcfa_col]) if amt_fcfa_col is not None else 0.0

            if "OPENING" in type_val:
                opening_balance_fcfa = amt
            elif "RECEIVED" in type_val:
                new_budget_fcfa = amt
            elif "SPENT" in type_val:
                total_spent_fcfa = amt
            elif "BALANCE" in type_val:
                balance_fcfa = amt

            date_raw = row.iloc[date_col] if date_col is not None else None
            date_parsed = pd.to_datetime(date_raw, errors="coerce") if date_raw is not None else pd.NaT

            if type_val not in ("SPENT", "BALANCE"):
                mr_rows.append({
                    "Type":        type_val,
                    "Date":        date_parsed,
                    "Source":      str(row.iloc[desc_col]).strip() if desc_col is not None else "",
                    "Amount_FCFA": amt,
                    "Amount_EUR":  safe_num(row.iloc[amt_eur_col]) if amt_eur_col is not None
                                   else round(amt / FCFA_TO_EUR, 2),
                    "Notes":       str(row.iloc[notes_col]).strip() if notes_col is not None else "",
                })
        mr_df = pd.DataFrame(mr_rows)
        total_received_fcfa = opening_balance_fcfa + new_budget_fcfa
        _validate_balances(month_label, opening_balance_fcfa, balance_fcfa, prev_closing_fcfa)

    # ── ACTIVITY EXPENSES ────────────────────────────────────────────────────
    ae_df = None
    if raw_ae is not None:
        cols        = _parse_header(raw_ae, 1)
        sno_col     = _find_col(cols, "s.no")
        doc_col     = _find_col(cols, "doctor / contact", "doctor/contact")
        hosp_col    = _find_col(cols, "hospital / clinic", "hospital/clinic")
        spec_col    = _find_col(cols, "speciality", "specialty")
        act_col     = _find_col(cols, "activity type")
        prod_col    = _find_col(cols, "products")
        amt_col     = _find_col(cols, "amount (fcfa)", "amount(fcfa)")
        contact_col = _find_col(cols, "contact number", "contact")
        resp_col    = _find_col(cols, "responsible")
        outcome_col = _find_col(cols, "sales outcome")   # absent in March
        visits_col  = _find_col(cols, "no. of visits", "no of visits", "visits")  # absent in March

        ae_rows = []
        for i, row in raw_ae.iterrows():
            if i < 2:
                continue
            sn = row.iloc[sno_col] if sno_col is not None else None
            if not isinstance(sn, (int, float)) or pd.isna(sn):
                try:
                    sn = float(str(sn).strip())
                except (ValueError, TypeError):
                    continue
            if pd.isna(sn):
                continue

            raw_resp = str(row.iloc[resp_col]).strip() if resp_col is not None else ""
            if "/" in raw_resp:
                mr_ids = ",".join(normalize_mr(p.strip()) for p in raw_resp.split("/"))
            else:
                mr_ids = normalize_mr(raw_resp)
            num_mrs = max(1, len([x for x in mr_ids.split(",") if x.strip()]))

            amount_fcfa = safe_num(row.iloc[amt_col]) if amt_col is not None else 0.0

            outcome_raw   = row.iloc[outcome_col] if outcome_col is not None else None
            outcome_parsed = _parse_sales_outcome(outcome_raw, canonical_rates)

            visits_raw = row.iloc[visits_col] if visits_col is not None else None
            num_visits_v = safe_num(visits_raw)
            num_visits = 0 if pd.isna(num_visits_v) else int(num_visits_v)

            ae_rows.append({
                "SN":              int(sn),
                "Doctor":          normalize_doctor(str(row.iloc[doc_col]).strip())  if doc_col  is not None else "",
                "Hospital":        str(row.iloc[hosp_col]).strip()                   if hosp_col is not None else "",
                "Speciality":      str(row.iloc[spec_col]).strip()                   if spec_col is not None else "",
                "Activity":        str(row.iloc[act_col]).strip()                    if act_col  is not None else "",
                "Activity_ID":     normalize_activity(str(row.iloc[act_col]).strip()) if act_col is not None else "UNKNOWN",
                "Products":        parse_multi_products(str(row.iloc[prod_col]).strip()) if prod_col is not None else "",
                "Amount_FCFA":     amount_fcfa,
                "Amount_EUR":      round(amount_fcfa / FCFA_TO_EUR, 2),
                "Amount_FCFA_Share": amount_fcfa / num_mrs,
                "Contact":         str(row.iloc[contact_col]).strip()                if contact_col is not None else "",
                "Responsible":     raw_resp,
                "MR_IDs":          mr_ids,
                "Num_MRs":         num_mrs,
                "Sales_Outcome":   outcome_parsed,
                "Sales_Outcome_EUR": sum(o["eur_value"] for o in outcome_parsed),
                "Num_Visits":      num_visits,
            })
        ae_df = pd.DataFrame(ae_rows)
        if not ae_df.empty:
            ae_df["Activity"] = ae_df["Activity_ID"].apply(activity_display_name)

    # ── OTHER EXPENSES ───────────────────────────────────────────────────────
    oe_df = None
    if raw_oe is not None:
        cols         = _parse_header(raw_oe, 1)
        sno_col      = _find_col(cols, "s.no")
        country_col  = _find_col(cols, "country")
        details_col  = _find_col(cols, "details")
        amt_fcfa_col = _find_col(cols, "amount (fcfa)", "amount(fcfa)")
        amt_eur_col  = _find_col(cols, "amount (eur)",  "amount(eur)")
        comments_col = _find_col(cols, "comments")
        cat_col      = _find_col(cols, "category")

        oe_rows = []
        for i, row in raw_oe.iterrows():
            if i < 2:
                continue
            sn = row.iloc[sno_col] if sno_col is not None else None
            if not isinstance(sn, (int, float)) or pd.isna(sn):
                try:
                    sn = float(str(sn).strip())
                except (ValueError, TypeError):
                    continue
            if pd.isna(sn):
                continue
            amt_fcfa = safe_num(row.iloc[amt_fcfa_col]) if amt_fcfa_col is not None else 0.0
            if amt_fcfa == 0:
                continue
            oe_rows.append({
                "SN":          int(sn),
                "Country":     str(row.iloc[country_col]).strip()  if country_col  is not None else "",
                "Details":     str(row.iloc[details_col]).strip()  if details_col  is not None else "",
                "Amount_FCFA": amt_fcfa,
                "Amount_EUR":  safe_num(row.iloc[amt_eur_col]) if amt_eur_col is not None
                               else round(amt_fcfa / FCFA_TO_EUR, 2),
                "Comments":    str(row.iloc[comments_col]).strip() if comments_col is not None else "",
                "Category":    str(row.iloc[cat_col]).strip()      if cat_col      is not None else "",
            })
        oe_df = pd.DataFrame(oe_rows)

    return {
        "activity_exp":          ae_df,
        "other_exp":             oe_df,
        "money_received":        mr_df,
        "opening_balance_fcfa":  opening_balance_fcfa,
        "new_budget_fcfa":       new_budget_fcfa,
        "total_received_fcfa":   total_received_fcfa,
        "total_spent_fcfa":      total_spent_fcfa,
        "balance_fcfa":          balance_fcfa,
        "missing_sheets":        missing_sheets,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MONTHLY REPORTS
# ─────────────────────────────────────────────────────────────────────────────

def load_monthly_reports(file_bytes: bytes = None, df: pd.DataFrame = None,
                         budget_df: pd.DataFrame = None) -> dict:
    """
    Returns {'delegates': DataFrame, 'budget_analysis': DataFrame, 'missing_sheets': list}.

    Budget Analysis: S.No is NaN for most rows in March; all rows with a valid doctor are included.
    """
    missing_sheets = []

    if df is not None or budget_df is not None:
        raw_d = df           if df         is not None else pd.DataFrame()
        raw_b = budget_df    if budget_df  is not None else pd.DataFrame()
    elif file_bytes is not None:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        raw_d = None
        for name in ("DELEGATES", "Delegates Reports", "Delegates"):
            if name in xl.sheet_names:
                raw_d = pd.read_excel(xl, sheet_name=name, header=None)
                break
        if raw_d is None:
            missing_sheets.append("DELEGATES")
            raw_d = pd.DataFrame()
        raw_b = None
        for name in ("BUDGET ANALYSIS", "Budget Analysis"):
            if name in xl.sheet_names:
                raw_b = pd.read_excel(xl, sheet_name=name, header=None)
                break
        if raw_b is None:
            missing_sheets.append("BUDGET ANALYSIS")
            raw_b = pd.DataFrame()
    else:
        return {"delegates": None, "budget_analysis": None, "missing_sheets": ["ALL"]}

    # ── DELEGATES ────────────────────────────────────────────────────────────
    del_df = None
    if raw_d is not None and not raw_d.empty:
        cols          = _parse_header(raw_d, 1)
        sno_col       = _find_col(cols, "s.no")
        name_col      = _find_col(cols, "delegate name", "name")
        terr_col      = _find_col(cols, "territory")
        nonpresc_col  = _find_col(cols, "non prescriber\ncalls", "non prescriber calls")
        presc_col     = _find_col(cols, "prescriber\ncalls", "prescriber calls")
        conv_col      = _find_col(cols, "drs\nconverted", "drs converted")
        total_col     = _find_col(cols, "total calls")
        pharm_col     = _find_col(cols, "pharmacy\ncalls", "pharmacy calls")
        days_tgt_col  = _find_col(cols, "days\ntarget", "days target")
        days_wk_col   = _find_col(cols, "days\nworked", "days worked")
        avg_col       = _find_col(cols, "avg calls\nper day", "avg calls per day")
        orders_col    = _find_col(cols, "total orders\n(eur)", "total orders (eur)", "total orders")
        ctc_col       = _find_col(cols, "ctc\n(eur)", "ctc (eur)", "ctc")

        del_rows = []
        for i, row in raw_d.iterrows():
            if i < 2:
                continue
            try:
                sn = float(str(row.iloc[sno_col]).strip()) if sno_col is not None else float("nan")
            except (ValueError, TypeError):
                continue
            if pd.isna(sn):
                continue
            delegate_raw = str(row.iloc[name_col]).strip() if name_col is not None else ""
            if not delegate_raw or any(k in delegate_raw.upper() for k in ("TOTAL", "TARGET")):
                continue
            del_rows.append({
                "SN":            int(sn),
                "Delegate":      normalize_mr(delegate_raw),
                "Delegate_Raw":  delegate_raw,
                "Territory":     normalize_territory(str(row.iloc[terr_col]).strip()) if terr_col is not None else "UNKNOWN",
                "NonPrescriber": safe_num(row.iloc[nonpresc_col])  if nonpresc_col is not None else 0.0,
                "Prescriber":    safe_num(row.iloc[presc_col])     if presc_col    is not None else 0.0,
                "DrsConverted":  safe_num(row.iloc[conv_col])      if conv_col     is not None else 0.0,
                "TotalCalls":    safe_num(row.iloc[total_col])     if total_col    is not None else 0.0,
                "PharmacyCalls": safe_num(row.iloc[pharm_col])     if pharm_col    is not None else 0.0,
                "DaysTarget":    safe_num(row.iloc[days_tgt_col])  if days_tgt_col is not None else 0.0,
                "DaysWorked":    safe_num(row.iloc[days_wk_col])   if days_wk_col  is not None else 0.0,
                "AvgCallsPerDay":safe_num(row.iloc[avg_col])       if avg_col      is not None else 0.0,
                "TotalOrders":   safe_num(row.iloc[orders_col])    if orders_col   is not None else 0.0,
                "CTC":           safe_num(row.iloc[ctc_col])       if ctc_col      is not None else 0.0,
            })
        del_df = pd.DataFrame(del_rows)

    # ── BUDGET ANALYSIS ──────────────────────────────────────────────────────
    ba_df = None
    if raw_b is not None and not raw_b.empty:
        cols     = _parse_header(raw_b, 1)
        doc_col  = _find_col(cols, "doctor / contact", "doctor/contact")
        area_col = _find_col(cols, "area / hospital", "area/hospital")
        mr_col   = _find_col(cols, "responsible mr", "responsible")
        act_col  = _find_col(cols, "activity type")
        amt_col  = _find_col(cols, "amount (fcfa)", "amount(fcfa)")

        ba_rows = []
        for i, row in raw_b.iterrows():
            if i < 2:
                continue
            # S.No is NaN for most March rows — filter by doctor presence instead
            doctor = str(row.iloc[doc_col]).strip() if doc_col is not None else ""
            if not doctor or doctor.upper() in ("NAN", "DOCTOR / CONTACT", ""):
                continue
            try:
                float(doctor)
                continue  # purely numeric → malformed row
            except ValueError:
                pass
            ba_rows.append({
                "Doctor":       normalize_doctor(doctor),
                "Area":         str(row.iloc[area_col]).strip() if area_col is not None else "",
                "MR":           normalize_mr(str(row.iloc[mr_col]).strip()) if mr_col is not None else "UNKNOWN",
                "ActivityType": normalize_activity(str(row.iloc[act_col]).strip()) if act_col is not None else "UNKNOWN",
                "Value_FCFA":   safe_num(row.iloc[amt_col]) if amt_col is not None else 0.0,
            })
        ba_df = pd.DataFrame(ba_rows)

    return {"delegates": del_df, "budget_analysis": ba_df, "missing_sheets": missing_sheets}


# ─────────────────────────────────────────────────────────────────────────────
# VISIT TRACKER
# ─────────────────────────────────────────────────────────────────────────────

def load_visit_tracker(files_and_months: list = None,
                       sheets: list = None) -> pd.DataFrame:
    """
    files_and_months: [(file_bytes, month_label), ...]  — local Excel path.
    sheets:           [(df, month_label), ...]           — Google Sheets path.

    Returns flat DataFrame: MR_ID, MR, Doctor, Speciality, Clinic, Visit_Date, Month.
    Missing / unreadable sheets are skipped gracefully.
    """
    all_rows = []

    def _process(raw: pd.DataFrame, month_label: str, sheet_name: str = ""):
        if raw is None or raw.empty or len(raw) < 4:
            return
        # MR name lives at row 0, column 1 (header "Name of MR" is col 0)
        try:
            mr_name = str(raw.iloc[0, 1]).strip()
        except Exception:
            mr_name = ""
        if not mr_name or mr_name.upper() in ("NAN", "NAME OF MR", ""):
            mr_name = sheet_name or month_label
        mr_id = normalize_mr(mr_name)
        # Fall back to sheet_name normalization if still UNKNOWN
        if mr_id == "UNKNOWN" and sheet_name:
            mr_id = normalize_mr(sheet_name)

        # Header at row index 3
        col_map = {}
        for c, val in raw.iloc[3].items():
            col_map[_norm_hdr(str(val))] = c

        doc_col    = _find_col(col_map, "doctor name", "dr name", "dr. name", "doctor", "nom", "name of")
        spec_col   = _find_col(col_map, "speciality", "specialty")
        clinic_col = _find_col(col_map, "hospital / clinic", "hospital/clinic", "clinic", "hospital")
        visit_cols = [c for k, c in col_map.items() if "visit" in k]

        for vc in visit_cols:
            raw[vc] = _parse_visit_date(raw[vc])

        for i, row in raw.iterrows():
            if i <= 3:
                continue
            doctor = str(row[doc_col]).strip() if doc_col is not None else ""
            if not doctor or doctor.upper() in ("NAN", "DR NAME", "DOCTOR NAME", ""):
                continue
            speciality = str(row[spec_col]).strip()   if spec_col   is not None else ""
            clinic     = str(row[clinic_col]).strip() if clinic_col is not None else ""
            for vc in visit_cols:
                vdate = row[vc]
                if pd.isna(vdate):
                    continue
                all_rows.append({
                    "MR_ID":      mr_id,
                    "MR":         mr_display_name(mr_id) if mr_id != "UNKNOWN" else mr_name,
                    "Doctor":     doctor,
                    "Speciality": speciality,
                    "Clinic":     clinic,
                    "Visit_Date": vdate,
                    "Month":      month_label,
                })

    if sheets is not None:
        for raw, month_label in sheets:
            _process(raw, month_label)
    else:
        for file_bytes, month_label in (files_and_months or []):
            try:
                xl = pd.ExcelFile(BytesIO(file_bytes))
            except Exception as exc:
                logger.warning(f"[loaders] Cannot open visit tracker for {month_label}: {exc}")
                continue
            for sname in xl.sheet_names:
                try:
                    raw = pd.read_excel(xl, sheet_name=sname, header=None)
                    _process(raw, month_label, sheet_name=sname)
                except Exception as exc:
                    logger.warning(f"[loaders] Skipping visit sheet {sname!r} ({month_label}): {exc}")

    if all_rows:
        result = pd.DataFrame(all_rows)
        result["Visit_Date"] = pd.to_datetime(result["Visit_Date"])
        return result
    return pd.DataFrame(columns=["MR_ID", "MR", "Doctor", "Speciality", "Clinic", "Visit_Date", "Month"])


# ─────────────────────────────────────────────────────────────────────────────
# COPY REPORT
# ─────────────────────────────────────────────────────────────────────────────

def load_copy_report(file_bytes: bytes = None, current_month: str = None,
                     df: pd.DataFrame = None) -> dict:
    """
    Returns {'product_perf', 'plan_activities', 'actual_activities', 'missing_sheets'}.
    """
    _empty = {
        "product_perf": pd.DataFrame(), "plan_activities": pd.DataFrame(),
        "actual_activities": pd.DataFrame(), "missing_sheets": ["ALL"],
    }
    if df is not None:
        raw = df
    elif file_bytes is not None:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        if not xl.sheet_names:
            return _empty
        prefix = (current_month or "")[:3].lower()
        match = next((s for s in xl.sheet_names if s.lower().startswith(prefix)), None)
        if not match:
            match = xl.sheet_names[0]
        raw = pd.read_excel(xl, sheet_name=match, header=None)
    else:
        return _empty

    prod_rows, plan_rows, actual_rows = [], [], []
    for i, row in raw.iterrows():
        if i < 2:
            continue
        sn = row.iloc[0]
        if isinstance(sn, (int, float)) and not pd.isna(sn):
            product = str(row.iloc[1]).strip()
            if product and product.upper() not in ("NAN", "PRODUCTS"):
                prod_rows.append({
                    "Product":        product,
                    "RATE":           safe_num(row.iloc[2]),
                    "Target_Units":   safe_num(row.iloc[3]),
                    "Achieved_Units": safe_num(row.iloc[4]),
                })
        doc_plan = str(row.iloc[5]).strip()
        if doc_plan and doc_plan.upper() not in ("NAN", "NAME OF DOCTOR", ""):
            plan_rows.append({
                "Doctor":      normalize_doctor(doc_plan),
                "Hospital":    str(row.iloc[6]).strip(),
                "Speciality":  str(row.iloc[7]).strip(),
                "Activity":    normalize_activity(str(row.iloc[8]).strip()),
                "Amount_FCFA": safe_num(row.iloc[9]),
            })
        doc_actual = str(row.iloc[10]).strip() if len(row) > 10 else ""
        if doc_actual and doc_actual.upper() not in ("NAN", "DOCTOR NAME", ""):
            actual_rows.append({
                "Doctor":      normalize_doctor(doc_actual),
                "Hospital":    str(row.iloc[11]).strip()  if len(row) > 11 else "",
                "Speciality":  str(row.iloc[12]).strip()  if len(row) > 12 else "",
                "Activity":    normalize_activity(str(row.iloc[13]).strip()) if len(row) > 13 else "",
                "Amount_FCFA": safe_num(row.iloc[14])     if len(row) > 14 else 0,
                "Remarks":     str(row.iloc[15]).strip()  if len(row) > 15 else "",
                "VisitedBy":   normalize_mr(str(row.iloc[16]).strip()) if len(row) > 16 else "",
                "NoOfVisits":  safe_num(row.iloc[17])     if len(row) > 17 else 0,
            })
    return {
        "product_perf":      pd.DataFrame(prod_rows),
        "plan_activities":   pd.DataFrame(plan_rows),
        "actual_activities": pd.DataFrame(actual_rows),
        "missing_sheets":    [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOUR PLAN
# ─────────────────────────────────────────────────────────────────────────────

def is_covered(plan, actual) -> bool:
    if not plan or not actual:
        return False
    p, a = str(plan).strip(), str(actual).strip()
    if p in ("nan", "") or a in ("nan", ""):
        return False
    stopwords = {"ZONE", "DE", "DU", "LA", "LE", "LES"}
    p_words = {w for w in re.findall(r"[A-Z0-9]{3,}", p.upper()) if w not in stopwords}
    a_words = {w for w in re.findall(r"[A-Z0-9]{3,}", a.upper()) if w not in stopwords}
    if not p_words or not a_words:
        return p.upper() == a.upper()
    return bool(p_words & a_words)


def load_tour_plan(file_bytes: bytes = None, df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Single TOUR PLAN sheet, flat format.
    Date column may contain strings ("05/01/2026") or datetime objects depending on month.
    """
    if df is not None:
        raw = df
    elif file_bytes is not None:
        raw = pd.read_excel(BytesIO(file_bytes), sheet_name=0, header=None)
    else:
        return pd.DataFrame()

    # Locate header row: first row containing "DATE" and "NAME"
    header_idx = None
    for i, row in raw.iterrows():
        txt = " ".join(str(v).upper() for v in row.values if not pd.isna(v))
        if "DATE" in txt and ("MR NAME" in txt or "NAME" in txt):
            header_idx = i
            break
    if header_idx is None:
        logger.warning("[loaders] load_tour_plan: header row not found")
        return pd.DataFrame()

    cols       = _parse_header(raw, header_idx)
    date_col   = _find_col(cols, "date")
    name_col   = _find_col(cols, "mr name", "name")
    joint_col  = _find_col(cols, "joint working", "joint")
    plan_col   = _find_col(cols, "tour plan (planned area)", "tour plan", "planned area", "planned")
    actual_col = _find_col(cols, "actual working area", "actual working", "actual area", "working area")

    rows = []
    for i, row in raw.iterrows():
        if i <= header_idx:
            continue
        name = str(row.iloc[name_col]).strip() if name_col is not None else ""
        if not name or name.upper() in ("NAN", "MR NAME", ""):
            continue

        date_raw = row.iloc[date_col] if date_col is not None else None
        if isinstance(date_raw, str):
            date_parsed = pd.to_datetime(date_raw, dayfirst=True, errors="coerce")
        else:
            date_parsed = pd.to_datetime(date_raw, errors="coerce")

        plan   = str(row.iloc[plan_col]).strip()   if plan_col   is not None else ""
        actual = str(row.iloc[actual_col]).strip() if actual_col is not None else ""
        joint  = str(row.iloc[joint_col]).strip()  if joint_col  is not None else ""

        rows.append({
            "Date":          date_parsed,
            "MR":            normalize_mr(name),
            "MR_Raw":        name,
            "Joint_Working": joint,
            "Planned_Area":  plan,
            "Actual_Area":   actual,
            "Covered":       is_covered(plan, actual),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Month folder auto-discovery helpers
# ─────────────────────────────────────────────────────────────────────────────

_MONTH_ORDER   = {"jan": 0, "feb": 1, "mar": 2}
_SALES_TAB     = {"jan": "JAN-26", "feb": "FEB-26", "mar": "MAR-26"}
_PREV_SALES_TAB = {"jan": None,    "feb": "JAN-26", "mar": "FEB-26"}


def _folder_to_month_key(name: str) -> "str | None":
    n = name.strip().lower()
    for key in ("jan", "feb", "mar"):
        if n.startswith(key):
            return key
    return None


def _discover_month_folders(storage) -> list:
    """
    List subdirectories of the IVC root and return sorted month config dicts.
    Each dict: key, folder, sales_tab, prev_sales_tab.
    """
    try:
        entries = storage.list_files("")
    except Exception as exc:
        logger.warning(f"[loaders] Cannot list IVC root: {exc}")
        return []

    months = []
    for entry in entries:
        key = _folder_to_month_key(entry)
        if key is None:
            continue
        # Verify it's a directory by trying to list it
        try:
            files = storage.list_files(entry)
            if not files:
                continue
        except Exception:
            continue
        months.append({
            "key":            key,
            "folder":         entry,
            "sales_tab":      _SALES_TAB[key],
            "prev_sales_tab": _PREV_SALES_TAB[key],
        })

    months.sort(key=lambda m: _MONTH_ORDER.get(m["key"], 99))
    return months


def _find_file(storage, folder: str, keyword: str) -> "bytes | None":
    """Return bytes of the first .xlsx in folder whose name contains keyword (case-insensitive)."""
    try:
        files = storage.list_files(folder)
    except Exception:
        return None
    kw = keyword.lower()
    for f in sorted(files):
        if kw in f.lower() and f.lower().endswith(".xlsx"):
            try:
                return storage.get_file_bytes(f"{folder}/{f}")
            except Exception as exc:
                logger.warning(f"[loaders] Cannot read {folder}/{f}: {exc}")
    return None


def _find_root_file(storage, keyword: str) -> "bytes | None":
    """Return bytes of the first .xlsx at the IVC root matching keyword."""
    try:
        files = storage.list_files("")
    except Exception:
        return None
    kw = keyword.lower()
    for f in sorted(files):
        if kw in f.lower() and f.lower().endswith(".xlsx"):
            try:
                return storage.get_file_bytes(f)
            except Exception as exc:
                logger.warning(f"[loaders] Cannot read root file {f}: {exc}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# LOAD ALL DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_all_data(storage) -> dict:
    """
    Load all monthly and master data from local storage.
    Month folders are auto-discovered from IVC root subdirectories.
    """
    data = {}

    sales_bytes = _find_root_file(storage, "sales")
    copy_bytes  = _find_root_file(storage, "copy")

    canonical_rates = {}
    if sales_bytes:
        canonical_rates = build_canonical_rates(sales_bytes)
        logger.info(f"[loaders] Canonical rates built for {len(canonical_rates)} products")
    else:
        logger.warning("[loaders] Sales file not found at IVC root — canonical rates unavailable")

    months = _discover_month_folders(storage)
    if not months:
        logger.warning("[loaders] No month folders found — returning empty data")
        return data

    # Track each month's closing balance to validate the next month's opening
    prev_closing: dict = {}   # key → closing balance FCFA

    for m in months:
        key    = m["key"]
        folder = m["folder"]
        logger.info(f"[loaders] Loading {key.upper()} from '{folder}'")

        proj_bytes    = _find_file(storage, folder, "projection")
        exp_bytes     = _find_file(storage, folder, "expense")
        monthly_bytes = _find_file(storage, folder, "monthly")
        tour_bytes    = _find_file(storage, folder, "tour")
        visit_bytes   = _find_file(storage, folder, "visit")

        # Sales
        sales = (
            load_sales(sales_bytes, m["sales_tab"], m["prev_sales_tab"])
            if sales_bytes
            else {"current": pd.DataFrame(), "prev": pd.DataFrame()}
        )

        # Projection (canonical rates injected)
        projection = (
            load_projection(proj_bytes, canonical_rates=canonical_rates)
            if proj_bytes
            else {"projection": None, "activity_plan": None, "missing_sheets": ["ALL"]}
        )

        # Expense (balance validation against previous month)
        prev_key = {"feb": "jan", "mar": "feb"}.get(key)
        expense = (
            load_expense(
                exp_bytes,
                month_label=key.upper(),
                prev_closing_fcfa=prev_closing.get(prev_key),
                canonical_rates=canonical_rates,
            )
            if exp_bytes
            else {
                "activity_exp": None, "other_exp": None, "money_received": None,
                "opening_balance_fcfa": 0.0, "new_budget_fcfa": 0.0,
                "total_received_fcfa": 0.0, "total_spent_fcfa": 0.0,
                "balance_fcfa": 0.0, "missing_sheets": ["ALL"],
            }
        )
        prev_closing[key] = expense.get("balance_fcfa", 0.0)

        # Monthly reports
        monthly = (
            load_monthly_reports(monthly_bytes)
            if monthly_bytes
            else {"delegates": None, "budget_analysis": None, "missing_sheets": ["ALL"]}
        )

        # Copy report (optional master file)
        copy = (
            load_copy_report(copy_bytes, key.capitalize())
            if copy_bytes
            else {
                "product_perf": pd.DataFrame(), "plan_activities": pd.DataFrame(),
                "actual_activities": pd.DataFrame(), "missing_sheets": ["ALL"],
            }
        )

        # Tour plan
        tour = load_tour_plan(tour_bytes) if tour_bytes else pd.DataFrame()

        # Visit tracker (sheets vary by month — handled gracefully inside loader)
        visits = (
            load_visit_tracker([(visit_bytes, key[:3])])
            if visit_bytes
            else pd.DataFrame(
                columns=["MR_ID", "MR", "Doctor", "Speciality", "Clinic", "Visit_Date", "Month"]
            )
        )

        data[key] = {
            "sales":      sales,
            "projection": projection,
            "expense":    expense,
            "monthly":    monthly,
            "copy":       copy,
            "tour":       tour,
            "visits":     visits,
        }

    return data
