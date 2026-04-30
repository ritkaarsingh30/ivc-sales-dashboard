import os
from groq import AsyncGroq
import json

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


def build_summary(data: dict) -> dict:
    """Build a tight structured summary from the loaded data for Groq."""
    summary = {}
    for month_key in ["jan", "feb", "mar"]:
        d = data.get(month_key, {})
        monthly = d.get("monthly", {})
        delegates = monthly.get("delegates") if monthly else None
        expense = d.get("expense", {}) or {}
        sales_data = d.get("sales", {})
        sales = sales_data.get("current") if sales_data else None
        proj_data = d.get("projection", {}) or {}
        proj = proj_data.get("projection") if proj_data else None

        total_sales = float(sales["TOTAL_VALUE_EUR"].sum()) if sales is not None and not sales.empty else 0
        total_target = float(proj["Target_Value_EUR"].sum()) if proj is not None and not proj.empty else 0

        delegate_summary = []
        if delegates is not None and not delegates.empty:
            for _, row in delegates.iterrows():
                delegate_summary.append({
                    "name": str(row.get("Delegate", "")),
                    "total_calls": int(row.get("TotalCalls", 0) or 0),
                    "prescriber": int(row.get("Prescriber", 0) or 0),
                    "drs_converted": int(row.get("DrsConverted", 0) or 0),
                    "days_worked": int(row.get("DaysWorked", 0) or 0),
                    "days_target": int(row.get("DaysTarget", 0) or 0),
                    "ctc": float(row.get("CTC", 0) or 0),
                    "total_orders": float(row.get("TotalOrders", 0) or 0),
                })

        summary[month_key] = {
            "total_sales_eur": round(total_sales, 2),
            "total_target_eur": round(total_target, 2),
            "achievement_pct": round(total_sales / total_target * 100, 1) if total_target > 0 else None,
            "activity_spent_fcfa": expense.get("total_spent_fcfa", 0),
            "budget_received_fcfa": expense.get("total_received_fcfa", 0),
            "balance_fcfa": expense.get("balance_fcfa", 0),
            "delegates": delegate_summary,
        }
    return summary


async def generate_insights(data: dict) -> list:
    summary = build_summary(data)

    prompt = f"""You are a pharmaceutical sales analyst. Analyze this Q1 2026 field force data for Ivory Coast and return exactly 6 insights as a JSON array.

DATA:
{json.dumps(summary, indent=2)}

Rules:
- Return ONLY a valid JSON array, no markdown, no preamble
- Each insight must have exactly these fields:
  - "type": one of "danger", "warn", "good", "info"
  - "icon": one relevant emoji
  - "title": short uppercase label (max 5 words)
  - "text": 2-3 sentence analytical observation with specific numbers from the data
- Focus on: budget anomalies, CTC ratio breaches (target is max 25%), sales vs targets, doctor conversion patterns, month-over-month trends, product performance shifts
- Be specific with numbers, do not be vague
- Distribute types: at least 1 danger, 1 warn, 2 good, and mix the rest

Return only the JSON array."""

    response = await client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1200,
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        insights = json.loads(raw)
        return insights
    except json.JSONDecodeError:
        return [
            {"type": "warn", "icon": "⚠️", "title": "INSIGHTS UNAVAILABLE",
             "text": "Could not parse AI insights. Check GROQ_API_KEY and retry."}
        ]
