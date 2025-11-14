from app.odds_api import (
    get_live_spread,
    get_pregame_spreads,
)
from app.constants import confidence_to_label


def _pick_team_to_bet(pregame_spread: float, current_margin: float) -> str:
    """
    Given the pregame spread and estimated current margin,
    return which side is currently covering: 'favorite' or 'underdog'.
    """
    diff = current_margin if pregame_spread < 0 else -current_margin
    is_covering = diff > abs(pregame_spread)
    return "underdog" if is_covering else "favorite"


def analyze_spread_movement(matchup: str):
    alerts = []

    # matchup is already ABBR, no conversions needed
    abbr_key = matchup
    away_abbr, _, home_abbr = abbr_key.partition(" @ ")

    pre_spreads = get_pregame_spreads()
    pre_spread = pre_spreads.get(abbr_key)
    live_spread = get_live_spread(abbr_key)

    if pre_spread is None or live_spread is None:
        return alerts

    delta = live_spread - pre_spread
    flip = pre_spread < 0 and live_spread > 0

    # Ignore small movements (unless the favorite flipped)
    if abs(delta) < 3 and not flip:
        return alerts

    label = confidence_to_label(abs(delta), "SPREAD")

    # Identify pregame fav/underdog
    favorite_team = home_abbr if pre_spread < 0 else away_abbr
    underdog_team = away_abbr if pre_spread < 0 else home_abbr

    # Rough margin estimate
    current_margin = -live_spread
    side = _pick_team_to_bet(pre_spread, current_margin)

    # Determine correct recommendation + line formatting
    if side == "favorite":
        live_side_team = favorite_team
        live_side_line = live_spread if pre_spread < 0 else -live_spread
    else:
        live_side_team = underdog_team
        live_side_line = -live_spread if pre_spread < 0 else live_spread

    emoji = "🚨 UPSET WATCH:" if flip else "↔️"

    alerts.append(
        f"{emoji} Spread changed by {abs(delta)} pts "
        f"(Pre: {pre_spread:+.1f}, Live: {live_spread:+.1f})\n"
        f"Scoey's Take: {label} {live_side_team} {live_side_line:+.1f}"
    )

    return alerts
