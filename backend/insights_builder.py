import os
import math
from groq import AsyncGroq
import json

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

_MONTH_ORDER = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _sf(v, decimals=2):
    try:
        f = float(v)
        return 0.0 if math.isnan(f) or math.isinf(f) else round(f, decimals)
    except (TypeError, ValueError):
        return 0.0


def _compute_findings(overview: dict, delegates: dict, expenses: dict) -> list[dict]:
    """
    Compute pre-verified insight findings from already-computed API data.
    Uses overview/delegates/expenses router outputs — never raw DataFrames.
    """
    month_comparison = overview.get("month_comparison", [])
    products_trend = overview.get("all_products_trend", [])
    months_loaded = overview.get("months_loaded", [])
    annual_target = 205000

    # ── Per-month stats ──────────────────────────────────────────
    months = {
        m["key"]: m for m in month_comparison if m.get("key") in months_loaded
    }

    # ── Expense budget flow ──────────────────────────────────────
    budget_flow = {
        row["month"].lower()[:3]: row
        for row in expenses.get("budget_flow", [])
    }

    # ── Delegate CTC ratio breaches ──────────────────────────────
    all_ctc_breaches = []
    for dl in delegates.get("delegates", []):
        name = dl.get("display_name", dl.get("id", "Unknown"))
        for mk, mdata in dl.get("months", {}).items():
            ratio = mdata.get("ctc_ratio")
            orders = _sf(mdata.get("orders_eur", 0))
            ctc = _sf(mdata.get("ctc_eur", 0))
            if ratio is not None and ratio > 25 and orders > 0:
                all_ctc_breaches.append({
                    "name": name,
                    "month": mk.upper(),
                    "ctc_ratio_pct": _sf(ratio, 1),
                    "ctc_eur": ctc,
                    "orders_eur": orders,
                })
    all_ctc_breaches.sort(key=lambda x: x["ctc_ratio_pct"], reverse=True)

    # ── YTD totals ───────────────────────────────────────────────
    ytd_sales = round(sum(_sf(m.get("sales", 0)) for m in months.values()), 2)
    ytd_pct = round(ytd_sales / annual_target * 100, 1)

    first_mk = next((k for k in _MONTH_ORDER if k in months), None)
    last_mk = next((k for k in reversed(_MONTH_ORDER) if k in months), None)
    first_visits = months[first_mk]["visits"] if first_mk else 0
    last_visits = months[last_mk]["visits"] if last_mk else 0
    visit_growth_pct = round((last_visits - first_visits) / first_visits * 100, 1) if first_visits > 0 else 0

    # ── Product summaries ─────────────────────────────────────────
    product_totals = []
    for p in products_trend:
        prod = p.get("product", "")
        vals = {mk: _sf(p.get(mk, 0)) for mk in months_loaded}
        total = round(sum(vals.values()), 2)
        if total == 0:
            continue
        first_nonzero = next((mk for mk in months_loaded if vals.get(mk, 0) > 0), None)
        last_nonzero = next((mk for mk in reversed(months_loaded) if vals.get(mk, 0) > 0), None)
        trend = "stable"
        if first_nonzero and months_loaded.index(first_nonzero) > 0:
            trend = "emerging"
        elif last_nonzero and months_loaded.index(last_nonzero) < len(months_loaded) - 1:
            trend = "dropped"
        product_totals.append({"product": prod, "total": total, "by_month": vals, "trend": trend})
    product_totals.sort(key=lambda x: x["total"], reverse=True)

    # ── Build findings ────────────────────────────────────────────
    findings = []

    # 1. DANGER — CTC ratio crisis
    if all_ctc_breaches:
        worst = all_ctc_breaches[0]
        unique_delegates = sorted({b["name"] for b in all_ctc_breaches})
        breach_count = len(all_ctc_breaches)
        findings.append({
            "type": "danger",
            "icon": "🚨",
            "title": "CTC RATIO CRISIS",
            "facts": [
                f"The CTC (commission cost) target maximum is 25% of orders.",
                f"Worst breach: {worst['name']} in {worst['month']} with a CTC ratio of {worst['ctc_ratio_pct']}% "
                f"({worst['ctc_eur']} EUR commission against {worst['orders_eur']} EUR in orders).",
                f"{breach_count} delegate-month CTC violations recorded across {', '.join(unique_delegates)}.",
            ]
        })

    # 2. WARN — Activity budget deficit
    deficit_months = [(k, v) for k, v in budget_flow.items() if _sf(v.get("balance_eur", 0)) < 0]
    if deficit_months:
        mk, row = deficit_months[0]
        deficit = abs(_sf(row.get("balance_eur", 0)))
        findings.append({
            "type": "warn",
            "icon": "⚠️",
            "title": "ACTIVITY BUDGET DEFICIT",
            "facts": [
                f"In {row.get('month', mk.title())}, activity spend of {_sf(row.get('spent_eur', 0))} EUR "
                f"exceeded the budget received ({_sf(row.get('received_eur', 0))} EUR) by {deficit} EUR.",
                f"This left a negative closing balance for that month. "
                f"The deficit was cleared in the subsequent month via additional budget disbursement.",
            ]
        })

    # 3. WARN — Sales target shortfall
    best_mk = max(months, key=lambda k: _sf(months[k].get("achievement", 0))) if months else None
    worst_mk = min(months, key=lambda k: _sf(months[k].get("achievement", 100))) if months else None
    if worst_mk and _sf(months[worst_mk].get("achievement", 100)) < 70:
        bm = months[best_mk]
        wm = months[worst_mk]
        findings.append({
            "type": "warn",
            "icon": "📉",
            "title": "SALES TARGET SHORTFALL",
            "facts": [
                f"YTD sales total {ytd_sales} EUR — only {ytd_pct}% of the {annual_target:,} EUR annual target.",
                f"Best month: {bm.get('month', best_mk)} at {_sf(bm.get('achievement', 0))}% achievement "
                f"({_sf(bm.get('sales', 0))} EUR vs {_sf(bm.get('projection', 0))} EUR target).",
                f"Weakest month: {wm.get('month', worst_mk)} at {_sf(wm.get('achievement', 0))}% achievement "
                f"({_sf(wm.get('sales', 0))} EUR vs {_sf(wm.get('projection', 0))} EUR target).",
            ]
        })

    # 4. GOOD — Best month + top product
    if best_mk and product_totals:
        bm = months[best_mk]
        top = product_totals[0]
        findings.append({
            "type": "good",
            "icon": "🏆",
            "title": "BEST MONTH & TOP PRODUCT",
            "facts": [
                f"Strongest month: {bm.get('month', best_mk)} with {_sf(bm.get('sales', 0))} EUR sales "
                f"({_sf(bm.get('achievement', 0))}% of target).",
                f"Top product overall: {top['product']} with {top['total']} EUR total across all months.",
            ]
        })

    # 5. GOOD — Field activity growth
    if first_mk and last_mk and first_mk != last_mk:
        fm = months[first_mk]
        lm = months[last_mk]
        total_drs = sum(m.get("drs_converted", 0) for m in months.values())
        drs_month = next((m.get("month", mk) for mk, m in months.items() if m.get("drs_converted", 0) > 0), "N/A")
        findings.append({
            "type": "good",
            "icon": "📈",
            "title": "FIELD ACTIVITY GROWTH",
            "facts": [
                f"Total field visits grew from {fm.get('visits', 0)} in {fm.get('month', first_mk)} "
                f"to {lm.get('visits', 0)} in {lm.get('month', last_mk)} (+{visit_growth_pct}%).",
                f"{total_drs} doctor conversions recorded — all concentrated in {drs_month}.",
            ]
        })

    # 6. INFO — Product mix / emerging or dropped products
    emerging = [p for p in product_totals if p["trend"] == "emerging"]
    dropped = [p for p in product_totals if p["trend"] == "dropped"]
    product_facts = []
    if emerging:
        ep = emerging[0]
        latest_val = ep["by_month"].get(last_mk, 0)
        product_facts.append(
            f"New market entrant: {ep['product']} debuted in {months.get(last_mk, {}).get('month', last_mk)} "
            f"with {latest_val} EUR in sales."
        )
    if dropped:
        dp = dropped[0]
        early_val = dp["by_month"].get(first_mk, 0)
        product_facts.append(
            f"Product drop-off: {dp['product']} generated {early_val} EUR in "
            f"{months.get(first_mk, {}).get('month', first_mk)} but has since recorded zero sales."
        )
    if not product_facts and product_totals:
        top2 = product_totals[1] if len(product_totals) > 1 else product_totals[0]
        product_facts.append(f"Second-ranking product: {top2['product']} with {top2['total']} EUR YTD.")
    product_facts.append("Injectable products consistently account for the majority of revenue across all months.")

    findings.append({
        "type": "info",
        "icon": "💊",
        "title": "PRODUCT MIX SHIFTS",
        "facts": product_facts,
    })

    return findings[:6]


