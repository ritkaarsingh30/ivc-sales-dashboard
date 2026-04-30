"""
Shared utility helpers for IVC Pharma Executive Dashboard (no Streamlit dependency).
"""

from constants import FCFA_TO_EUR


def to_eur(fcfa: float, fcfa_to_eur: float = FCFA_TO_EUR) -> float:
    return round(fcfa / fcfa_to_eur, 2)


def fmt_currency(val: float, unit: str) -> str:
    if unit == "EUR":
        return f"€ {val:,.2f}"
    return f"FCFA {val:,.0f}"


def safe_num(val):
    try:
        return float(val)
    except Exception:
        return 0.0
