"""
GET /api/delegates — cross-month MR performance
"""
import json
import numpy as np
from fastapi import APIRouter
from constants import FCFA_TO_EUR
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()


def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )


def _get_data():
    from main import app_state
    return app_state.get("data", {})


def _get_delegates_df(data, month_key):
    d = data.get(month_key, {})
    monthly = d.get("monthly", {}) or {}
    return monthly.get("delegates")


@router.get("/delegates")
async def get_delegates():
    cached = await get_api_cache("delegates")
    if cached:
        return cached

    data = _get_data()
    month_keys = ["jan", "feb", "mar"]

    # Collect all unique delegate names across months
    all_names = set()
    for key in month_keys:
        df = _get_delegates_df(data, key)
        if df is not None and not df.empty:
            all_names.update(df["Delegate"].tolist())

    # Visit counts per MR per month
    visit_counts = []
    for name in sorted(all_names):
        entry = {"mr": name.split()[-1] if name else name, "fullname": name}
        for key in month_keys:
            df = _get_delegates_df(data, key)
            if df is not None and not df.empty:
                row = df[df["Delegate"] == name]
                entry[key] = int(row["TotalCalls"].sum()) if not row.empty else 0
            else:
                entry[key] = 0
        visit_counts.append(entry)

    # Orders per MR (only months that have order data)
    orders = []
    for name in sorted(all_names):
        entry = {"mr": name.split()[-1] if name else name, "fullname": name}
        has_data = False
        for key in month_keys:
            df = _get_delegates_df(data, key)
            if df is not None and not df.empty:
                row = df[df["Delegate"] == name]
                if not row.empty:
                    val = float(row["TotalOrders"].iloc[0] or 0)
                    entry[f"{key}_eur"] = round(val, 2) if val > 0 else None
                    if val > 0:
                        has_data = True
                else:
                    entry[f"{key}_eur"] = None
            else:
                entry[f"{key}_eur"] = None
        if has_data:
            orders.append(entry)

    # Avg calls per day across months
    avg_per_day = []
    for key in month_keys:
        label = key.capitalize()
        df = _get_delegates_df(data, key)
        entry = {"month": label}
        if df is not None and not df.empty:
            # Overall sum of avg (as reported in monthly reports)
            overall = round(float(df["AvgCallsPerDay"].sum()), 2)
            entry["overall"] = overall
            for name in sorted(all_names):
                short = name.split()[-1].lower() if name else "unknown"
                row = df[df["Delegate"] == name]
                if not row.empty:
                    entry[short] = round(float(row["AvgCallsPerDay"].iloc[0] or 0), 2)
                else:
                    entry[short] = None
        else:
            entry["overall"] = None
        avg_per_day.append(entry)

    # CTC Ratios per MR per month
    ctc_ratios = []
    for name in sorted(all_names):
        entry = {"mr": name.split()[-1] if name else name, "fullname": name}
        for key in month_keys:
            df = _get_delegates_df(data, key)
            if df is not None and not df.empty:
                row = df[df["Delegate"] == name]
                if not row.empty:
                    orders_val = float(row["TotalOrders"].iloc[0] or 0)
                    ctc_val = float(row["CTC"].iloc[0] or 0)
                    ratio = round(ctc_val / orders_val * 100, 1) if orders_val > 0 else None
                    entry[key] = ratio
                else:
                    entry[key] = None
            else:
                entry[key] = None
        ctc_ratios.append(entry)

    result = safe_json({
        "visit_counts": visit_counts,
        "orders": orders,
        "avg_per_day": avg_per_day,
        "ctc_ratios": ctc_ratios,
    })
    await set_api_cache("delegates", result)
    return result
