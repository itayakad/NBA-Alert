import time
import requests
from datetime import datetime, timedelta
from apikeys import ODDS_API_KEY, ODDS_URL
from constants import TEAM_MAP

CACHE_TTL = 300  # seconds

_cache = {"timestamp": 0, "data": []}
_pregame_spreads = {}
_processed_games = set()


def _fetch_odds_data(market_type="spreads"):
    """Fetch NBA odds data from The Odds API, with simple caching."""
    global _cache

    if time.time() - _cache["timestamp"] < CACHE_TTL and _cache["data"]:
        return _cache["data"]

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
        _cache = {"timestamp": time.time(), "data": data}
        return data
    except Exception as e:
        print(f"⚠️ Error fetching odds: {e}")
        return []


def _find_team_spread(team_abbr, outcomes):
    """Find spread value for an abbreviation by fuzzy matching full names."""
    full_name = TEAM_MAP.get(team_abbr, team_abbr)
    for name, point in outcomes.items():
        if full_name.lower() in name.lower() or name.lower() in full_name.lower():
            return point
    return None


def record_pre_game_spreads():
    """Fetches all pregame spreads for *today's* games and stores them in _pregame_spreads."""
    global _pregame_spreads
    data = _fetch_odds_data(market_type="spreads")
    count = 0

    today_str = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    for game in data:
        commence_time = game.get("commence_time")
        if not commence_time:
            continue

        game_date = commence_time[:10]
        if game_date != today_str:
            continue  # Only today's games

        home = game.get("home_team")
        away = game.get("away_team")
        matchup = f"{away} @ {home}"

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        market = next((m for m in bookmakers[0]["markets"] if m["key"] == "spreads"), None)
        if not market:
            continue

        outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}
        home_abbr = next((abbr for abbr, name in TEAM_MAP.items() if name == home), home)
        home_spread = _find_team_spread(home_abbr, outcomes)

        if home_spread is not None:
            _pregame_spreads[matchup] = home_spread
            count += 1

    print(f"✅ Recorded {count} pregame spreads for today's games ({datetime.utcnow().strftime('%Y-%m-%d')}).")
    return _pregame_spreads


def get_live_spread(matchup):
    """Returns the current home spread for the given matchup (e.g. 'LAL @ BOS')."""
    data = _fetch_odds_data(market_type="spreads")

    # Parse matchup abbreviations and expand to full names
    away_abbr, _, home_abbr = matchup.partition(" @ ")
    full_home = TEAM_MAP.get(home_abbr, home_abbr)
    full_away = TEAM_MAP.get(away_abbr, away_abbr)

    for game in data:
        if full_home in (game["home_team"], game["away_team"]) or full_away in (game["home_team"], game["away_team"]):
            bookmakers = game.get("bookmakers", [])
            if not bookmakers:
                continue

            market = next((m for m in bookmakers[0]["markets"] if m["key"] == "spreads"), None)
            if not market:
                continue

            outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}
            return _find_team_spread(home_abbr, outcomes)

    return None


def get_pregame_spreads():
    return _pregame_spreads


def mark_game_processed(matchup):
    _processed_games.add(matchup)


def is_game_processed(matchup):
    return matchup in _processed_games
