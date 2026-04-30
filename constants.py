"""
Shared constants for IVC Pharma Executive Dashboard.
"""

FCFA_TO_EUR = 655.97
TEMPLATE = "plotly_dark"

DISTRIBUTORS = [
    "UBIPHARM/LABOREX",
    "COPHARMED/LABOREX",
    "TEDIS",
    "DPCI",
]

# IDs that are NOT field MRs — excluded from MR Performance tab
_NON_MR_IDS = {"MR_006", "AGT_001", "UNKNOWN"}

# ── Color palette ──
CLR_GREEN  = "#00C49A"
CLR_RED    = "#FF4C61"
CLR_BLUE   = "#4C9FFF"
CLR_ORANGE = "#FF9F40"
CLR_PURPLE = "#B57BFF"
CLR_TEAL   = "#26C6DA"
CLR_YELLOW = "#FFD166"

DIST_COLORS = {
    "UBIPHARM/LABOREX":  CLR_BLUE,
    "COPHARMED/LABOREX": CLR_GREEN,
    "TEDIS":             CLR_ORANGE,
    "DPCI":              CLR_PURPLE,
}
