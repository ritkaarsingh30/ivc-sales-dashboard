"""
GET /api/months/{month} — full monthly data bundle
"""
import json
import numpy as np
from fastapi import APIRouter, HTTPException
from constants import FCFA_TO_EUR, DISTRIBUTORS
from name_map import product_display_name, mr_display_name, MR_CANONICAL
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()

VALID_MONTHS = {"jan", "feb", "mar"}


def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )


def _get_data():
    from main import app_state
    return app_state.get("data", {})


@router.get("/months/{month}")
async def get_month(month: str):
    if month not in VALID_MONTHS:
        raise HTTPException(status_code=404, detail=f"Month '{month}' not found. Use jan/feb/mar.")

    cache_key = f"months:{month}"
    cached = await get_api_cache(cache_key)
    if cached:
        return cached

    data = _get_data()
    d = data.get(month, {})

    sales_data = d.get("sales", {})
    current_sales = sales_data.get("current")
    prev_sales = sales_data.get("prev")
    monthly = d.get("monthly", {}) or {}
    expense = d.get("expense", {}) or {}
    proj_dict = d.get("projection", {}) or {}
    visits_df = d.get("visits")
    copy_data = d.get("copy", {}) or {}

    # ── KPIs ──
    delegates_df = monthly.get("delegates")
    proj_df = proj_dict.get("projection")
    ae_df = expense.get("activity_exp")

    total_sales = round(float(current_sales["TOTAL_VALUE_EUR"].sum()), 2) if current_sales is not None and not current_sales.empty else 0
    total_target = round(float(proj_df["Target_Value_EUR"].sum()), 2) if proj_df is not None and not proj_df.empty else None
    achievement_pct = round(total_sales / total_target * 100, 1) if total_target and total_target > 0 else None

    tablet_sales = 0
    inj_sales = 0
    if current_sales is not None and not current_sales.empty:
        tablet_sales = round(float(current_sales[current_sales["Category"] == "TABLET"]["TOTAL_VALUE_EUR"].sum()), 2)
        inj_sales = round(float(current_sales[current_sales["Category"] == "INJECTABLE"]["TOTAL_VALUE_EUR"].sum()), 2)

    total_visits = int(len(visits_df)) if visits_df is not None and hasattr(visits_df, "empty") and not visits_df.empty else 0
    prescriber_calls = int(delegates_df["Prescriber"].sum()) if delegates_df is not None and not delegates_df.empty else 0
    non_prescriber_calls = int(delegates_df["NonPrescriber"].sum()) if delegates_df is not None and not delegates_df.empty else 0
    pharmacy_calls = int(delegates_df["PharmacyCalls"].sum()) if delegates_df is not None and not delegates_df.empty else 0
    drs_converted = int(delegates_df["DrsConverted"].sum()) if delegates_df is not None and not delegates_df.empty else 0
    avg_visits = round(float(delegates_df["AvgCallsPerDay"].sum()), 2) if delegates_df is not None and not delegates_df.empty else 0
    spent_fcfa = expense.get("total_spent_fcfa", 0)
    received_fcfa = expense.get("total_received_fcfa", 0)
    balance_fcfa = expense.get("balance_fcfa", 0)
    opening_fcfa = expense.get("opening_balance_fcfa", 0)

    kpis = {
        "total_sales_eur": total_sales,
        "tablet_sales_eur": tablet_sales,
        "injectable_sales_eur": inj_sales,
        "total_target_eur": total_target,
        "achievement_pct": achievement_pct,
        "total_visits": total_visits,
        "prescriber_calls": prescriber_calls,
        "non_prescriber_calls": non_prescriber_calls,
        "pharmacy_calls": pharmacy_calls,
        "drs_converted": drs_converted,
        "avg_visits_day": avg_visits,
        "activity_spent_fcfa": round(float(spent_fcfa), 2),
        "activity_spent_eur": round(float(spent_fcfa) / FCFA_TO_EUR, 2),
        "activity_received_fcfa": round(float(received_fcfa), 2),
        "activity_received_eur": round(float(received_fcfa) / FCFA_TO_EUR, 2),
        "opening_balance_fcfa": round(float(opening_fcfa), 2),
        "opening_balance_eur": round(float(opening_fcfa) / FCFA_TO_EUR, 2),
        "closing_balance_fcfa": round(float(balance_fcfa), 2),
        "closing_balance_eur": round(float(balance_fcfa) / FCFA_TO_EUR, 2),
    }

    # ── Target vs Achieved ──
    target_vs_achieved = []
    if proj_df is not None and not proj_df.empty and current_sales is not None and not current_sales.empty:
        for _, prow in proj_df.iterrows():
            prod = prow["Product"]
            target = prow.get("Target_Units", 0)
            matched = current_sales[current_sales["Product"] == prod]
            achieved = float(matched["TOTAL_SALES"].sum()) if not matched.empty else 0
            target_vs_achieved.append({
                "product": prod,
                "target": round(float(target), 2),
                "achieved": round(achieved, 2),
            })

    # ── Product Sales (top 10) ──
    product_sales = []
    if current_sales is not None and not current_sales.empty:
        ps = current_sales[["Product", "TOTAL_VALUE_EUR"]].copy()
        ps = ps.groupby("Product")["TOTAL_VALUE_EUR"].sum().reset_index()
        ps = ps.sort_values("TOTAL_VALUE_EUR", ascending=False).head(10)
        for _, row in ps.iterrows():
            product_sales.append({
                "product": row["Product"],
                "sales_eur": round(float(row["TOTAL_VALUE_EUR"]), 2),
            })

    # ── Delegate Table ──
    delegate_table = []
    if delegates_df is not None and not delegates_df.empty:
        for _, row in delegates_df.iterrows():
            total_orders = float(row.get("TotalOrders", 0) or 0)
            ctc = float(row.get("CTC", 0) or 0)
            ctc_ratio = round(ctc / total_orders * 100, 1) if total_orders > 0 else None
            delegate_table.append({
                "name": row.get("Delegate", ""),
                "territory": row.get("Territory", ""),
                "total_calls": int(row.get("TotalCalls", 0) or 0),
                "prescriber": int(row.get("Prescriber", 0) or 0),
                "non_prescriber": int(row.get("NonPrescriber", 0) or 0),
                "pharmacy": int(row.get("PharmacyCalls", 0) or 0),
                "drs_converted": int(row.get("DrsConverted", 0) or 0),
                "days_worked": int(row.get("DaysWorked", 0) or 0),
                "avg_per_day": round(float(row.get("AvgCallsPerDay", 0) or 0), 2),
                "orders_eur": round(total_orders, 2) if total_orders else None,
                "ctc_eur": round(ctc, 2) if ctc else None,
                "ctc_ratio": ctc_ratio,
            })

    # ── Distributor Sales ──
    distributor_sales = []
    if current_sales is not None and not current_sales.empty:
        total_s = current_sales["TOTAL_VALUE_EUR"].sum()
        for dist in DISTRIBUTORS:
            col = f"{dist}_SALES"
            closing_col = f"{dist}_CLOSING"
            if col in current_sales.columns:
                dist_sales = float(current_sales[col].sum())
                # Closing stock: RATE * closing qty
                if closing_col in current_sales.columns:
                    closing_val = (current_sales[closing_col] * current_sales["RATE"]).sum()
                    closing_eur = round(float(closing_val) / FCFA_TO_EUR, 2)
                else:
                    closing_eur = 0
                share_pct = round(dist_sales / float(total_s) * 100, 1) if total_s > 0 else 0
                distributor_sales.append({
                    "distributor": dist,
                    "sales_eur": round(dist_sales, 2),
                    "closing_stock_eur": closing_eur,
                    "share_pct": share_pct,
                })

    # ── Activity Expenses ──
    activity_expenses = []
    if ae_df is not None and not ae_df.empty:
        for _, row in ae_df.iterrows():
            activity_expenses.append({
                "sn": int(row.get("SN", 0)),
                "doctor": row.get("Doctor", ""),
                "hospital": row.get("Hospital", ""),
                "speciality": row.get("Speciality", ""),
                "activity": row.get("Activity", ""),
                "products": row.get("Products", ""),
                "amount_fcfa": round(float(row.get("Amount_FCFA", 0)), 2),
                "amount_eur": round(float(row.get("Amount_EUR", 0)), 2),
                "responsible": row.get("Responsible", ""),
            })

    # ── Call Breakdown (for chart) ──
    call_breakdown = {"labels": [], "prescriber": [], "non_prescriber": [], "pharmacy": []}
    if delegates_df is not None and not delegates_df.empty:
        for _, row in delegates_df.iterrows():
            name = row.get("Delegate", "")
            # Shorten name
            short = name.split()[-1] if name else name
            call_breakdown["labels"].append(short)
            call_breakdown["prescriber"].append(int(row.get("Prescriber", 0) or 0))
            call_breakdown["non_prescriber"].append(int(row.get("NonPrescriber", 0) or 0))
            call_breakdown["pharmacy"].append(int(row.get("PharmacyCalls", 0) or 0))

    result = safe_json({
        "month": month,
        "kpis": kpis,
        "target_vs_achieved": target_vs_achieved,
        "product_sales": product_sales,
        "delegate_table": delegate_table,
        "distributor_sales": distributor_sales,
        "activity_expenses": activity_expenses,
        "call_breakdown": call_breakdown,
    })
    await set_api_cache(cache_key, result)
    return result
