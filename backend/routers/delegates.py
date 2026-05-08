"""
GET /api/delegates — cross-month MR performance with full ROI analysis
"""
import json
import math
import numpy as np
from fastapi import APIRouter
from constants import FCFA_TO_EUR
from name_map import mr_display_name
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()

TERRITORY_LABELS = {
    "ZONE_YOP_EAST":  "Yopougon East",
    "ZONE_YOP_WEST":  "Yopougon West",
    "ZONE_ADJAME":    "Adjamé",
    "ZONE_COCODY":    "Cocody",
    "ZONE_MARCORI":   "Marcori",
    "UNKNOWN":        "—",
}

def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )

def _get_data():
    from main import app_state
    return app_state.get("data", {})

def _get_delegates_df(data, month_key):
    d = data.get(month_key, {})
    return (d.get("monthly") or {}).get("delegates")

def _si(v):
    try:
        f = float(v)
        return 0 if math.isnan(f) or math.isinf(f) else int(f)
    except (TypeError, ValueError):
        return 0

def _sf(v):
    try:
        f = float(v)
        return 0.0 if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return 0.0

def _row_metrics(row):
    calls    = _si(row.get("TotalCalls", 0))
    pres     = _si(row.get("Prescriber", 0))
    pharm    = _si(row.get("PharmacyCalls", 0))
    drs      = _si(row.get("DrsConverted", 0))
    days_w   = _si(row.get("DaysWorked", 0))
    days_t   = _si(row.get("DaysTarget", 0))
    avg_cpd  = round(_sf(row.get("AvgCallsPerDay", 0)), 2)
    orders   = round(_sf(row.get("TotalOrders", 0)), 2)
    ctc      = round(_sf(row.get("CTC", 0)), 2)
    ctc_ratio = round(ctc / orders * 100, 1) if orders > 0 else None
    util_pct  = round(days_w / days_t * 100, 1) if days_t > 0 else None
    return {
        "calls": calls, "prescriber": pres, "pharmacy": pharm,
        "drs_converted": drs, "days_worked": days_w, "days_target": days_t,
        "avg_calls_day": avg_cpd, "orders_eur": orders, "ctc_eur": ctc,
        "ctc_ratio": ctc_ratio, "days_utilization": util_pct,
    }

_EMPTY_MONTH = {
    "calls": 0, "prescriber": 0, "pharmacy": 0, "drs_converted": 0,
    "days_worked": 0, "days_target": 0, "avg_calls_day": 0.0,
    "orders_eur": 0.0, "ctc_eur": 0.0,
    "ctc_ratio": None, "days_utilization": None,
    "tour_planned": 0, "tour_covered": 0, "tour_coverage_pct": None,
}


