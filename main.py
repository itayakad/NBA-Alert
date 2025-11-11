import time
from datetime import datetime
import os
import logging
from odds_api import record_pre_game_spreads, get_pregame_spreads, record_pre_game_totals
from constants import HALFTIME_CHECK_INTERVAL
from player_alerts import get_top_scorers, analyze_game_players
from spread_alerts import analyze_spread_movement
from discord_alert import send_discord_alert
from espn_api import iter_halftimes
from total_alerts import analyze_total_movement

# --- Logging Setup ---
os.makedirs("logs", exist_ok=True)
log_filename = datetime.now().strftime("logs/%Y-%m-%d.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(log_filename, encoding="utf-8")]
)

if __name__ == "__main__":
    print("🚀 NBA Live Monitor Started")
    print("Loading top scorers and pregame spreads...\n")

    # ESPN-only: get_top_scorers no longer uses nba_api
    top_scorers = get_top_scorers()

    # Load previous day/today cached lines first
    pregame_spreads = get_pregame_spreads()
    pregame_totals = record_pre_game_totals()

    # Then attempt to fill in missing ones (but this will NOT overwrite old ones now)
    record_pre_game_spreads()

    # Refresh local copy after update
    pregame_spreads = get_pregame_spreads()

    if pregame_spreads:
        lines = [
            f"{matchup} ({spread:+.1f})"
            for matchup, spread in pregame_spreads.items()
            # Only include full names (abbr is always 3 letters)
            if "@" in matchup and not matchup.split()[0].isupper()
        ]
        formatted_msg = "\n".join(lines)
        send_discord_alert(formatted_msg, title="🚀 Pregame Spreads")
    else:
        send_discord_alert("⚠️ No pregame spreads found.", title="🚀 Pregame Spreads")

    processed_games = set()

    # ---------------- MAIN LOOP ---------------- #
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking halftimes...")

            halftimes = iter_halftimes()

            for g in halftimes:
                matchup = g["matchup"]           # e.g., "DAL @ WSH"
                event_id = g["game_id"]          # ESPN event ID (used by ESPN summary API)
                home_score = g["home_score"]
                away_score = g["away_score"]

                # Skip if already processed
                if event_id in processed_games:
                    continue

                print(f"⏱️ Halftime detected: {matchup}")
                print(f"   Scores — {away_score}-{home_score}")

                processed_games.add(event_id)

                # Player Alerts
                player_alerts = analyze_game_players(
                    event_id,      # ESPN event ID for summary endpoint
                    matchup,
                    top_scorers,   # may be empty if ESPN leaders unavailable; logic handles it
                    home_score,
                    away_score
                )

                spread_alerts = analyze_spread_movement(event_id, matchup)
                total_alerts = analyze_total_movement(event_id, matchup)

                # Combined Alerts
                all_alerts = player_alerts + spread_alerts + total_alerts
                if all_alerts:
                    alert_text = "\n".join(all_alerts)
                    send_discord_alert(alert_text, title=f"📊 {matchup} Halftime")
                    logging.info(f"Halftime Alerts for {matchup}:\n{alert_text}\n")
                else:
                    send_discord_alert("❌ Nothing notable.", title=f"📊 {matchup} Halftime")

        except Exception as e:
            print(f"❌ Error in main loop: {e}")

        time.sleep(HALFTIME_CHECK_INTERVAL)
