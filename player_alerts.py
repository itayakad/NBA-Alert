from typing import Dict, List
from typing import Dict, List
import requests
from constants import (
    TOP_SCORER_LIMIT,
    MIN_MINUTES_FOR_VALID_SAMPLE,
    CONFIDENCE_WEIGHTS,
    EXPECTED_HALF_MINUTES,
    EXPECTED_LEAGUE_LEADER_PPG,
    EXPECTED_HALF_FGA,
    SEASON,
    confidence_to_label,
)
from espn_api import fetch_boxscore_players

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

BALD_URL = "https://api.balldontlie.io/v1"
BALD_SEASON = 2025   # maps to 2025-26 season

def get_top_scorers(limit=TOP_SCORER_LIMIT) -> Dict[str, Dict]:
    """
    Loads league-wide top scorers using balldontlie season averages.
    Builds:
        NAME_TO_NBA_ID
        NBA_ID_TO_STATS
    Returns dict of top scorers keyed by fake NBA_ID strings for compatibility.
    """

    print("📊 Fetching top scorers from balldontlie...")

    # Step 1 — Get all players
    players = []
    page = 1
    while True:
        r = requests.get(f"{BALD_URL}/players", params={"page": page, "per_page": 100}, timeout=10)
        data = r.json()
        players.extend(data["data"])
        if data["meta"]["next_page"] is None:
            break
        page += 1

    # Step 2 — Get season averages for all players
    player_ids = [p["id"] for p in players]
    averages = {}

    for i in range(0, len(player_ids), 25):
        batch = player_ids[i:i+25]
        r = requests.get(
            f"{BALD_URL}/season_averages",
            params=[("player_ids[]", pid) for pid in batch] + [("season", BALD_SEASON)],
            timeout=10
        )
        for stat in r.json().get("data", []):
            pid = stat["player_id"]
            averages[pid] = stat.get("pts", 0.0)

    # Step 3 — Build stats tables
    global NAME_TO_NBA_ID, NBA_ID_TO_STATS
    NAME_TO_NBA_ID = {}
    NBA_ID_TO_STATS = {}

    for p in players:
        pid = str(p["id"])
        name = f"{p['first_name']} {p['last_name']}"
        ppg = float(averages.get(p["id"], 0.0))

        NAME_TO_NBA_ID[normalize_name(name)] = pid
        NBA_ID_TO_STATS[pid] = {
            "name": name,
            "ppg": ppg,
            "ppg_weight": ppg / EXPECTED_LEAGUE_LEADER_PPG if ppg else 0.0,
        }

    # Top scorers sorted by PPG
    sorted_players = sorted(
        NBA_ID_TO_STATS.items(),
        key=lambda x: x[1]["ppg"],
        reverse=True
    )[:limit]

    top_scorers = {pid: stat for pid, stat in sorted_players}

    print(f"✅ Loaded top {limit} scorers (balldontlie).")
    return top_scorers

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