@router.get("/delegates")
async def get_delegates():
    cached = await get_api_cache("delegates")
    if cached:
        return cached

    data = _get_data()
    month_keys = list(data.keys())  # dynamic — whatever months are loaded

    # ── Collect all unique delegate IDs ──────────────────────────────────────
    all_ids: set[str] = set()
    for key in month_keys:
        df = _get_delegates_df(data, key)
        if df is not None and not df.empty:
            all_ids.update(df["Delegate"].tolist())

    # ── Build per-delegate detail ─────────────────────────────────────────────
    delegates_detail = []

    for del_id in sorted(all_ids):
        months_data: dict = {}
        territory_raw = ""
        display_name_raw = ""

        q1 = dict(calls=0, prescriber=0, pharmacy=0, drs_converted=0,
                  days_worked=0, days_target=0, orders_eur=0.0, ctc_eur=0.0,
                  tour_planned=0, tour_covered=0)

        for key in month_keys:
            df = _get_delegates_df(data, key)
            m = dict(_EMPTY_MONTH)

            if df is not None and not df.empty:
                rows = df[df["Delegate"] == del_id]
                if not rows.empty:
                    row = rows.iloc[0]
                    if not territory_raw:
                        territory_raw = str(row.get("Territory", ""))
                    if not display_name_raw:
                        display_name_raw = str(row.get("Delegate_Raw", "")).strip()
                    m.update(_row_metrics(row))

            # Tour plan coverage for this delegate this month
            tour_df = data.get(key, {}).get("tour")
            if tour_df is not None and hasattr(tour_df, "empty") and not tour_df.empty:
                mr_rows = tour_df[tour_df["MR"] == del_id]
                if not mr_rows.empty:
                    tp = len(mr_rows)
                    tc = int(mr_rows["Covered"].sum())
                    m["tour_planned"]      = tp
                    m["tour_covered"]      = tc
                    m["tour_coverage_pct"] = round(tc / tp * 100, 1) if tp > 0 else None

            months_data[key] = m

            # Accumulate Q1 totals
            for f in ("calls","prescriber","pharmacy","drs_converted","days_worked","days_target","tour_planned","tour_covered"):
                q1[f] += m[f]
            q1["orders_eur"] += m["orders_eur"]
            q1["ctc_eur"]    += m["ctc_eur"]

        # Q1 derived metrics
        q1["orders_eur"]      = round(q1["orders_eur"], 2)
        q1["ctc_eur"]         = round(q1["ctc_eur"], 2)
        q1["ctc_ratio"]       = round(q1["ctc_eur"] / q1["orders_eur"] * 100, 1) if q1["orders_eur"] > 0 else None
        q1["days_utilization"]= round(q1["days_worked"] / q1["days_target"] * 100, 1) if q1["days_target"] > 0 else None
        q1["conversion_pct"]  = round(q1["drs_converted"] / q1["calls"] * 100, 1) if q1["calls"] > 0 else None
        q1["tour_coverage_pct"]= round(q1["tour_covered"] / q1["tour_planned"] * 100, 1) if q1["tour_planned"] > 0 else None

        # Resolve display name: use name_map first, fall back to raw, then ID
        disp = mr_display_name(del_id)
        if not disp or disp == del_id:
            disp = display_name_raw.split()[0] if display_name_raw else del_id

        # Short name (first word) for chart labels
        short = disp.split()[0] if disp and disp not in ("UNKNOWN", "") else display_name_raw.split()[0] if display_name_raw else del_id

        territory_label = TERRITORY_LABELS.get(territory_raw, territory_raw or "—")

        delegates_detail.append({
            "id":           del_id,
            "display_name": disp,
            "short_name":   short,
            "territory":    territory_label,
            "months":       months_data,
            "q1":           q1,
        })

    # ── Q1 overall summary ────────────────────────────────────────────────────
    total_orders = sum(d["q1"]["orders_eur"] for d in delegates_detail)
    total_ctc    = sum(d["q1"]["ctc_eur"]    for d in delegates_detail)
    q1_summary = {
        "total_calls":       sum(d["q1"]["calls"]         for d in delegates_detail),
        "total_prescriber":  sum(d["q1"]["prescriber"]    for d in delegates_detail),
        "total_pharmacy":    sum(d["q1"]["pharmacy"]       for d in delegates_detail),
        "total_drs":         sum(d["q1"]["drs_converted"] for d in delegates_detail),
        "total_days_worked": sum(d["q1"]["days_worked"]   for d in delegates_detail),
        "total_days_target": sum(d["q1"]["days_target"]   for d in delegates_detail),
        "total_orders_eur":  round(total_orders, 2),
        "total_ctc_eur":     round(total_ctc,    2),
        "overall_ctc_ratio": round(total_ctc / total_orders * 100, 1) if total_orders > 0 else None,
    }

    # ── Legacy structures (kept for any callers) ──────────────────────────────
    visit_counts = []
    for d in delegates_detail:
        entry = {"mr": d["display_name"], "fullname": d["display_name"]}
        for key in month_keys:
            entry[key] = d["months"][key]["calls"]
        visit_counts.append(entry)

    avg_per_day = []
    for key in month_keys:
        label = key.capitalize()
        df = _get_delegates_df(data, key)
        entry = {"month": label}
        if df is not None and not df.empty:
            entry["overall"] = round(float(df["AvgCallsPerDay"].sum()), 2)
            for d in delegates_detail:
                rows = df[df["Delegate"] == d["id"]]
                entry[d["display_name"].lower()] = round(_sf(rows["AvgCallsPerDay"].iloc[0]) if not rows.empty else 0, 2)
        else:
            entry["overall"] = None
        avg_per_day.append(entry)

    ctc_ratios = [
        {
            "mr": d["short_name"], "fullname": d["display_name"],
            **{key: d["months"][key]["ctc_ratio"] for key in month_keys}
        }
        for d in delegates_detail
    ]

    result = safe_json({
        "q1_summary":       q1_summary,
        "delegates":        delegates_detail,
        "visit_counts":     visit_counts,
        "avg_per_day":      avg_per_day,
        "ctc_ratios":       ctc_ratios,
    })
    await set_api_cache("delegates", result)
    return result
