"""
GET /api/overview — Q1 summary, month comparison, product mix
"""
import json
import numpy as np
from fastapi import APIRouter
from constants import FCFA_TO_EUR, DISTRIBUTORS
from name_map import product_display_name, product_category, MR_CANONICAL
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()


def safe_json(obj):
    """Convert NaN/None floats to null for JSON serialization."""
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
    inj = sales_df[sales_df["Category"] == "INJECTABLE"]["TOTAL_VALUE_EUR"].sum()
    return {"tablet": round(float(tablet), 2), "injectable": round(float(inj), 2)}


def _total_sales(sales_dict):
    s = sales_dict.get("current")
    if s is None or s.empty:
        return 0.0
    return round(float(s["TOTAL_VALUE_EUR"].sum()), 2)


def _total_visits(visits_df):
    if visits_df is None or hasattr(visits_df, "empty") and visits_df.empty:
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
    val = d["AvgCallsPerDay"].sum()
    return round(float(val), 2)


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

    month_labels = {"jan": "January", "feb": "February", "mar": "March"}
    month_colors = {"jan": "j", "feb": "f", "mar": "m"}

    # Month comparison
    month_comparison = []
    for key, label in month_labels.items():
        d = data.get(key, {})
        sales = d.get("sales", {})
        monthly = d.get("monthly", {})
        expense = d.get("expense", {}) or {}
        visits = d.get("visits")
        proj_dict = d.get("projection", {}) or {}

        total_s = _total_sales(sales)
        proj_s = _month_projection(proj_dict)
        ach_pct = round(total_s / proj_s * 100, 1) if proj_s and proj_s > 0 else None

        current_sales = sales.get("current")
        prev_sales = sales.get("prev")
        tcalls = 0
        pcalls = 0
        phcalls = 0
        acts = monthly.get("delegates") if monthly else None
        if acts is not None and not acts.empty:
            tcalls = int(acts["TotalCalls"].sum())
            pcalls = int(acts["Prescriber"].sum())
            phcalls = int(acts["PharmacyCalls"].sum())

        opening_bal = expense.get("opening_balance_fcfa", 0)
        closing_bal = expense.get("balance_fcfa", 0)
        spent = expense.get("total_spent_fcfa", 0)
        received = expense.get("total_received_fcfa", 0)

        # Count active delegates (non-CM, non-zero calls)
        active_delegates = 0
        if acts is not None and not acts.empty:
            active_delegates = int((acts["TotalCalls"] > 0).sum())

        month_comparison.append({
            "month": label,
            "sales": total_s,
            "projection": proj_s,
            "achievement": ach_pct,
            "visits": _total_visits(visits),
            "prescriber_calls": pcalls,
            "pharmacy_calls": phcalls,
            "drs_converted": _drs_converted(monthly),
            "avg_visits_day": _avg_calls_per_day(monthly),
            "activity_spent_fcfa": round(float(spent), 2),
            "activity_spent_eur": round(float(spent) / FCFA_TO_EUR, 2),
            "opening_balance_eur": round(float(opening_bal) / FCFA_TO_EUR, 2) if opening_bal else None,
            "closing_balance_eur": round(float(closing_bal) / FCFA_TO_EUR, 2),
            "received_fcfa": round(float(received), 2),
            "active_delegates": active_delegates,
            "top_product": _top_product(sales.get("current")),
        })

    # Q1 Summary
    jan_s = month_comparison[0]["sales"] if month_comparison else 0
    feb_s = month_comparison[1]["sales"] if len(month_comparison) > 1 else 0
    mar_s = month_comparison[2]["sales"] if len(month_comparison) > 2 else 0

    q1_summary = {
        "total_sales_eur": round(jan_s + feb_s + mar_s, 2),
        "jan_sales": jan_s,
        "feb_sales": feb_s,
        "mar_sales": mar_s,
        "jan_achievement_pct": month_comparison[0]["achievement"] if month_comparison else None,
        "feb_achievement_pct": month_comparison[1]["achievement"] if len(month_comparison) > 1 else None,
        "mar_achievement_pct": month_comparison[2]["achievement"] if len(month_comparison) > 2 else None,
        "total_visits": {
            "jan": month_comparison[0]["visits"] if month_comparison else 0,
            "feb": month_comparison[1]["visits"] if len(month_comparison) > 1 else 0,
            "mar": month_comparison[2]["visits"] if len(month_comparison) > 2 else 0,
        },
        "drs_converted": {
            "jan": month_comparison[0]["drs_converted"] if month_comparison else 0,
            "feb": month_comparison[1]["drs_converted"] if len(month_comparison) > 1 else 0,
            "mar": month_comparison[2]["drs_converted"] if len(month_comparison) > 2 else 0,
        },
        "avg_calls_per_day": {
            "jan": month_comparison[0]["avg_visits_day"] if month_comparison else None,
            "feb": month_comparison[1]["avg_visits_day"] if len(month_comparison) > 1 else None,
            "mar": month_comparison[2]["avg_visits_day"] if len(month_comparison) > 2 else None,
        },
    }

    # Product mix
    product_mix = {}
    for key in ["jan", "feb", "mar"]:
        d = data.get(key, {})
        sales = d.get("sales", {})
        current = sales.get("current")
        product_mix[key] = _sales_by_category(current)

    # All products Q1 trend (for grouped bar)
    all_products = set()
    for key in ["jan", "feb", "mar"]:
        d = data.get(key, {})
        s = d.get("sales", {}).get("current")
        if s is not None and not s.empty:
            all_products.update(s["Product"].tolist())

    all_products_trend = []
    for prod in sorted(all_products):
        entry = {"product": prod}
        for key, label in month_labels.items():
            d = data.get(key, {})
            s = d.get("sales", {}).get("current")
            if s is not None and not s.empty:
                row = s[s["Product"] == prod]
                entry[key] = round(float(row["TOTAL_VALUE_EUR"].iloc[0]), 2) if not row.empty else 0
            else:
                entry[key] = 0
        all_products_trend.append(entry)

    result = safe_json({
        "q1_summary": q1_summary,
        "month_comparison": month_comparison,
        "product_mix": product_mix,
        "all_products_trend": all_products_trend,
    })
    await set_api_cache("overview", result)
    return result
