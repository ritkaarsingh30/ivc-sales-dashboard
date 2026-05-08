"""
GET /api/months/{month} — full monthly data bundle
"""
import json
import math
import numpy as np
from fastapi import APIRouter, HTTPException
from constants import FCFA_TO_EUR, DISTRIBUTORS
from name_map import product_display_name, mr_display_name, MR_CANONICAL
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()


def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )


def _get_data():
    from main import app_state
    return app_state.get("data", {})


@router.get("/months/{month}")
async def get_month(month: str):
    data = _get_data()
    if month not in data:
        available = list(data.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Month '{month}' not loaded. Available: {available}",
        )

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

    def _safe_int(v):
        try:
            f = float(v)
            return 0 if math.isnan(f) or math.isinf(f) else int(f)
        except (TypeError, ValueError):
            return 0

    def _safe_float(v):
        try:
            f = float(v)
            return 0.0 if math.isnan(f) or math.isinf(f) else f
        except (TypeError, ValueError):
            return 0.0

    # ── Delegate Table ──
    delegate_table = []
    if delegates_df is not None and not delegates_df.empty:
        for _, row in delegates_df.iterrows():
            total_orders = _safe_float(row.get("TotalOrders", 0))
            ctc = _safe_float(row.get("CTC", 0))
            ctc_ratio = round(ctc / total_orders * 100, 1) if total_orders > 0 else None
            mr_id = row.get("Delegate", "")
            delegate_table.append({
                "name": mr_display_name(mr_id) if mr_id else "",
                "territory": row.get("Territory", ""),
                "total_calls": _safe_int(row.get("TotalCalls", 0)),
                "prescriber": _safe_int(row.get("Prescriber", 0)),
                "non_prescriber": _safe_int(row.get("NonPrescriber", 0)),
                "pharmacy": _safe_int(row.get("PharmacyCalls", 0)),
                "drs_converted": _safe_int(row.get("DrsConverted", 0)),
                "days_worked": _safe_int(row.get("DaysWorked", 0)),
                "avg_per_day": round(_safe_float(row.get("AvgCallsPerDay", 0)), 2),
                "orders_eur": round(total_orders, 2) if total_orders else None,
                "ctc_eur": round(ctc, 2) if ctc else None,
                "ctc_ratio": ctc_ratio,
            })

    distributor_sales = []
    if current_sales is not None and not current_sales.empty:
        total_s = current_sales["TOTAL_VALUE_EUR"].sum()
        for dist in DISTRIBUTORS:
            eur_col = f"{dist}_SALES_EUR"
            closing_col = f"{dist}_CLOSING"
            if eur_col in current_sales.columns:
                dist_sales = float(current_sales[eur_col].sum())
                # Closing stock: RATE * closing qty
                if closing_col in current_sales.columns:
                    closing_val = (current_sales[closing_col] * current_sales["RATE"]).sum()
                    closing_eur = round(float(closing_val), 2)
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
            outcome = row.get("Sales_Outcome")
            if not isinstance(outcome, list):
                outcome = []
            outcome_eur = _safe_float(row.get("Sales_Outcome_EUR", 0))
            num_visits_raw = row.get("Num_Visits", 0)
            try:
                num_visits = int(float(num_visits_raw)) if num_visits_raw else 0
            except (ValueError, TypeError):
                num_visits = 0
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
                "sales_outcome": outcome,
                "sales_outcome_eur": round(outcome_eur, 2),
                "num_visits": num_visits,
            })

    # ── Call Breakdown (for chart) ──
    call_breakdown = {"labels": [], "prescriber": [], "non_prescriber": [], "pharmacy": []}
    if delegates_df is not None and not delegates_df.empty:
        for _, row in delegates_df.iterrows():
            mr_id = row.get("Delegate", "")
            name = mr_display_name(mr_id) if mr_id else mr_id
            short = name.split()[-1] if name else name
            call_breakdown["labels"].append(short)
            call_breakdown["prescriber"].append(_safe_int(row.get("Prescriber", 0)))
            call_breakdown["non_prescriber"].append(_safe_int(row.get("NonPrescriber", 0)))
            call_breakdown["pharmacy"].append(_safe_int(row.get("PharmacyCalls", 0)))

    # ── Tour Plan ──
    tour_plan = {"summary": {}, "by_delegate": [], "entries": []}
    tour_df = d.get("tour")
    if tour_df is not None and hasattr(tour_df, "empty") and not tour_df.empty:
        total_planned = len(tour_df)
        covered_count = int(tour_df["Covered"].sum())
        uncovered_count = total_planned - covered_count
        coverage_pct = round(covered_count / total_planned * 100, 1) if total_planned > 0 else 0

        joint_mask = (
            tour_df["Joint_Working"].notna() &
            (~tour_df["Joint_Working"].astype(str).str.strip().str.lower().isin(["", "nan"]))
        )
        joint_count = int(joint_mask.sum())

        by_delegate = []
        for mr_id, grp in tour_df.groupby("MR"):
            mr_name = str(grp["MR_Raw"].iloc[0]) if not grp.empty else mr_id
            planned = len(grp)
            cov = int(grp["Covered"].sum())
            by_delegate.append({
                "mr":           mr_name,
                "mr_id":        mr_id,
                "planned":      planned,
                "covered":      cov,
                "uncovered":    planned - cov,
                "coverage_pct": round(cov / planned * 100, 1) if planned > 0 else 0,
            })
        by_delegate.sort(key=lambda x: x["coverage_pct"], reverse=True)

        entries = []
        for _, row in tour_df.iterrows():
            date_val = row.get("Date")
            date_str = str(date_val)[:10] if date_val is not None and date_val == date_val else ""
            joint = str(row.get("Joint_Working", "")).strip()
            joint = "" if joint.lower() in ("nan", "") else joint
            entries.append({
                "date":          date_str,
                "mr":            str(row.get("MR_Raw", row.get("MR", ""))),
                "planned_area":  str(row.get("Planned_Area", "")).strip(),
                "actual_area":   str(row.get("Actual_Area",  "")).strip(),
                "covered":       bool(row.get("Covered", False)),
                "joint_working": joint,
            })

        # Group entries by delegate (preserving by_delegate sort order)
        entries_by_delegate = {}
        for del_info in by_delegate:
            mr_name = del_info["mr"]
            entries_by_delegate[mr_name] = [e for e in entries if e["mr"] == mr_name]

        tour_plan = {
            "summary": {
                "total":             total_planned,
                "covered":           covered_count,
                "uncovered":         uncovered_count,
                "coverage_pct":      coverage_pct,
                "delegates_active":  len(by_delegate),
                "joint_working":     joint_count,
            },
            "by_delegate":         by_delegate,
            "entries":             entries,
            "entries_by_delegate": entries_by_delegate,
        }

    # ── Visit Tracker ──
    visit_tracker = {"by_delegate": []}
    if visits_df is not None and hasattr(visits_df, "empty") and not visits_df.empty:
        vt_delegates = []
        for mr_id_key, grp in visits_df.groupby("MR_ID"):
            mr_name = (
                mr_display_name(mr_id_key)
                if mr_id_key not in ("UNKNOWN", "")
                else (str(grp["MR"].iloc[0]) if not grp.empty else mr_id_key)
            )
            visits_list = []
            for _, vrow in grp.iterrows():
                date_val = vrow.get("Visit_Date")
                date_str = str(date_val)[:10] if date_val is not None and str(date_val) not in ("NaT", "nan", "") else ""
                if not date_str:
                    continue
                visits_list.append({
                    "date":       date_str,
                    "doctor":     str(vrow.get("Doctor",     "")),
                    "speciality": str(vrow.get("Speciality", "")),
                    "clinic":     str(vrow.get("Clinic",     "")),
                })
            if not visits_list:
                continue
            vt_delegates.append({
                "mr":             mr_name,
                "mr_id":          mr_id_key,
                "total_visits":   len(visits_list),
                "unique_doctors": len(set(v["doctor"] for v in visits_list)),
                "visits":         visits_list,
            })
        vt_delegates.sort(key=lambda x: x["total_visits"], reverse=True)
        visit_tracker = {"by_delegate": vt_delegates}

    result = safe_json({
        "month":              month,
        "kpis":               kpis,
        "target_vs_achieved": target_vs_achieved,
        "product_sales":      product_sales,
        "delegate_table":     delegate_table,
        "distributor_sales":  distributor_sales,
        "activity_expenses":  activity_expenses,
        "call_breakdown":     call_breakdown,
        "tour_plan":          tour_plan,
        "visit_tracker":      visit_tracker,
    })
    await set_api_cache(cache_key, result)
    return result
