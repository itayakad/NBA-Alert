from typing import Dict, List
from nba_api.stats.endpoints import leaguedashplayerstats
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
    """
    Loose normalization to match ESPN displayName to NBA API PLAYER_NAME.
    Removes punctuation, spaces, lowercase everything.
    E.g. "P.J. Washington" → "pjwashington"
         "D'Angelo Russell" → "dangelorussell"
    """
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

def get_top_scorers(limit=TOP_SCORER_LIMIT) -> Dict[str, Dict]:
    """
    Pulls league-wide season PPG from nba_api.
    Builds a normalized name -> NBA_ID table for ESPN matching.
    Stores PPG + weighting so halftime alerts know expected scoring.
    """
    global NAME_TO_NBA_ID, NBA_ID_TO_STATS

    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        per_mode_detailed="PerGame"
    ).get_data_frames()[0]

    NAME_TO_NBA_ID = {
        normalize_name(row["PLAYER_NAME"]): str(row["PLAYER_ID"])
        for _, row in stats.iterrows()
    }

    NBA_ID_TO_STATS = {
        str(row["PLAYER_ID"]): {
            "name": row["PLAYER_NAME"],
            "ppg": float(row["PTS"]),
            "ppg_weight": float(row["PTS"]) / EXPECTED_LEAGUE_LEADER_PPG,
        }
        for _, row in stats.iterrows()
    }

    # Select top N scorers
    top_players = stats.sort_values("PTS", ascending=False).head(limit)

    top_scorers = {
        str(row["PLAYER_ID"]): NBA_ID_TO_STATS[str(row["PLAYER_ID"])]
        for _, row in top_players.iterrows()
    }

    print(f"✅ Loaded top {limit} scorers for {SEASON}.")
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
