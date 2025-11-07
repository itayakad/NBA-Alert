from nba_api.live.nba.endpoints import boxscore
from nba_api.stats.endpoints import leaguedashplayerstats
from constants import (
    SEASON,
    TOP_SCORER_LIMIT,
    MIN_MINUTES_FOR_VALID_SAMPLE,
    CONFIDENCE_WEIGHTS,
    EXPECTED_HALF_MINUTES,
    EXPECTED_LEAGUE_LEADER_PPG,
    EXPECTED_HALF_FGA,
)

def get_top_scorers(limit=TOP_SCORER_LIMIT):
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        per_mode_detailed="PerGame",
    ).get_data_frames()[0]

    top_ppg = stats.sort_values("PTS", ascending=False).head(limit)
    top_scorers = {
        str(row["PLAYER_ID"]): {
            "name": row["PLAYER_NAME"],
            "ppg": row["PTS"],
            "ppg_weight": row["PTS"] / EXPECTED_LEAGUE_LEADER_PPG,
        }
        for _, row in top_ppg.iterrows()
    }

    print(f"✅ Loaded top {limit} scorers for {SEASON}.")
    return top_scorers

def compute_confidence(pts, avg_ppg, min_float, fga, home_score, away_score, ppg_weight):
    expected_half_pts = avg_ppg / 2
    U = min(1, pts / expected_half_pts) if expected_half_pts > 0 else 1  # colder is better (1-U)
    M = min(1, min_float / EXPECTED_HALF_MINUTES)
    Y = min(1, fga / EXPECTED_HALF_FGA) if fga is not None else 0
    diff = abs(home_score - away_score)
    C = max(0, 1 - diff / 25)
    P = min(1, ppg_weight)

    w = CONFIDENCE_WEIGHTS
    confidence = (1 - U) * w["U"] + M * w["M"] + Y * w["Y"] + C * w["C"] + P * w["P"]
    return round(max(0, min(confidence, 1)), 2)

def analyze_game_players(game_id, matchup, top_scorers, home_score, away_score):
    """
    For a given game_id and matchup string, returns a list of alert messages
    if any top scorers are underperforming (< 50% of their avg points at half).
    """
    alerts = []
    try:
        bs = boxscore.BoxScore(game_id).game.get_dict()
    except Exception as e:
        return [f"⚠️ Error fetching boxscore for {matchup}: {e}"]

    for side in ["homeTeam", "awayTeam"]:
        for player in bs[side]["players"]:
            pid = str(player["personId"])
            stats = player.get("statistics", {})
            pts = stats.get("points", 0)
            fga = stats.get("fieldGoalsAttempted", 0)
            minutes = stats.get("minutes", "0:00")
            status_flag = player.get("status", "ACTIVE")

            # Skip inactive or 0-min players
            if status_flag != "ACTIVE" or minutes == "0:00" or pts == 0:
                continue

            # Skip players with extremely short stints (e.g., early injury or bench)
            try:
                min_float = float(minutes.split(":")[0]) + float(minutes.split(":")[1]) / 60
                if min_float < MIN_MINUTES_FOR_VALID_SAMPLE and pts < 5:
                    continue
            except Exception:
                min_float = 0

            if pid in top_scorers:
                avg_ppg = top_scorers[pid]["ppg"]
                name = top_scorers[pid]["name"]
                ppg_weight = top_scorers[pid]["ppg_weight"]

                if pts < 0.5 * avg_ppg:
                    conf = compute_confidence(pts, avg_ppg, min_float, fga, home_score, away_score, ppg_weight)
                    msg = (
                        f"⚠️  {name}: {pts} pts in {minutes} "
                        f"(avg {avg_ppg:.1f}) — {matchup} | Confidence: {conf}"
                    )
                    alerts.append(msg)
    return alerts
