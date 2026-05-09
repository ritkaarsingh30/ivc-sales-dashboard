"""
GET /api/activities — Activity Plan vs Actual Execution comparison.

Matches each planned row (Projection ACTIVITY PLAN tab) to an actual expense row
(Expense ACTIVITY EXP. tab) by (Doctor, ActivityType). Returns:
  - matched:          planned and executed, with outcome data
  - planned_not_done: planned but no matching actual row found
  - unplanned_done:   actual rows with no matching plan row
"""
import json
import numpy as np
import pandas as pd
from fastapi import APIRouter
from name_map import activity_display_name, mr_display_name
from cache.redis_client import get_api_cache, set_api_cache

router = APIRouter()

MONTH_FULL_NAMES = {
    "jan": "January",   "feb": "February",  "mar": "March",     "apr": "April",
    "may": "May",       "jun": "June",       "jul": "July",      "aug": "August",
    "sep": "September", "oct": "October",   "nov": "November",  "dec": "December",
}


def safe_json(obj):
    return json.loads(
        json.dumps(obj, default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x)
    )


def _get_data():
    from main import app_state
    return app_state.get("data", {})


def _sf(v, default=0.0):
    try:
        f = float(v)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _si(v):
    try:
        f = float(v)
        return 0 if (np.isnan(f) or np.isinf(f)) else int(f)
    except (TypeError, ValueError):
        return 0


def _match_month(plan_df: pd.DataFrame | None, expense_df: pd.DataFrame | None):
    """
    Match plan rows to expense rows by (Doctor, Activity_ID).
    Returns (matched, planned_not_done, unplanned_done) — all lists of dicts.
    """
    matched, planned_not_done = [], []

    plan_empty = plan_df is None or (hasattr(plan_df, "empty") and plan_df.empty)
    exp_empty  = expense_df is None or (hasattr(expense_df, "empty") and expense_df.empty)

    if plan_empty and exp_empty:
        return [], [], []

    # Build a lookup from expense rows by (doctor, activity_id) for O(1) matching
    exp_lookup: dict[tuple, list] = {}
    if not exp_empty:
        for idx, er in expense_df.iterrows():
            k = (str(er.get("Doctor", "")), str(er.get("Activity_ID", "")))
            exp_lookup.setdefault(k, []).append((idx, er))

    used_idx: set = set()

    if not plan_empty:
        for _, pr in plan_df.iterrows():
            doc    = str(pr.get("Doctor", ""))
            act_id = str(pr.get("Activity", ""))   # normalized activity ID in plan
            key    = (doc, act_id)

            hit_list = [item for item in exp_lookup.get(key, []) if item[0] not in used_idx]

            if hit_list:
                idx, er = hit_list[0]
                used_idx.add(idx)
                outcome = er.get("Sales_Outcome", [])
                if not isinstance(outcome, list):
                    outcome = []
                outcome_eur = _sf(er.get("Sales_Outcome_EUR", 0))
                matched.append({
                    "doctor":            doc,
                    "hospital":          str(pr.get("Hospital", "")),
                    "speciality":        str(pr.get("Speciality", "")),
                    "delegate":          mr_display_name(str(pr.get("Delegate", ""))) if pr.get("Delegate") else "",
                    "area":              str(pr.get("Area", "")),
                    "activity":          activity_display_name(act_id),
                    "activity_id":       act_id,
                    "focus_products":    str(pr.get("Focus_Products", "")),
                    "planned_fcfa":      round(_sf(pr.get("Amount_FCFA")), 2),
                    "actual_fcfa":       round(_sf(er.get("Amount_FCFA")), 2),
                    "actual_eur":        round(_sf(er.get("Amount_EUR")), 2),
                    "variance_fcfa":     round(_sf(er.get("Amount_FCFA")) - _sf(pr.get("Amount_FCFA")), 2),
                    "sales_outcome":     outcome,
                    "sales_outcome_eur": round(outcome_eur, 2),
                    "has_outcome":       outcome_eur > 0,
                    "num_visits":        _si(er.get("Num_Visits", 0)),
                    "responsible":       str(er.get("Responsible", "")),
                    "status":            "executed",
                })
            else:
                planned_not_done.append({
                    "doctor":         doc,
                    "hospital":       str(pr.get("Hospital", "")),
                    "speciality":     str(pr.get("Speciality", "")),
                    "delegate":       mr_display_name(str(pr.get("Delegate", ""))) if pr.get("Delegate") else "",
                    "area":           str(pr.get("Area", "")),
                    "activity":       activity_display_name(act_id),
                    "activity_id":    act_id,
                    "focus_products": str(pr.get("Focus_Products", "")),
                    "planned_fcfa":   round(_sf(pr.get("Amount_FCFA")), 2),
                    "status":         "planned_not_done",
                })

    # Expense rows that didn't match any plan entry
    unplanned_done = []
    if not exp_empty:
        for idx, er in expense_df.iterrows():
            if idx in used_idx:
                continue
            outcome = er.get("Sales_Outcome", [])
            if not isinstance(outcome, list):
                outcome = []
            outcome_eur = _sf(er.get("Sales_Outcome_EUR", 0))
            unplanned_done.append({
                "doctor":            str(er.get("Doctor", "")),
                "hospital":          str(er.get("Hospital", "")),
                "speciality":        str(er.get("Speciality", "")),
                "activity":          str(er.get("Activity", "")),
                "activity_id":       str(er.get("Activity_ID", "")),
                "products":          str(er.get("Products", "")),
                "actual_fcfa":       round(_sf(er.get("Amount_FCFA")), 2),
                "actual_eur":        round(_sf(er.get("Amount_EUR")), 2),
                "sales_outcome":     outcome,
                "sales_outcome_eur": round(outcome_eur, 2),
                "has_outcome":       outcome_eur > 0,
                "num_visits":        _si(er.get("Num_Visits", 0)),
                "responsible":       str(er.get("Responsible", "")),
                "status":            "unplanned",
            })

    return matched, planned_not_done, unplanned_done


