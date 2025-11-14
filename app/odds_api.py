import time
import requests
from datetime import datetime, timedelta, timezone
from app.keys import ODDS_API_KEY, ODDS_URL
from app.constants import TEAM_MAP
import json
import os

PREGAME_FILE = "state/pregame_lines.json"
CACHE_TTL = 300  # seconds

_cache = {}  # key: market_type -> {"timestamp": float, "data": list}
_pregame_spreads = {}
_pregame_totals = {}
_processed_games = set()

REV_TEAM_MAP = {v: k for k, v in TEAM_MAP.items()}

def normalize_team_abbr(abbr: str) -> str:
    """
    Normalize ESPN-provided abbreviations to the ones used in TEAM_MAP.
    """
    abbr = abbr.upper()

    fixes = {
        "UTAH": "UTA",
        "PHO": "PHX",
        "GS": "GSW",
        "SA": "SAS",
        "NO": "NOP",
        "NY": "NYK",
        "INDY": "IND",
        "WSH": "WAS",
        "CHAR": "CHA",
        "OKC": "OKC",  # passthrough examples
    }

    return fixes.get(abbr, abbr)

def _load_pregame_cache():
    global _pregame_spreads, _pregame_totals
    _pregame_spreads, _pregame_totals = {}, {}

    if not os.path.exists(PREGAME_FILE):
        print("⚠️ No pregame_lines.json found yet.")
        return

    try:
        with open(PREGAME_FILE, "r") as f:
            data = json.load(f)

        _pregame_spreads = data.get("spreads", {})
        _pregame_totals = data.get("totals", {})

        print("✅ Pregame spreads/totals loaded into memory.")
    except Exception as e:
        print(f"⚠️ Failed to load pregame file: {e}")


_load_pregame_cache()

def _fetch_odds_data(market_type="spreads"):
    now_ts = time.time()
    entry = _cache.get(market_type)
    if entry and (now_ts - entry["timestamp"] < CACHE_TTL):
        return entry["data"]

    try:
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": market_type,
            "oddsFormat": "decimal",
        }
        response = requests.get(ODDS_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        _cache[market_type] = {"timestamp": now_ts, "data": data}
        return data
    except Exception as e:
        print(f"⚠️ Error fetching odds for {market_type}: {e}")
        return []

def _abbr_key(away_name: str, home_name: str) -> str:
    away_abbr = REV_TEAM_MAP.get(away_name, away_name)
    home_abbr = REV_TEAM_MAP.get(home_name, home_name)
    return f"{away_abbr} @ {home_abbr}"

def _find_team_spread(team_abbr, outcomes):
    """
    The Odds API uses full team names in outcomes like:
        [{'name': 'Los Angeles Lakers', 'point': -4.5}, ...]
    So we match by FULL name derived from TEAM_MAP.
    """
    full_name = TEAM_MAP.get(team_abbr)
    if not full_name:
        return None

    for name, point in outcomes.items():
        if name.lower() == full_name.lower():
            return point
    return None

def record_all_pregame_lines():
    spreads = {}
    totals = {}

    now = datetime.now(timezone.utc)
    start_window = now.replace(hour=17, minute=0, second=0, microsecond=0)
    if now.hour < 5:
        start_window -= timedelta(days=1)
    end_window = start_window + timedelta(hours=12)

    spread_data = _fetch_odds_data("spreads")
    total_data = _fetch_odds_data("totals")

    for game in spread_data:
        commence_time = game.get("commence_time")
        if not commence_time:
            continue

        game_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        if not (start_window <= game_dt <= end_window):
            continue

        home = game["home_team"]
        away = game["away_team"]
        abbr_key = _abbr_key(away, home)

        market = next((m for m in game["bookmakers"][0]["markets"] 
                       if m["key"] == "spreads"), None)
        if not market:
            continue

        outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}

        home_abbr = REV_TEAM_MAP.get(home)
        spread_val = _find_team_spread(home_abbr, outcomes)

        if spread_val is not None:
            spreads[abbr_key] = spread_val

    # Process totals
    for game in total_data:
        commence_time = game.get("commence_time")
        if not commence_time:
            continue

        game_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        if not (start_window <= game_dt <= end_window):
            continue

        home = game["home_team"]
        away = game["away_team"]
        abbr_key = _abbr_key(away, home)

        market = next((m for m in game["bookmakers"][0]["markets"]
                       if m["key"] == "totals"), None)
        if not market:
            continue

        outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}
        total_val = outcomes.get("Over")

        if total_val:
            totals[abbr_key] = total_val

    result = {
        "date": start_window.strftime("%Y-%m-%d"),
        "spreads": spreads,
        "totals": totals
    }

    with open(PREGAME_FILE, "w") as f:
        json.dump(result, f, indent=2)

    print(f"💾 Saved {len(spreads)} spreads + {len(totals)} totals.")

    # Refresh in-memory cache
    _load_pregame_cache()

    return result

def get_live_spread(matchup):
    away_abbr, _, home_abbr = matchup.partition(" @ ")
    away_abbr = normalize_team_abbr(away_abbr)
    home_abbr = normalize_team_abbr(home_abbr)

    home_full = TEAM_MAP[home_abbr]
    away_full = TEAM_MAP[away_abbr]

    data = _fetch_odds_data("spreads")

    for game in data:
        if game["home_team"] == home_full and game["away_team"] == away_full:
            market = next((m for m in game["bookmakers"][0]["markets"] 
                           if m["key"] == "spreads"), None)
            if not market:
                return None

            outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}
            return _find_team_spread(home_abbr, outcomes)

    return None

def get_live_total(matchup):
    away_abbr, _, home_abbr = matchup.partition(" @ ")
    away_abbr = normalize_team_abbr(away_abbr)
    home_abbr = normalize_team_abbr(home_abbr)

    home_full = TEAM_MAP[home_abbr]
    away_full = TEAM_MAP[away_abbr]

    data = _fetch_odds_data("totals")

    for game in data:
        if game["home_team"] == home_full and game["away_team"] == away_full:
            market = next((m for m in game["bookmakers"][0]["markets"]
                           if m["key"] == "totals"), None)
            if not market:
                return None

            outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}
            return outcomes.get("Over")

    return None

def get_pregame_spreads():
    return _pregame_spreads

def get_pregame_totals():
    return _pregame_totals

def mark_game_processed(matchup):
    _processed_games.add(matchup)

def is_game_processed(matchup):
    return matchup in _processed_games