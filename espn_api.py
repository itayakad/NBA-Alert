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
    now = now_utc or _utc_now()
    today = now.strftime("%Y%m%d")

    if now.hour < 5:
        yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")
        return [yesterday, today]

    if now.hour >= 17:
        tomorrow = (now + timedelta(days=1)).strftime("%Y%m%d")
        return [today, tomorrow]

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
    s = (ev.get("status") or {}).get("type") or {}
    return {
        "status_name": s.get("name"),
        "status_detail": s.get("description"),
        "status_short": s.get("shortDetail"),
        "period": (ev.get("status") or {}).get("period"),
        "clock": (ev.get("status") or {}).get("displayClock"),
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
