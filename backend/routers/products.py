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

    month_keys = [k for k in data.keys() if not k.startswith('_')]

    # Collect all products
    all_products = set()
    for key in month_keys:
        d = data.get(key, {})
        s = d.get("sales", {}).get("current")
        if s is not None and not s.empty:
            all_products.update(s["Product"].tolist())

    # Trend per product (one entry per product, one key per loaded month)
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

    # YTD achieved per product
    product_ytd = {t["product"]: round(sum(t.get(k, 0) for k in month_keys), 2) for t in q1_trend}

    # Annual targets from ANNUAL PROJECTIONS sheet (keyed by display name)
    from main import app_state
    annual_proj = app_state.get("annual_projections", {})

    # Build annual_vs_q1 (named for backwards compat; contains YTD data)
    all_prods = set(product_ytd)
    annual_vs_q1 = []
    for prod in all_prods:
        annual_vs_q1.append({
            "product":       prod,
            "annual_target": annual_proj.get(prod),  # None if sheet not loaded
            "ytd_achieved":  product_ytd.get(prod, 0),
        })
    annual_vs_q1 = sorted(annual_vs_q1, key=lambda x: x["ytd_achieved"], reverse=True)

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
        "month_sales":     month_sales,
        "month_units":     month_units,
        # Backwards-compat aliases
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
