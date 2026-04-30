"""
GET /api/expenses — budget flow, activity type totals, all expenses
"""
import json
import numpy as np
from fastapi import APIRouter
from constants import FCFA_TO_EUR
from name_map import activity_display_name

router = APIRouter()


def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )


def _get_data():
    from main import app_state
    return app_state.get("data", {})


@router.get("/expenses")
def get_expenses():
    data = _get_data()

    month_labels = {"jan": "January", "feb": "February", "mar": "March"}

    # Budget flow
    budget_flow = []
    for key, label in month_labels.items():
        d = data.get(key, {})
        expense = d.get("expense", {}) or {}
        received = float(expense.get("total_received_fcfa", 0) or 0)
        spent = float(expense.get("total_spent_fcfa", 0) or 0)
        balance = float(expense.get("balance_fcfa", 0) or 0)
        budget_flow.append({
            "month": label,
            "received_fcfa": round(received, 2),
            "spent_fcfa": round(spent, 2),
            "balance_fcfa": round(balance, 2),
            "received_eur": round(received / FCFA_TO_EUR, 2),
            "spent_eur": round(spent / FCFA_TO_EUR, 2),
            "balance_eur": round(balance / FCFA_TO_EUR, 2),
        })

    # Activity type totals across Q1
    activity_totals = {}
    all_expenses = []

    for key, label in month_labels.items():
        d = data.get(key, {})
        expense = d.get("expense", {}) or {}
        ae = expense.get("activity_exp")
        if ae is not None and not ae.empty:
            for _, row in ae.iterrows():
                act = row.get("Activity", "Unknown")
                act_id = row.get("Activity_ID", "UNKNOWN")
                amount = float(row.get("Amount_FCFA", 0) or 0)

                if act not in activity_totals:
                    activity_totals[act] = 0
                activity_totals[act] += amount

                all_expenses.append({
                    "month": label,
                    "sn": int(row.get("SN", 0)),
                    "doctor": row.get("Doctor", ""),
                    "hospital": row.get("Hospital", ""),
                    "speciality": row.get("Speciality", ""),
                    "activity": act,
                    "activity_id": act_id,
                    "products": row.get("Products", ""),
                    "amount_fcfa": round(amount, 2),
                    "amount_eur": round(amount / FCFA_TO_EUR, 2),
                    "responsible": row.get("Responsible", ""),
                })

    activity_type_totals = [
        {"activity": act, "amount_fcfa": round(total, 2), "amount_eur": round(total / FCFA_TO_EUR, 2)}
        for act, total in sorted(activity_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return safe_json({
        "budget_flow": budget_flow,
        "activity_type_totals": activity_type_totals,
        "all_expenses": all_expenses,
    })
