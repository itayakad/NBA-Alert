# pregame_setup.py
import json
import os
import logging
from datetime import datetime
from app.odds_api import record_pre_game_spreads, get_pregame_spreads, record_pre_game_totals, REV_TEAM_MAP
from app.espn_api import get_top_scorers
from app.discord_alert import send_discord_alert
from app.keys import DISCORD_WEBHOOK_URL, NBA_WEBHOOK_URL

# Reset processed_games.json daily
STATE_FILE = "state/processed_games.json"
with open(STATE_FILE, "w") as f:
    json.dump({"ids": []}, f, indent=2)
print("🔄 Reset processed_games.json for a new day.")

# --- Logging Setup ---
os.makedirs("logs/performance_logs", exist_ok=True)
log_filename = datetime.now().strftime("logs/%Y-%m-%d.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(log_filename, encoding="utf-8")]
)

print("🚀 NBA Pregame Setup Started")
print("Fetching top scorers and pregame lines...\n")

# Top scorers
top_scorers = get_top_scorers()

# Record spreads/totals
pregame_spreads = record_pre_game_spreads()
pregame_totals = record_pre_game_totals()

spread_map = get_pregame_spreads()
total_map = pregame_totals

lines = []
seen = set()

for matchup in spread_map.keys() | total_map.keys():
    if "@" not in matchup:
        continue
    if matchup.split()[0].isupper():  # skip abbrev keys
        continue
    if matchup in seen:
        continue

    seen.add(matchup)

    full_line = matchup
    away_full, _, home_full = matchup.partition(" @ ")
    away_abbr = REV_TEAM_MAP.get(away_full, away_full)
    home_abbr = REV_TEAM_MAP.get(home_full, home_full)
    abbr = f"{away_abbr} @ {home_abbr}"

    spread = spread_map.get(matchup)
    total = total_map.get(matchup)

    parts = []
    if spread is not None:
        parts.append(f"{home_abbr} {spread:+.1f}")
    if total is not None:
        parts.append(f"Total {total:.1f}")

    second_line = " | ".join(parts)
    lines.append(f"{full_line}\n{second_line}")

# Send to Discord
if lines:
    formatted = "\n\n".join(lines)
    send_discord_alert(formatted, DISCORD_WEBHOOK_URL, title="🚀 Pregame Lines")
    send_discord_alert(formatted, NBA_WEBHOOK_URL, title="🚀 Pregame Lines")
else:
    send_discord_alert("⚠️ No pregame lines found.", DISCORD_WEBHOOK_URL, title="🚀 Pregame Lines")
    send_discord_alert("⚠️ No pregame lines found.", NBA_WEBHOOK_URL, title="🚀 Pregame Lines")

print("✅ Pregame setup complete.")
