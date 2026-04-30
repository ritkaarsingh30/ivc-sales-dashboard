"""
Shared utility helpers for IVC Pharma Executive Dashboard.
"""

import streamlit as st
from constants import CLR_BLUE, CLR_GREEN, CLR_RED


def to_eur(fcfa: float, fcfa_to_eur: float) -> float:
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


def placeholder_tab(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div style="display:flex;flex-direction:column;align-items:center;
                    justify-content:center;height:400px;">
            <div style="background:linear-gradient(135deg,#1e2a3a,#2a3a50);
                        border:1px solid #3a5070;border-radius:16px;
                        padding:48px 64px;text-align:center;max-width:500px;">
                <div style="font-size:48px;margin-bottom:16px;">🚧</div>
                <h2 style="color:#4C9FFF;margin:0 0 8px 0;">{title}</h2>
                <p style="color:#8899aa;margin:0;">{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(cards: list):
    """
    cards = [{"label": str, "value": str, "delta": str|None, "color": str}, ...]
    """
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        color = card.get("color", CLR_BLUE)
        delta_html = ""
        if card.get("delta"):
            delta_color = CLR_GREEN if "+" in str(card["delta"]) else CLR_RED
            delta_html = f'<div style="color:{delta_color};font-size:13px;margin-top:4px;">{card["delta"]}</div>'
        col.markdown(
            f"""
            <div style="background:linear-gradient(135deg,#1a2535,#1e2e42);
                        border-left:4px solid {color};border-radius:10px;
                        padding:18px 20px;margin-bottom:8px;">
                <div style="color:#8899aa;font-size:12px;text-transform:uppercase;
                            letter-spacing:1px;margin-bottom:6px;">{card['label']}</div>
                <div style="color:#ffffff;font-size:22px;font-weight:700;">{card['value']}</div>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
