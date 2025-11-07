from datetime import datetime
from odds_api import (
    get_live_spread,
    get_pregame_spreads,
    is_game_processed,
    mark_game_processed,
)


def analyze_spread_movement(game_id, matchup):
    """
    Compare live spread vs pre-game spread.
    Trigger alert if the spread tightens, widens, or flips significantly.
    Returns a list of alert messages (to be handled by main.py).
    """
    alerts = []
    if is_game_processed(matchup):
        return alerts

    pre_spreads = get_pregame_spreads()
    pre_spread = pre_spreads.get(matchup)
    live_spread = get_live_spread(matchup)

    if pre_spread is None or live_spread is None:
        return alerts

    delta = live_spread - pre_spread
    now = datetime.now().strftime("%H:%M:%S")

    flip = pre_spread < 0 and live_spread > 0
    significant = abs(delta) >= 3 or flip
    if significant:
        trend = "tightened" if delta > 0 else "widened"
        prefix = "🔥 MAJOR" if flip else "⚠️"
        team_status = "Underdog Rally" if flip else "Spread Shift"
        alerts.append(
            f"{prefix} {now} — {matchup}: {team_status} | Spread {trend} by {delta:+.1f} pts "
            f"(Pre: {pre_spread:+.1f}, Live: {live_spread:+.1f})"
        )
        mark_game_processed(matchup)

    return alerts
