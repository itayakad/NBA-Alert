import json
import os
import logging
from datetime import datetime
from app.odds_api import record_all_pregame_lines
from app.espn_api import get_top_scorers
from app.discord_alert import send_discord_alert
from app.keys import DISCORD_WEBHOOK_URL, NBA_WEBHOOK_URL

STATE_FILE = "state/processed_games.json"
with open(STATE_FILE, "w") as f:
    json.dump({"ids": []}, f, indent=2)
print("🔄 Reset processed_games.json for a new day.")

os.makedirs("logs/performance_logs", exist_ok=True)
log_filename = datetime.now().strftime("logs/%Y-%m-%d.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(log_filename, encoding="utf-8")]
)

print("🚀 NBA Pregame Setup Started")
print("Fetching top scorers and pregame lines...\n")

top_scorers = get_top_scorers()

pregame = record_all_pregame_lines()
spreads = pregame["spreads"]   # ABBR keys only
totals  = pregame["totals"]

lines = []

for abbr in sorted(spreads.keys() | totals.keys()):
    if "@" not in abbr:
        continue

    spread = spreads.get(abbr)
    total  = totals.get(abbr)

    parts = []
    if spread is not None:
        # home team = right side of "A @ B"
        home = abbr.split(" @ ")[1]
        parts.append(f"{home} {spread:+.1f}")
    if total is not None:
        parts.append(f"Total {total:.1f}")

    lines.append(f"{abbr}\n" + " | ".join(parts))

if lines:
    formatted = "\n\n".join(lines)
    send_discord_alert(formatted, DISCORD_WEBHOOK_URL, title="🚀 Pregame Lines")
    send_discord_alert(formatted, NBA_WEBHOOK_URL, title="🚀 Pregame Lines")
else:
    msg = "⚠️ No pregame lines found."
    send_discord_alert(msg, DISCORD_WEBHOOK_URL, title="🚀 Pregame Lines")
    send_discord_alert(msg, NBA_WEBHOOK_URL, title="🚀 Pregame Lines")

print("✅ Pregame setup complete.")
