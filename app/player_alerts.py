from typing import Dict, List
import requests
from app.constants import (
    TOP_SCORER_LIMIT,
    MIN_MINUTES_FOR_VALID_SAMPLE,
    CONFIDENCE_WEIGHTS,
    EXPECTED_HALF_MINUTES,
    EXPECTED_LEAGUE_LEADER_PPG,
    EXPECTED_HALF_FGA,
    SEASON,
    confidence_to_label,
)
from app.espn_api import fetch_boxscore_players

def normalize_name(name: str) -> str:
    return (
        name.lower()
            .replace(".", "")
            .replace("'", "")
            .replace("-", "")
            .replace(" ", "")
            .strip()
    )

NAME_TO_NBA_ID = {}
NBA_ID_TO_STATS = {}

def get_top_scorers(limit=TOP_SCORER_LIMIT):
    print("📊 Fetching top scorers from ESPN...")

    url = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics"
    r = requests.get(url, timeout=10)
    data = r.json()

    try:
        leaders = data["categories"][0]["stats"][0]["athletes"]
    except Exception:
        print("⚠️ ESPN top-scorer API changed or unavailable.")
        return {}

    top = leaders[:limit]

    # Reset globals
    NAME_TO_NBA_ID.clear()
    NBA_ID_TO_STATS.clear()

    for p in top:
        athlete = p["athlete"]

        pid = str(athlete["id"])
        name = athlete["displayName"]
        ppg = float(p["value"])

        NAME_TO_NBA_ID[normalize_name(name)] = pid
        NBA_ID_TO_STATS[pid] = {
            "name": name,
            "ppg": ppg,
            "ppg_weight": ppg / EXPECTED_LEAGUE_LEADER_PPG
        }

    print(f"✅ Loaded top {limit} scorers (via ESPN).")
    return {
    pid: NBA_ID_TO_STATS[pid]
    for pid in list(NBA_ID_TO_STATS.keys())[:limit]
}

def compute_confidence(pts, avg_ppg, min_float, fga, home_score, away_score, ppg_weight):
    expected_half_pts = avg_ppg / 2 if avg_ppg else (EXPECTED_LEAGUE_LEADER_PPG / 2)
    U = min(1, pts / expected_half_pts) if expected_half_pts > 0 else 1
    M = min(1, min_float / EXPECTED_HALF_MINUTES)
    Y = min(1, fga / EXPECTED_HALF_FGA) if fga is not None else 0

    diff = abs(home_score - away_score)
    C = max(0, 1 - diff / 25)

    P = min(1, ppg_weight or 1)

    w = CONFIDENCE_WEIGHTS
    confidence = (
        (1 - U) * w["U"] +
        M * w["M"] +
        Y * w["Y"] +
        C * w["C"] +
        P * w["P"]
    )

    return round(max(0, min(confidence, 1)), 2)

def analyze_game_players(event_id: str, matchup: str, top_scorers: Dict[str, Dict], home_score: int, away_score: int) -> List[str]:
    alerts: List[str] = []

    players = fetch_boxscore_players(event_id)
    if not players:
        return [f"⚠️ ESPN summary missing for {matchup}"]

    print(f"📊 DEBUG: {matchup} — Loaded {len(players)} players from ESPN.")

    for p in players:
        name = p["name"]
        pts = p["points"]
        fga = p["fga"]
        minutes = p["minutes"]

        # Skip empty stints
        if pts == 0 and minutes == "0:00":
            continue

        # Convert minutes
        try:
            mm, ss = minutes.split(":")
            min_float = int(mm) + int(ss) / 60
        except:
            min_float = 0

        # Discard small-sample garbage time
        if min_float < MIN_MINUTES_FOR_VALID_SAMPLE and pts < 5:
            continue

        # Map ESPN -> NBA ID via normalized name
        norm = normalize_name(name)
        nba_id = NAME_TO_NBA_ID.get(norm)

        if not nba_id:
            # ESPN name not found in NBA season stats — skip
            continue

        # Only evaluate if this is one of the "top scorers"
        if nba_id not in top_scorers:
            continue

        avg_ppg = top_scorers[nba_id]["ppg"]
        ppg_weight = top_scorers[nba_id]["ppg_weight"]

        # Underperforming at halftime
        conf = compute_confidence(pts, avg_ppg, min_float, fga, home_score, away_score, ppg_weight)
        pace = pts / avg_ppg
        if pace < 0.50:
            conf_label = confidence_to_label(conf,"POINTS")
            alerts.append(f"🎯 {name}: {pts} pts in {minutes} min (season avg {avg_ppg:.1f})\nScoey's Take: {conf_label}")
    return alerts
