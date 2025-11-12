from __future__ import annotations
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL_TMPL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"

# Date window helpers (17:00–05:00 UTC)
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _espn_dates_for_window(now_utc: Optional[datetime] = None) -> List[str]:
    """
    Return the ESPN date(s) to fetch so NBA nights are treated as one continuous window.
    - Games before 10:00 UTC (≈5 AM ET) still belong to the previous calendar day.
    - Games after 22:00 UTC (≈5 PM ET) belong to today + tomorrow.
    """
    now = now_utc or _utc_now()
    today = now.strftime("%Y%m%d")

    # Before 10:00 UTC → previous day's slate still active (late West Coast games)
    if now.hour < 10:
        yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")
        return [yesterday, today]

    # After 22:00 UTC → tonight's games begin and can run into tomorrow
    if now.hour >= 22:
        tomorrow = (now + timedelta(days=1)).strftime("%Y%m%d")
        return [today, tomorrow]

    # Otherwise, normal midday window
    return [today]

# Fetch scoreboard payload
def _fetch_scoreboard(date_str: str) -> Dict[str, Any]:
    r = requests.get(ESPN_SCOREBOARD_URL, params={"dates": date_str}, timeout=10)
    r.raise_for_status()
    return r.json()

def _iter_events_for_window() -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for ds in _espn_dates_for_window():
        try:
            data = _fetch_scoreboard(ds)
        except Exception as e:
            print(f"⚠️ ESPN fetch error for {ds}: {e}")
            continue

        for ev in data.get("events", []):
            ev_id = ev.get("id")
            if ev_id and ev_id not in seen:
                seen.add(ev_id)
                out.append(ev)

    return out

# Normalize event → matchup, scores, IDs
def _to_matchup_abbr(ev: Dict[str, Any]) -> Optional[str]:
    comps = ev.get("competitions") or []
    if not comps:
        return None
    
    home = away = None
    for c in comps[0].get("competitors") or []:
        abbr = (c.get("team") or {}).get("abbreviation")
        if c.get("homeAway") == "home":
            home = abbr
        elif c.get("homeAway") == "away":
            away = abbr

    return f"{away} @ {home}" if home and away else None


def _scores(ev: Dict[str, Any]):
    comps = ev.get("competitions") or []
    if not comps:
        return None, None

    home_score = away_score = None
    for c in comps[0].get("competitors") or []:
        score_str = c.get("score")
        score = int(score_str) if score_str and score_str.isdigit() else None
        if c.get("homeAway") == "home":
            home_score = score
        else:
            away_score = score

    return home_score, away_score


def _status_fields(ev: Dict[str, Any]):
    """Safely extract game status info from ESPN event JSON."""
    status = ev.get("status", {})
    stype = status.get("type", {}) or {}

    name = stype.get("name") or status.get("name")
    detail = stype.get("description") or status.get("detail") or ""
    short = stype.get("shortDetail") or status.get("shortDetail") or ""

    return {
        "status_name": name,
        "status_detail": detail,
        "status_short": short,
        "period": status.get("period"),
        "clock": status.get("displayClock"),
    }

# Public: normalized games
def get_today_games() -> List[Dict[str, Any]]:
    games = []
    for ev in _iter_events_for_window():
        matchup = _to_matchup_abbr(ev)
        if not matchup:
            continue

        home_abbr = matchup.split(" @ ")[1]
        away_abbr = matchup.split(" @ ")[0]

        comps = ev.get("competitions") or []
        nba_game_id = comps[0].get("id") if comps else None

        home_score, away_score = _scores(ev)
        st = _status_fields(ev)

        games.append({
            "game_id": ev.get("id"),        # ESPN ID
            "nba_game_id": nba_game_id,      # NBA API boxscore ID
            "matchup": matchup,
            "status_name": st["status_name"],
            "status_detail": st["status_detail"],
            "period": st["period"],
            "clock": st["clock"],
            "home_abbr": home_abbr,
            "away_abbr": away_abbr,
            "home_score": home_score,
            "away_score": away_score,
        })
    return games

