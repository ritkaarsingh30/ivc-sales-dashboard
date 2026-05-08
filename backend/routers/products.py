"""
GET /api/products — Q1 product trend, annual vs Q1, category mix
"""
import json
import numpy as np
from fastapi import APIRouter
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()


def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )


def _get_data():
    from main import app_state
    return app_state.get("data", {})


@router.get("/products")
async def get_products():
    cached = await get_api_cache("products")
    if cached:
        return cached

    data = _get_data()

    month_keys = ["jan", "feb", "mar"]

    # Collect all products
    all_products = set()
    for key in month_keys:
        d = data.get(key, {})
        s = d.get("sales", {}).get("current")
        if s is not None and not s.empty:
            all_products.update(s["Product"].tolist())

    # Q1 trend per product
    q1_trend = []
    for prod in sorted(all_products):
        entry = {"product": prod}
        for key in month_keys:
            d = data.get(key, {})
            s = d.get("sales", {}).get("current")
            if s is not None and not s.empty:
                row = s[s["Product"] == prod]
                entry[key] = round(float(row["TOTAL_VALUE_EUR"].sum()), 2) if not row.empty else 0
            else:
                entry[key] = 0
        q1_trend.append(entry)

    # Annual vs Q1 — use Jan projection as proxy for annual (or sum of all month projections)
    annual_map = {}
    for key in month_keys:
        d = data.get(key, {})
        proj = d.get("projection", {})
        if proj:
            proj_df = proj.get("projection")
            if proj_df is not None and not proj_df.empty:
                for _, row in proj_df.iterrows():
                    prod = row["Product"]
                    # Annual is typically 3x quarterly projection; use what we have
                    if prod not in annual_map:
                        annual_map[prod] = {"annual_target": 0, "q1_achieved": 0}
                    annual_map[prod]["annual_target"] += round(float(row.get("Target_Value_EUR", 0)), 2)

    # Fill Q1 achieved
    for key in month_keys:
        d = data.get(key, {})
        s = d.get("sales", {}).get("current")
        if s is not None and not s.empty:
            for prod, vals in annual_map.items():
                row = s[s["Product"] == prod]
                if not row.empty:
                    annual_map[prod]["q1_achieved"] = annual_map[prod].get("q1_achieved", 0) + round(float(row["TOTAL_VALUE_EUR"].sum()), 2)

    annual_vs_q1 = []
    for prod, vals in annual_map.items():
        at = vals["annual_target"]
        ach = vals["q1_achieved"]
        pct = round(ach / at * 100, 1) if at > 0 else None
        annual_vs_q1.append({
            "product": prod,
            "annual_target": round(at, 2),
            "q1_achieved": round(ach, 2),
            "pct": pct,
        })
    annual_vs_q1 = sorted(annual_vs_q1, key=lambda x: x["q1_achieved"], reverse=True)

    # Category mix per month
    category_mix = {}
    for key in month_keys:
        d = data.get(key, {})
        s = d.get("sales", {}).get("current")
        if s is not None and not s.empty:
            tablet = round(float(s[s["Category"] == "TABLET"]["TOTAL_VALUE_EUR"].sum()), 2)
            inj = round(float(s[s["Category"] == "INJECTABLE"]["TOTAL_VALUE_EUR"].sum()), 2)
        else:
            tablet, inj = 0, 0
        category_mix[key] = {"tablet": tablet, "injectable": inj}

    # KPI summary — totals + per-month sales & units
    month_sales = {}
    month_units = {}
    for key in month_keys:
        d = data.get(key, {})
        s = d.get("sales", {}).get("current")
        if s is not None and not s.empty:
            month_sales[key] = round(float(s["TOTAL_VALUE_EUR"].sum()), 2)
            month_units[key] = int(s["TOTAL_SALES"].sum()) if "TOTAL_SALES" in s.columns else 0
        else:
            month_sales[key] = 0
            month_units[key] = 0

    q1_kpis = {
        "total_sales_eur": round(sum(month_sales.values()), 2),
        "total_units":     sum(month_units.values()),
        "jan_sales":  month_sales.get("jan", 0),
        "feb_sales":  month_sales.get("feb", 0),
        "mar_sales":  month_sales.get("mar", 0),
        "jan_units":  month_units.get("jan", 0),
        "feb_units":  month_units.get("feb", 0),
        "mar_units":  month_units.get("mar", 0),
    }

    result = safe_json({
        "q1_kpis":      q1_kpis,
        "q1_trend":     q1_trend,
        "annual_vs_q1": annual_vs_q1,
        "category_mix": category_mix,
    })
    await set_api_cache("products", result)
    return result
