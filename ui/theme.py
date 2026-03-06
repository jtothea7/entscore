"""
Color constants and design tokens for EntScore UI
"""

# Primary palette
PRIMARY = "#2563EB"
PRIMARY_LIGHT = "#3B82F6"
PRIMARY_DARK = "#1D4ED8"

# Background
BG_PRIMARY = "#F8FAFC"
BG_SECONDARY = "#F1F5F9"
BG_CARD = "#FFFFFF"

# Text
TEXT_PRIMARY = "#0F172A"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#94A3B8"

# Status colors
SUCCESS = "#10B981"
SUCCESS_BG = "#ECFDF5"
WARNING = "#F59E0B"
WARNING_BG = "#FFFBEB"
DANGER = "#EF4444"
DANGER_BG = "#FEF2F2"
INFO = "#3B82F6"
INFO_BG = "#EFF6FF"

# Priority colors
PRIORITY_HIGH = DANGER
PRIORITY_MEDIUM = WARNING
PRIORITY_LOW = SUCCESS

# Score gauge colors
SCORE_EXCELLENT = "#10B981"  # 80-100
SCORE_GOOD = "#3B82F6"       # 60-79
SCORE_FAIR = "#F59E0B"       # 40-59
SCORE_POOR = "#EF4444"       # 0-39

# Border
BORDER_LIGHT = "#E2E8F0"
BORDER_DEFAULT = "#CBD5E1"

# Spacing
SPACING_SM = "8px"
SPACING_MD = "16px"
SPACING_LG = "24px"
SPACING_XL = "32px"

# Border radius
RADIUS_SM = "4px"
RADIUS_MD = "8px"
RADIUS_LG = "12px"


def get_score_color(score: float) -> str:
    """Get color for a health score value (0-100)."""
    if score >= 80:
        return SCORE_EXCELLENT
    elif score >= 60:
        return SCORE_GOOD
    elif score >= 40:
        return SCORE_FAIR
    else:
        return SCORE_POOR


def get_priority_color(priority: str) -> str:
    """Get color for a priority level."""
    return {
        "HIGH": PRIORITY_HIGH,
        "MEDIUM": PRIORITY_MEDIUM,
        "LOW": PRIORITY_LOW,
    }.get(priority, TEXT_MUTED)