def get_yesterday_games() -> list[dict]:
    """
    Fetch all games from yesterday's calendar date (UTC-based) for post-game summaries.
    Includes abbreviations and scores for final result reporting.
    """
    from datetime import datetime, timedelta

    target_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y%m%d")
    print(f"📅 Fetching ESPN scoreboard for {target_date} (yesterday UTC)")

    try:
        data = _fetch_scoreboard(target_date)
    except Exception as e:
        print(f"⚠️ ESPN fetch error for {target_date}: {e}")
        return []

    games = []
    for ev in data.get("events", []):
        comps = ev.get("competitions") or []
        if not comps:
            continue

        # extract team abbreviations + scores
        home_abbr = away_abbr = None
        home_score = away_score = None

        competitors = comps[0].get("competitors", [])
        for c in competitors:
            abbr = (c.get("team") or {}).get("abbreviation")
            score_str = c.get("score")
            score = int(score_str) if score_str and score_str.isdigit() else None

            if c.get("homeAway") == "home":
                home_abbr, home_score = abbr, score
            elif c.get("homeAway") == "away":
                away_abbr, away_score = abbr, score

        # extract status fields
        st = _status_fields(ev)
        status_name = st.get("status_name") or ""
        status_detail = st.get("status_detail") or ""

        games.append({
            "game_id": ev.get("id"),
            "matchup": f"{away_abbr} @ {home_abbr}" if home_abbr and away_abbr else None,
            "home_abbr": home_abbr,
            "away_abbr": away_abbr,
            "home_score": home_score,
            "away_score": away_score,
            "status_name": status_name,
            "status_detail": status_detail,
        })

    return games

def iter_halftimes():
    # games = get_today_games()
    # return games
    return [
        g for g in get_today_games()
        if g["status_detail"] and "Halftime" in g["status_detail"]
    ]

# ESPN Player Boxscore
def fetch_boxscore_players(event_id: str):
    url = SUMMARY_URL_TMPL.format(event_id=event_id)

    try:
        data = requests.get(url, timeout=10).json()
    except Exception as e:
        print(f"⚠️ ERROR loading ESPN summary {event_id}: {e}")
        return []

    out = []
    box = data.get("boxscore", {})
    player_blocks = box.get("players", [])

    for team_block in player_blocks:

        team_abbr = (team_block.get("team") or {}).get("abbreviation")
        statistics = team_block.get("statistics") or []
        if not statistics:
            continue

        stat_block = statistics[0]

        labels = stat_block.get("labels", [])
        athletes = stat_block.get("athletes", [])

        # Build label -> index map
        label_index = {label: i for i, label in enumerate(labels)}

        idx_MIN = label_index.get("MIN")
        idx_PTS = label_index.get("PTS")
        idx_FG  = label_index.get("FG")

        for player in athletes:
            ath = player.get("athlete") or {}
            stats = player.get("stats") or []

            pid = str(ath.get("id"))
            name = ath.get("displayName")

            # Extract values safely
            minutes = stats[idx_MIN] if idx_MIN is not None and idx_MIN < len(stats) else "0:00"
            
            pts = 0
            if idx_PTS is not None and idx_PTS < len(stats):
                try:
                    pts = int(stats[idx_PTS])
                except:
                    pts = 0

            # Parse FGA from "M-A"
            fga = 0
            if idx_FG is not None and idx_FG < len(stats):
                fg_str = stats[idx_FG]
                if isinstance(fg_str, str) and "-" in fg_str:
                    try:
                        fga = int(fg_str.split("-")[1])
                    except:
                        fga = 0

            out.append({
                "id": pid,
                "name": name,
                "team": team_abbr,
                "points": pts,
                "minutes": minutes,
                "fga": fga,
            })

    return out
