from app.odds_api import (
    get_live_spread,
    get_pregame_spreads,
    mark_game_processed,
)
from app.constants import TEAM_MAP, confidence_to_label

# Reverse mapping to convert full name -> abbr
REV_TEAM_MAP = {v: k for k, v in TEAM_MAP.items()}


def _canonical_keys(matchup: str):
    """
    Given 'LAL @ BOS', return:
        - full name key  ('Los Angeles Lakers @ Boston Celtics')
        - abbr key       ('LAL @ BOS')
        - individual abbreviations (away, home)
    """
    away_abbr, _, home_abbr = matchup.partition(" @ ")
    full_away = TEAM_MAP.get(away_abbr, away_abbr)
    full_home = TEAM_MAP.get(home_abbr, home_abbr)
    return f"{full_away} @ {full_home}", matchup, away_abbr, home_abbr


def _pick_team_to_bet(pregame_spread: float, current_margin: float) -> str:
    diff = current_margin if pregame_spread < 0 else -current_margin
    is_covering = diff > abs(pregame_spread)
    return "underdog" if is_covering else "favorite"


def analyze_spread_movement(matchup):
    alerts = []
    full_key, abbr_key, away_abbr, home_abbr = _canonical_keys(matchup)

    pre_spreads = get_pregame_spreads()
    pre_spread = pre_spreads.get(abbr_key) or pre_spreads.get(full_key)
    live_spread = get_live_spread(abbr_key)

    if pre_spread is None or live_spread is None:
        return alerts

    delta = live_spread - pre_spread
    flip = pre_spread < 0 and live_spread > 0

    if abs(delta) < 3 and not flip:
        return alerts

    label = confidence_to_label(abs(delta), "SPREAD")

    # Identify pregame favorite and underdog
    favorite_team = home_abbr if pre_spread < 0 else away_abbr
    underdog_team = away_abbr if pre_spread < 0 else home_abbr

    # Estimate if covering (based on margin approximation)
    current_margin = -live_spread  # approximate live margin
    side = _pick_team_to_bet(pre_spread, current_margin)

    # Pick correct team and their live line
    if side == "favorite":
        live_side_team = favorite_team
        live_side_line = live_spread if pre_spread < 0 else -live_spread
    else:
        live_side_team = underdog_team
        live_side_line = -live_spread if pre_spread < 0 else live_spread

    team_status = "🚨 UPSET WATCH:" if flip else "↔️"

    alerts.append(
        f"{team_status} Spread changed by {abs(delta)} pts "
        f"(Pre: {pre_spread:+.1f}, Live: {live_spread:+.1f})\n"
        f"Scoey's Take: {label} {live_side_team} {live_side_line:+.1f}"
    )

    mark_game_processed(abbr_key)
    return alerts
