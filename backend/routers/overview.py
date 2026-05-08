"""
GET /api/overview — cross-month summary, product mix, comparison
"""
import json
import numpy as np
from fastapi import APIRouter
from constants import FCFA_TO_EUR, DISTRIBUTORS
from name_map import product_display_name, product_category, MR_CANONICAL
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()

MONTH_FULL_NAMES = {
    "jan": "January",   "feb": "February",  "mar": "March",     "apr": "April",
    "may": "May",       "jun": "June",      "jul": "July",      "aug": "August",
    "sep": "September", "oct": "October",   "nov": "November",  "dec": "December",
}


def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )


def _get_data():
    from main import app_state
    return app_state.get("data", {})


def _sales_by_category(sales_df):
    if sales_df is None or sales_df.empty:
        return {"tablet": 0, "injectable": 0}
    tablet = sales_df[sales_df["Category"] == "TABLET"]["TOTAL_VALUE_EUR"].sum()
    inj    = sales_df[sales_df["Category"] == "INJECTABLE"]["TOTAL_VALUE_EUR"].sum()
    return {"tablet": round(float(tablet), 2), "injectable": round(float(inj), 2)}


def _total_sales(sales_dict):
    s = sales_dict.get("current")
    if s is None or s.empty:
        return 0.0
    return round(float(s["TOTAL_VALUE_EUR"].sum()), 2)


def _total_visits(visits_df):
    if visits_df is None or (hasattr(visits_df, "empty") and visits_df.empty):
        return 0
    return int(len(visits_df))


def _drs_converted(monthly_dict):
    d = monthly_dict.get("delegates") if monthly_dict else None
    if d is None or d.empty:
        return 0
    return int(d["DrsConverted"].sum())


def _avg_calls_per_day(monthly_dict):
    d = monthly_dict.get("delegates") if monthly_dict else None
    if d is None or d.empty:
        return None
    return round(float(d["AvgCallsPerDay"].sum()), 2)


def _top_product(sales_df):
    if sales_df is None or sales_df.empty:
        return "N/A"
    idx = sales_df["TOTAL_VALUE_EUR"].idxmax()
    return sales_df.loc[idx, "Product"]


def _month_projection(proj_dict):
    p = proj_dict.get("projection") if proj_dict else None
    if p is None or p.empty:
        return None
    return round(float(p["Target_Value_EUR"].sum()), 2)


