# check_halftimes_once.py
import json
import os
import logging
from datetime import datetime
from app.espn_api import iter_halftimes
from app.player_alerts import get_top_scorers, analyze_game_players
from app.spread_alerts import analyze_spread_movement
from app.total_alerts import analyze_total_movement
from app.discord_alert import send_discord_alert
from app.keys import DISCORD_WEBHOOK_URL, NBA_WEBHOOK_URL

# --- Setup logging ---
os.makedirs("logs", exist_ok=True)
log_filename = datetime.now().strftime("logs/%Y-%m-%d.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(log_filename, encoding="utf-8")]
)

# --- Load state ---
STATE_FILE = "state/processed_games.json"
if not os.path.exists("state"):
    os.makedirs("state")

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            processed_games = set(json.load(f).get("ids", []))
        except Exception:
            processed_games = set()
else:
    processed_games = set()

# --- Main one-pass logic ---
print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking halftimes...")
halftimes = iter_halftimes()

if not halftimes:
    print("❌ No halftimes right now.")
else:
    top_scorers = get_top_scorers()
    new_games = 0

    for g in halftimes:
        matchup = g["matchup"]
        event_id = g["game_id"]
        home_score = g["home_score"]
        away_score = g["away_score"]

        if event_id in processed_games:
            continue  # skip duplicates

        print(f"⏱️ Halftime detected: {matchup} ({away_score}-{home_score})")

        # --- Run analyses ---
        player_alerts = analyze_game_players(event_id, matchup, top_scorers, home_score, away_score)
        spread_alerts = analyze_spread_movement(matchup)
        total_alerts = analyze_total_movement(matchup)

        all_alerts = player_alerts + spread_alerts + total_alerts

        if all_alerts:
            alert_text = "\n\n".join(all_alerts)
            send_discord_alert(alert_text, DISCORD_WEBHOOK_URL, title=f"📊 {matchup} Halftime")
            send_discord_alert(alert_text, NBA_WEBHOOK_URL, title=f"📊 {matchup} Halftime")
            logging.info(f"Halftime Alerts for {matchup}:\n{alert_text}\n")
        else:
            send_discord_alert("❌ Nothing notable.", DISCORD_WEBHOOK_URL, title=f"📊 {matchup} Halftime")
            send_discord_alert("❌ Nothing notable.", NBA_WEBHOOK_URL, title=f"📊 {matchup} Halftime")

        processed_games.add(event_id)
        new_games += 1

    if new_games == 0:
        print("⚙️ All halftimes already processed.")
    else:
        print(f"✅ Processed {new_games} new halftimes.")

# --- Save updated state ---
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump({"ids": list(processed_games)}, f, indent=2)
print("💾 State saved. Done.")
