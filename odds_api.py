import time
import requests
from datetime import datetime, timedelta, timezone
from apikeys import ODDS_API_KEY, ODDS_URL
from constants import TEAM_MAP
import json
import os

PREGAME_FILE = "pregame_spreads.json"
CACHE_TTL = 300  # seconds

_cache = {"timestamp": 0, "data": []}
_pregame_spreads = {}
_processed_games = set()

REV_TEAM_MAP = {v: k for k, v in TEAM_MAP.items()}

def _load_pregame_cache():
    global _pregame_spreads
    if os.path.exists(PREGAME_FILE):
        try:
            with open(PREGAME_FILE, "r") as f:
                _pregame_spreads = json.load(f)
                print("✅ Loaded pregame spreads from disk.")
        except:
            _pregame_spreads = {}

def _save_pregame_cache():
    try:
        with open(PREGAME_FILE, "w") as f:
            json.dump(_pregame_spreads, f, indent=2)
        print("💾 Saved pregame spreads to disk.")
    except Exception as e:
        print(f"⚠️ Failed to save pregame spreads: {e}")

def _abbr_key(away_name: str, home_name: str) -> str:
    """Return canonical key 'AWY @ HOME' using abbreviations."""
    away_abbr = REV_TEAM_MAP.get(away_name, away_name)
    home_abbr = REV_TEAM_MAP.get(home_name, home_name)
    return f"{away_abbr} @ {home_abbr}"

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

# Spread
def _find_team_spread(team_abbr, outcomes):
    """Find spread value by matching full team names."""
    full_name = TEAM_MAP.get(team_abbr, team_abbr)

    for name, point in outcomes.items():
        if full_name.lower() in name.lower() or name.lower() in full_name.lower():
            return point
    return None

def record_pre_game_spreads():
    """
    Fetch all pregame spreads for today's NBA slate.
    Store spreads under BOTH:
        - Full key: 'Los Angeles Lakers @ Boston Celtics'
        - ABBR key: 'LAL @ BOS'
    So downstream lookups ALWAYS succeed.
    """
    global _pregame_spreads
    _load_pregame_cache()

    data = _fetch_odds_data(market_type="spreads")
    count = 0

    now = datetime.now(timezone.utc)
    start_window = now.replace(hour=17, minute=0, second=0, microsecond=0)
    if now.hour < 5:
        start_window -= timedelta(days=1)
    end_window = start_window + timedelta(hours=12)

    for game in data:
        commence_time = game.get("commence_time")
        if not commence_time:
            continue

        game_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        if not (start_window <= game_dt <= end_window):
            continue

        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue

        full_key = f"{away} @ {home}"
        abbr_key = _abbr_key(away, home)

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        market = next((m for m in bookmakers[0]["markets"] if m["key"] == "spreads"), None)
        if not market:
            continue

        outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}

        home_abbr = REV_TEAM_MAP.get(home, home)
        home_spread = _find_team_spread(home_abbr, outcomes)

        if home_spread is not None:

            # ✅ If already stored (from before tipoff), DO NOT overwrite.
            if abbr_key in _pregame_spreads or full_key in _pregame_spreads:
                # Stored value = real pregame spread → keep it
                print(f"✅ Already stored pregame spread for {abbr_key}, skipping overwrite.")
                continue

            print(f"📊 PRE-GAME LOCKED: {full_key} ({home_spread:+.1f})")

            _pregame_spreads[abbr_key] = home_spread
            _pregame_spreads[full_key] = home_spread

            count += 1

    print(f"✅ Recorded {count} pregame spreads for {start_window:%Y-%m-%d}.")
    _save_pregame_cache()
    return _pregame_spreads

# Live
def get_live_spread(matchup):
    """
    matchup is always 'AWY @ HOME' (abbreviations).
    Convert to full names before searching.
    """
    data = _fetch_odds_data(market_type="spreads")

    away_abbr, _, home_abbr = matchup.partition(" @ ")
    full_home = TEAM_MAP.get(home_abbr, home_abbr)
    full_away = TEAM_MAP.get(away_abbr, away_abbr)

    for game in data:
        ht = game.get("home_team")
        at = game.get("away_team")

        if not ht or not at:
            continue

        # Match using FULL team names
        if full_home in (ht, at) or full_away in (ht, at):
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
