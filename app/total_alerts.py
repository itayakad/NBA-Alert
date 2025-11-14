from app.odds_api import get_live_total, get_pregame_totals
from app.constants import confidence_to_label


def analyze_total_movement(matchup: str):
    alerts = []

    abbr_key = matchup  # canonical
    pre_totals = get_pregame_totals()
    pre_total = pre_totals.get(abbr_key)
    live_total = get_live_total(abbr_key)

    if pre_total is None or live_total is None:
        return alerts

    delta = live_total - pre_total
    pct_change = abs(delta) / pre_total

    # Only trigger for ≥5% movement
    if pct_change < 0.05:
        return alerts

    label = confidence_to_label(pct_change, "TOTAL")

    # Movement direction
    tag = "📈" if delta > 0 else "📉"
    direction = "up" if delta > 0 else "down"

    # If total moves UP → game expected to be lower scoring (bet UNDER)
    # If total moves DOWN → expect OVER
    recommended_side = "Under" if delta > 0 else "Over"

    msg = (
        f"{tag}: Total moved {direction} {abs(delta):.1f} pts "
        f"(Pre: {pre_total:.1f}, Live: {live_total:.1f})\n"
        f"Scoey's Take: {label} {recommended_side} {live_total:.1f}"
    )
    alerts.append(msg)
    return alerts