@router.get("/activities")
async def get_activities():
    cached = await get_api_cache("activities")
    if cached:
        return cached

    data = _get_data()
    by_month: dict = {}
    overall = {
        "total_planned": 0, "executed": 0, "not_executed": 0, "unplanned": 0,
        "total_outcome_eur": 0.0, "with_outcome": 0, "without_outcome": 0,
        "planned_budget_fcfa": 0.0, "actual_spent_fcfa": 0.0,
    }

    for key, month_data in data.items():
        plan_df    = (month_data.get("projection") or {}).get("activity_plan")
        expense_df = (month_data.get("expense") or {}).get("activity_exp")

        matched, planned_not_done, unplanned_done = _match_month(plan_df, expense_df)

        n_planned   = len(matched) + len(planned_not_done)
        n_executed  = len(matched)
        n_not_done  = len(planned_not_done)
        n_unplanned = len(unplanned_done)
        exec_rate   = round(n_executed / n_planned * 100, 1) if n_planned > 0 else 0.0

        total_outcome   = sum(r["sales_outcome_eur"] for r in matched)
        with_outcome    = sum(1 for r in matched if r["has_outcome"])
        without_outcome = n_executed - with_outcome
        planned_budget  = (
            sum(r["planned_fcfa"] for r in matched)
            + sum(r["planned_fcfa"] for r in planned_not_done)
        )
        actual_spent = (
            sum(r["actual_fcfa"] for r in matched)
            + sum(r["actual_fcfa"] for r in unplanned_done)
        )

        by_month[key] = {
            "label":            MONTH_FULL_NAMES.get(key, key.capitalize()),
            "matched":          matched,
            "planned_not_done": planned_not_done,
            "unplanned_done":   unplanned_done,
            "summary": {
                "total_planned":       n_planned,
                "executed":            n_executed,
                "not_executed":        n_not_done,
                "unplanned":           n_unplanned,
                "execution_rate_pct":  exec_rate,
                "planned_budget_fcfa": round(planned_budget, 2),
                "actual_spent_fcfa":   round(actual_spent, 2),
                "total_outcome_eur":   round(total_outcome, 2),
                "with_outcome":        with_outcome,
                "without_outcome":     without_outcome,
            },
        }

        overall["total_planned"]       += n_planned
        overall["executed"]            += n_executed
        overall["not_executed"]        += n_not_done
        overall["unplanned"]           += n_unplanned
        overall["total_outcome_eur"]   += total_outcome
        overall["with_outcome"]        += with_outcome
        overall["without_outcome"]     += without_outcome
        overall["planned_budget_fcfa"] += planned_budget
        overall["actual_spent_fcfa"]   += actual_spent

    overall["execution_rate_pct"]   = round(overall["executed"] / overall["total_planned"] * 100, 1) if overall["total_planned"] > 0 else 0.0
    overall["total_outcome_eur"]    = round(overall["total_outcome_eur"], 2)
    overall["planned_budget_fcfa"]  = round(overall["planned_budget_fcfa"], 2)
    overall["actual_spent_fcfa"]    = round(overall["actual_spent_fcfa"], 2)

    # Activity type outcome breakdown (across all months, executed only)
    act_outcome: dict = {}
    act_count:   dict = {}
    for m_entry in by_month.values():
        for r in m_entry["matched"]:
            aid = r["activity_id"]
            act_outcome[aid] = act_outcome.get(aid, 0.0) + r["sales_outcome_eur"]
            act_count[aid]   = act_count.get(aid, 0) + 1

    activity_breakdown = sorted([
        {
            "activity_id":      aid,
            "activity":         activity_display_name(aid),
            "total_outcome_eur": round(v, 2),
            "count":            act_count.get(aid, 0),
        }
        for aid, v in act_outcome.items()
    ], key=lambda x: x["total_outcome_eur"], reverse=True)

    result = safe_json({
        "months":               list(data.keys()),
        "by_month":             by_month,
        "overall":              overall,
        "activity_breakdown":   activity_breakdown,
    })
    await set_api_cache("activities", result)
    return result
