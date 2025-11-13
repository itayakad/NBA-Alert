from typing import Dict, List
from app.constants import (
    MIN_MINUTES_FOR_VALID_SAMPLE,
    CONFIDENCE_WEIGHTS,
    EXPECTED_HALF_MINUTES,
    EXPECTED_LEAGUE_LEADER_PPG,
    EXPECTED_HALF_FGA,
    confidence_to_label,
)
from app.espn_api import fetch_boxscore_players, normalize_name

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
    """
    Name-based version:
    - top_scorers is now a dict: normalized_name -> {"name", "ppg", "ppg_weight"}
    - We match solely by normalized ESPN name.
    """
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

        # Convert minutes into float
        try:
            mm, ss = minutes.split(":")
            min_float = int(mm) + int(ss) / 60
        except:
            min_float = 0

        # Discard tiny stints unless scoring >5
        if min_float < MIN_MINUTES_FOR_VALID_SAMPLE and pts < 5:
            continue

        # Normalize for name-matching
        norm = normalize_name(name)

        # If name not in top_scorers → skip
        if norm not in top_scorers:
            continue

        player_info = top_scorers[norm]
        avg_ppg = player_info["ppg"]
        ppg_weight = player_info["ppg_weight"]

        # Compute halftime confidence
        conf = compute_confidence(
            pts, avg_ppg, min_float, fga, home_score, away_score, ppg_weight
        )
        pace = pts / avg_ppg if avg_ppg > 0 else 0

        # Underperforming at halftime (< 50% pace)
        if pace < 0.50:
            conf_label = confidence_to_label(conf, "POINTS")
            alerts.append(
                f"🎯 {name}: {pts} pts in {minutes} min (season avg {avg_ppg:.1f})\n"
                f"Scoey's Take: {conf_label}"
            )

    return alerts