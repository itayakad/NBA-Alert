import time
import requests
from datetime import datetime, timedelta, timezone
from keys import ODDS_API_KEY, ODDS_URL
from constants import TEAM_MAP
import json
import os

PREGAME_FILE = "pregame_lines.json"
CACHE_TTL = 300  # seconds

_cache = {}  # key: market_type -> {"timestamp": float, "data": list}
_pregame_spreads = {}
_pregame_totals = {}
_processed_games = set()

REV_TEAM_MAP = {v: k for k, v in TEAM_MAP.items()}

def _load_pregame_cache():
    """Load pregame spreads/totals from disk and auto-reset if date changed."""
    global _pregame_spreads, _pregame_totals
    _pregame_spreads, _pregame_totals = {}, {}

    today = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(PREGAME_FILE):
        return  # Nothing cached yet

    try:
        with open(PREGAME_FILE, "r") as f:
            data = json.load(f) or {}

        file_date = data.get("date")
        if file_date != today:
            print(f"🧹 Cache is from {file_date}, resetting for {today}...")
            _save_pregame_cache()  # wipe immediately with new date
            return

        _pregame_spreads = data.get("spreads", {}) or {}
        _pregame_totals  = data.get("totals", {}) or {}
        print("✅ Loaded pregame lines from disk.")
    except Exception as e:
        print(f"⚠️ Failed to load cache: {e}")
        _pregame_spreads, _pregame_totals = {}, {}


def _save_pregame_cache():
    """Save spreads/totals to disk with today's date tag."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with open(PREGAME_FILE, "w") as f:
            json.dump(
                {
                    "date": today,
                    "spreads": _pregame_spreads,
                    "totals": _pregame_totals,
                },
                f,
                indent=2
            )
        print("💾 Saved pregame lines to disk.")
    except Exception as e:
        print(f"⚠️ Failed to save pregame lines: {e}")

def _abbr_key(away_name: str, home_name: str) -> str:
    """Return canonical key 'AWY @ HOME' using abbreviations."""
    away_abbr = REV_TEAM_MAP.get(away_name, away_name)
    home_abbr = REV_TEAM_MAP.get(home_name, home_name)
    return f"{away_abbr} @ {home_abbr}"

def _fetch_odds_data(market_type="spreads"):
    """Fetch NBA odds data from The Odds API, cached per market_type."""
    now_ts = time.time()
    entry = _cache.get(market_type)
    if entry and (now_ts - entry["timestamp"] < CACHE_TTL) and entry["data"]:
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
        print(f"⚠️ Error fetching odds for market '{market_type}': {e}")
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

def record_pre_game_totals():
    global _pregame_totals
    today = datetime.utcnow().strftime("%Y-%m-%d")

    data = _fetch_odds_data(market_type="totals")
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

        full_key = f"{away} @ {home}"
        abbr_key = _abbr_key(away, home)

        if full_key in _pregame_totals or abbr_key in _pregame_totals:
            continue

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        market = next((m for m in bookmakers[0]["markets"] if m["key"] == "totals"), None)
        if not market:
            continue

        outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}
        total = outcomes.get("Over") or outcomes.get("Under")

        if total:
            _pregame_totals[full_key] = total
            _pregame_totals[abbr_key] = total
            count += 1

    print(f"✅ Recorded {count} pregame TOTALS for {start_window:%Y-%m-%d}.")
    _save_pregame_cache()
    return _pregame_totals

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

def get_live_total(matchup):
    data = _fetch_odds_data(market_type="totals")

    away_abbr, _, home_abbr = matchup.partition(" @ ")
    full_home = TEAM_MAP.get(home_abbr, home_abbr)
    full_away = TEAM_MAP.get(away_abbr, away_abbr)

    for game in data:
        ht = game.get("home_team")
        at = game.get("away_team")
        if full_home not in (ht, at) and full_away not in (ht, at):
            continue

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        market = next((m for m in bookmakers[0]["markets"] if m["key"] == "totals"), None)
        if not market:
            continue

        outcomes = {o["name"]: o.get("point") for o in market["outcomes"]}
        return outcomes.get("Over") or outcomes.get("Under")

    return None

def get_pregame_spreads():
    return _pregame_spreads

def get_pregame_totals():
    return _pregame_totals

def mark_game_processed(matchup):
    _processed_games.add(matchup)

def is_game_processed(matchup):
    return matchup in _processed_games
