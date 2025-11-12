from datetime import datetime
from odds_api import get_live_total, get_pregame_totals
from constants import confidence_to_label


def analyze_total_movement(game_id, matchup):
    alerts = []

    pre_totals = get_pregame_totals()
    pre_total = pre_totals.get(matchup)
    live_total = get_live_total(matchup)

    if pre_total is None or live_total is None:
        return alerts

    delta = live_total - pre_total
    pct_change = abs(delta) / pre_total
    if pct_change >= 0.05:
        label = confidence_to_label(pct_change,"TOTAL")
    else:
        return alerts

    # Direction emoji
    tag = "📈" if delta > 0 else "📉"
    direction = "up" if delta > 0 else "down"

    # Build alert line (mirrors your player alert format)
    msg = (
        f"{tag}: Total moved {direction} {abs(delta)} pts (Pre: {pre_total:.1f}, Live: {live_total:.1f})\nScoey's Take: {label}"
    )
    alerts.append(msg)
    return alerts
