import time
from datetime import datetime
import os
import logging
from odds_api import record_pre_game_spreads, get_pregame_spreads, record_pre_game_totals, REV_TEAM_MAP
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
    pregame_totals = record_pre_game_totals()

    spread_map = pregame_spreads
    total_map = pregame_totals

    lines = []
    seen = set()

    for matchup in spread_map.keys() | total_map.keys():
        if "@" not in matchup:
            continue
        if matchup.split()[0].isupper():  # skip abbrev keys like "UTA @ IND"
            continue
        if matchup in seen:
            continue

        seen.add(matchup)

        # Full matchup (e.g. "Indiana Pacers @ Utah Jazz")
        full_line = matchup  

        # Abbrev "IND @ UTA"
        away_full, _, home_full = matchup.partition(" @ ")
        away_abbr = REV_TEAM_MAP.get(away_full, away_full)
        home_abbr = REV_TEAM_MAP.get(home_full, home_full)
        abbr = f"{away_abbr} @ {home_abbr}"

        spread = spread_map.get(matchup)
        total = total_map.get(matchup)

        # Second line formatting
        parts = []
        if spread is not None:
            parts.append(f"{home_abbr} {spread:+.1f}")  # Home spread like UTA +2.5
        if total is not None:
            parts.append(f"Total {total:.1f}")

        second_line = " | ".join(parts)

        # Final two-line block
        lines.append(f"{full_line}\n{second_line}")
        

    # Send to Discord
    if lines:
        formatted = "\n\n".join(lines)
        send_discord_alert(formatted, title="🚀 Pregame Lines")
    else:
        send_discord_alert("⚠️ No pregame lines found.", title="🚀 Pregame Lines")

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
