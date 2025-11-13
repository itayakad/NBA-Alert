from datetime import datetime
from odds_api import get_live_total, get_pregame_totals
from constants import confidence_to_label


def analyze_total_movement(matchup):
    alerts = []

    pre_totals = get_pregame_totals()
    pre_total = pre_totals.get(matchup)
    live_total = get_live_total(matchup)

    if pre_total is None or live_total is None:
        return alerts

    delta = live_total - pre_total
    pct_change = abs(delta) / pre_total

    # Only trigger for ≥5% movement
    if pct_change < 0.05:
        return alerts

    label = confidence_to_label(pct_change, "TOTAL")

    # Direction emoji and movement text
    tag = "📈" if delta > 0 else "📉"
    direction = "up" if delta > 0 else "down"
    recommended_side = "Over" if delta < 0 else "Under"

    msg = (
        f"{tag}: Total moved {direction} {abs(delta):.1f} pts "
        f"(Pre: {pre_total:.1f}, Live: {live_total:.1f})\n"
        f"Scoey's Take: {label} {recommended_side} {live_total:.1f}"
    )
    alerts.append(msg)
    return alerts