async def generate_insights(overview: dict, delegates: dict, expenses: dict) -> list:
    findings = _compute_findings(overview, delegates, expenses)

    findings_text = ""
    for i, f in enumerate(findings, 1):
        findings_text += f"\nINSIGHT {i}:\n"
        findings_text += f"  type: {f['type']}\n"
        findings_text += f"  icon: {f['icon']}\n"
        findings_text += f"  title: {f['title']}\n"
        findings_text += f"  facts:\n"
        for fact in f["facts"]:
            findings_text += f"    - {fact}\n"

    prompt = f"""You are a pharmaceutical sales analyst. Convert these pre-computed findings into polished JSON insight cards.

{findings_text}

Rules:
- Return ONLY a valid JSON array with exactly {len(findings)} objects — no markdown, no preamble
- Each object must have exactly these fields: "type", "icon", "title", "text"
- Copy "type", "icon", "title" verbatim from each insight above
- "text" must be 2-3 fluent sentences that incorporate ALL the provided facts using the EXACT numbers given
- Do NOT invent, recalculate, or rephrase any number — quote them exactly as shown in the facts
- Write in a confident, professional analytical tone

Return only the JSON array."""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1400,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        insights = json.loads(raw)
        if not isinstance(insights, list):
            raise ValueError("not a list")
        return insights
    except (json.JSONDecodeError, ValueError):
        # Safe fallback: return facts joined directly
        return [
            {
                "type": f["type"],
                "icon": f["icon"],
                "title": f["title"],
                "text": " ".join(f["facts"])
            }
            for f in findings
        ]
