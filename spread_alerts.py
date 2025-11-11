from datetime import datetime
from odds_api import (
    get_live_spread,
    get_pregame_spreads,
    is_game_processed,
    mark_game_processed,
)
from constants import TEAM_MAP, confidence_to_label

# Reverse mapping to convert full name -> abbr
REV_TEAM_MAP = {v: k for k, v in TEAM_MAP.items()}


def _canonical_keys(matchup: str):
    """
    Given 'LAL @ BOS', return:
        - full name key  ('Los Angeles Lakers @ Boston Celtics')
        - abbr key       ('LAL @ BOS')
    This ensures we can always match stored spreads.
    """
    away_abbr, _, home_abbr = matchup.partition(" @ ")
    full_away = TEAM_MAP.get(away_abbr, away_abbr)
    full_home = TEAM_MAP.get(home_abbr, home_abbr)
    
    full_key = f"{full_away} @ {full_home}"
    abbr_key = matchup  # already in ABBR form
    return full_key, abbr_key


def analyze_spread_movement(game_id, matchup):
    """
    Compare live spread vs pre-game spread.
    Trigger alert if the spread tightens, widens, or flips significantly.
    """
    alerts = []

    # Get the two possible keys
    full_key, abbr_key = _canonical_keys(matchup)

    pre_spreads = get_pregame_spreads()

    # Try both lookup keys
    pre_spread = (
        pre_spreads.get(abbr_key)
        or pre_spreads.get(full_key)
    )

    live_spread = get_live_spread(abbr_key)  # live always uses abbr

    if pre_spread is None or live_spread is None:
        return alerts  # no alert if no baseline

    delta = live_spread - pre_spread
    flip = pre_spread < 0 and live_spread > 0 

    if abs(delta) > 3 or flip == True:
        label = confidence_to_label(abs(delta),"SPREAD")
    else:
        return alerts

    team_status = "🤯 UPSET WATCH" if flip else "⚠️ Spread Shift"
    alerts.append(
        f"{team_status}: Spread changed by {delta:+.1f} pts (Pre: {pre_spread:+.1f}, Live: {live_spread:+.1f})\nScoey's Take: {label}"
    )
    mark_game_processed(abbr_key)

    return alerts
