import time
from datetime import datetime
from nba_api.live.nba.endpoints import scoreboard
import os
import logging
from constants import HALFTIME_CHECK_INTERVAL
from player_alerts import get_top_scorers, analyze_game_players
from spread_alerts import analyze_spread_movement
from odds_api import record_pre_game_spreads
from discord_alert import send_discord_alert

# --- Logging Setup ---
os.makedirs("logs", exist_ok=True)
log_filename = datetime.utcnow().strftime("logs/%Y-%m-%d.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(log_filename, encoding="utf-8")]
)

def get_live_games():
    """Fetch current live games from the NBA scoreboard."""
    try:
        sb = scoreboard.ScoreBoard()
        return sb.games.get_dict()
    except Exception as e:
        print(f"⚠️ Error fetching scoreboard: {e}")
        return []


if __name__ == "__main__":
    send_discord_alert("🚀 NBA Live Monitor Started", title="Startup 1/2")
    # Load top scorers + pregame spreads
    top_scorers = get_top_scorers()
    record_pre_game_spreads()
    processed_games = set()
    send_discord_alert("✅ Initialization complete", title="Startup 2/2")

    # Main monitoring loop
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking game updates...")
            games = get_live_games()

            for g in games:
                game_id = g["gameId"]
                status = g["gameStatusText"]
                matchup = f"{g['awayTeam']['teamTricode']} @ {g['homeTeam']['teamTricode']}"
                home_score = g["homeTeam"]["score"]
                away_score = g["awayTeam"]["score"]

                # Detect new halftimes
                if "Halftime" in status and game_id not in processed_games:
                    processed_games.add(game_id)

                    # --- Player Alerts ---
                    player_alerts = analyze_game_players(
                        game_id, matchup, top_scorers, home_score, away_score
                    )

                    # --- Spread Alerts ---
                    spread_alerts = analyze_spread_movement(game_id, matchup)

                    # --- Combine + Output ---
                    all_alerts = player_alerts + spread_alerts
                    if all_alerts:
                        alert_text = "\n".join(all_alerts)
                        send_discord_alert(alert_text, title=f"📊 {matchup} Halftime Alert")
                        logging.info(f"Halftime Alerts for {matchup}:\n{alert_text}\n")
                    else:
                        send_discord_alert("❌ Nothing To Note", title=f"📊 {matchup} Halftime Alert")

        except Exception as e:
            print(f"❌ Error in main loop: {e}")

        time.sleep(HALFTIME_CHECK_INTERVAL)