@router.get("/overview")
async def get_overview():
    cached = await get_api_cache("overview")
    if cached:
        return cached

    data = _get_data()
    month_keys = list(data.keys())  # dynamic — whatever months are loaded

    # ── Month comparison (one entry per loaded month) ──────────────────────────
    month_comparison = []
    for key in month_keys:
        label = MONTH_FULL_NAMES.get(key, key.capitalize())
        d = data.get(key, {})
        sales   = d.get("sales", {})
        monthly = d.get("monthly", {})
        expense = d.get("expense", {}) or {}
        visits  = d.get("visits")
        proj_dict = d.get("projection", {}) or {}

        total_s = _total_sales(sales)
        proj_s  = _month_projection(proj_dict)
        ach_pct = round(total_s / proj_s * 100, 1) if proj_s and proj_s > 0 else None

        tcalls = pcalls = phcalls = 0
        acts = monthly.get("delegates") if monthly else None
        if acts is not None and not acts.empty:
            tcalls  = int(acts["TotalCalls"].sum())
            pcalls  = int(acts["Prescriber"].sum())
            phcalls = int(acts["PharmacyCalls"].sum())
            active_delegates = int((acts["TotalCalls"] > 0).sum())
        else:
            active_delegates = 0

        opening_bal = expense.get("opening_balance_fcfa", 0)
        closing_bal = expense.get("balance_fcfa", 0)
        spent       = expense.get("total_spent_fcfa", 0)
        received    = expense.get("total_received_fcfa", 0)

        month_comparison.append({
            "key":               key,
            "month":             label,
            "sales":             total_s,
            "projection":        proj_s,
            "achievement":       ach_pct,
            "visits":            _total_visits(visits),
            "prescriber_calls":  pcalls,
            "pharmacy_calls":    phcalls,
            "drs_converted":     _drs_converted(monthly),
            "avg_visits_day":    _avg_calls_per_day(monthly),
            "activity_spent_fcfa": round(float(spent), 2),
            "activity_spent_eur":  round(float(spent) / FCFA_TO_EUR, 2),
            "opening_balance_eur": round(float(opening_bal) / FCFA_TO_EUR, 2) if opening_bal else None,
            "closing_balance_eur": round(float(closing_bal) / FCFA_TO_EUR, 2),
            "received_fcfa":       round(float(received), 2),
            "active_delegates":    active_delegates,
            "top_product":         _top_product(sales.get("current")),
        })

    # ── Cross-month aggregates ─────────────────────────────────────────────────
    total_sales_all = sum(m["sales"] for m in month_comparison)

    best = max(month_comparison, key=lambda m: m["sales"], default={"month": "N/A", "sales": 0})
    best_month, best_val = best["month"], best["sales"]

    # Top product across all loaded months
    all_sales_dfs = []
    for key in month_keys:
        s = data.get(key, {}).get("sales", {}).get("current")
        if s is not None and not s.empty:
            all_sales_dfs.append(s)

    top_product_all = "N/A"
    top_product_all_val = 0
    if all_sales_dfs:
        import pandas as _pd
        combined = _pd.concat(all_sales_dfs)
        if not combined.empty:
            grp = combined.groupby("Product")["TOTAL_VALUE_EUR"].sum()
            top_product_all     = grp.idxmax()
            top_product_all_val = round(float(grp.max()), 2)

    annual_target_eur = 205000
    annual_achievement_pct = round(total_sales_all / annual_target_eur * 100, 1) if annual_target_eur else None

    # Per-delegate visits across all months
    delegate_visits_all = {}
    for key in month_keys:
        visits = data.get(key, {}).get("visits")
        if visits is not None and hasattr(visits, "empty") and not visits.empty and "MR" in visits.columns:
            for mr, cnt in visits.groupby("MR").size().items():
                delegate_visits_all[mr] = delegate_visits_all.get(mr, 0) + int(cnt)

    # Build dynamic per-month dicts for summary (used by frontend overview charts)
    month_sales_by_key     = {m["key"]: m["sales"]         for m in month_comparison}
    month_visits_by_key    = {m["key"]: m["visits"]        for m in month_comparison}
    month_drs_by_key       = {m["key"]: m["drs_converted"] for m in month_comparison}
    month_avg_cpd_by_key   = {m["key"]: m["avg_visits_day"]for m in month_comparison}
    month_achievement_by_key = {m["key"]: m["achievement"] for m in month_comparison}

    q1_summary = {
        "total_sales_eur":        round(total_sales_all, 2),
        "month_sales":            month_sales_by_key,
        "month_achievement_pct":  month_achievement_by_key,
        "annual_target_eur":      annual_target_eur,
        "annual_achievement_pct": annual_achievement_pct,
        "best_month":             best_month,
        "best_month_sales":       round(best_val, 2),
        "top_product_all":        top_product_all,
        "top_product_all_val":    top_product_all_val,
        "total_visits":           month_visits_by_key,
        "total_visits_all":       sum(month_visits_by_key.values()),
        "drs_converted":          month_drs_by_key,
        "drs_converted_all":      sum(month_drs_by_key.values()),
        "avg_calls_per_day":      month_avg_cpd_by_key,
        "delegate_visits_all":    [
            {"delegate": k, "visits": v}
            for k, v in sorted(delegate_visits_all.items(), key=lambda x: -x[1])
        ],
        # Backwards-compat aliases (jan/feb/mar)
        "jan_sales":              month_sales_by_key.get("jan", 0),
        "feb_sales":              month_sales_by_key.get("feb", 0),
        "mar_sales":              month_sales_by_key.get("mar", 0),
        "jan_achievement_pct":    month_achievement_by_key.get("jan"),
        "feb_achievement_pct":    month_achievement_by_key.get("feb"),
        "mar_achievement_pct":    month_achievement_by_key.get("mar"),
        "top_product_q1":         top_product_all,
        "top_product_q1_val":     top_product_all_val,
        "total_visits_q1":        sum(month_visits_by_key.values()),
        "drs_converted_q1":       sum(month_drs_by_key.values()),
        "delegate_visits_q1":     [
            {"delegate": k, "visits": v}
            for k, v in sorted(delegate_visits_all.items(), key=lambda x: -x[1])
        ],
    }

    # ── Product mix by month ───────────────────────────────────────────────────
    product_mix = {}
    for key in month_keys:
        d = data.get(key, {})
        product_mix[key] = _sales_by_category(d.get("sales", {}).get("current"))

    # ── All-products trend across months ──────────────────────────────────────
    all_products: set = set()
    for key in month_keys:
        s = data.get(key, {}).get("sales", {}).get("current")
        if s is not None and not s.empty:
            all_products.update(s["Product"].tolist())

    all_products_trend = []
    for prod in sorted(all_products):
        entry = {"product": prod}
        for key in month_keys:
            s = data.get(key, {}).get("sales", {}).get("current")
            if s is not None and not s.empty:
                row = s[s["Product"] == prod]
                entry[key] = round(float(row["TOTAL_VALUE_EUR"].iloc[0]), 2) if not row.empty else 0
            else:
                entry[key] = 0
        all_products_trend.append(entry)

    result = safe_json({
        "q1_summary":         q1_summary,
        "month_comparison":   month_comparison,
        "product_mix":        product_mix,
        "all_products_trend": all_products_trend,
        "months_loaded":      month_keys,
    })
    await set_api_cache("overview", result)
    return result
