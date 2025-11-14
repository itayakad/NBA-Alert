import json
import os
import logging
from datetime import datetime

from app.espn_api import iter_halftimes, normalize_name
from app.odds_api import normalize_team_abbr
from app.player_alerts import analyze_game_players
from app.spread_alerts import analyze_spread_movement
from app.total_alerts import analyze_total_movement
from app.discord_alert import send_discord_alert
from app.keys import DISCORD_WEBHOOK_URL, NBA_WEBHOOK_URL
from app.constants import TEAM_MAP

TOP_SCORERS_FILE = "state/top_scorers.json"

os.makedirs("logs/performance_logs", exist_ok=True)
log_filename = datetime.now().strftime("logs/performance_logs/%Y-%m-%d.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(log_filename, encoding="utf-8")]
)

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

REV_TEAM_MAP = {v: k for k, v in TEAM_MAP.items()}

def normalize_matchup_to_abbr(matchup: str) -> str:
    """
    Convert ESPN-style full names into ABBR format.
    Example:
        'Toronto Raptors @ Cleveland Cavaliers' -> 'TOR @ CLE'
        'TOR @ CLE' -> 'TOR @ CLE' (unchanged)
    """
    away, _, home = matchup.partition(" @ ")

    # Already ABBR?
    if len(away) <= 4 and away.isupper():
        return matchup

    away_abbr = REV_TEAM_MAP.get(away, away)
    home_abbr = REV_TEAM_MAP.get(home, home)
    return f"{away_abbr} @ {home_abbr}"

def load_top_scorers_by_name():
    if not os.path.exists(TOP_SCORERS_FILE):
        raise FileNotFoundError("❌ Missing state/top_scorers.json. Run pregame_setup first.")

    with open(TOP_SCORERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    players_list = data.get("players", [])

    out = {}
    for info in players_list:
        norm = normalize_name(info["name"])
        out[norm] = {
            "name": info["name"],
            "ppg": info["ppg"],
            "ppg_weight": info["ppg_weight"]
        }

    return out

print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking halftimes...")
halftimes = iter_halftimes()

if not halftimes:
    print("❌ No halftimes right now.")
else:
    top_scorers = load_top_scorers_by_name()
    new_games = 0

    for g in halftimes:
        matchup_full = g["matchup"]          # Full name from ESPN
        event_id = g["game_id"]
        home_score = g["home_score"]
        away_score = g["away_score"]

        if event_id in processed_games:
            continue

        print(f"⏱️ Halftime detected: {matchup_full} ({away_score}-{home_score})")

        # Step 1: Convert ESPN full-name matchup -> ABBR format (TOR @ CLE)
        abbr_matchup = normalize_matchup_to_abbr(matchup_full)

        # Step 2: Fix ESPN inconsistent abbreviations (UTAH -> UTA, PHO -> PHX, etc.)
        away, _, home = abbr_matchup.partition(" @ ")
        away = normalize_team_abbr(away)
        home = normalize_team_abbr(home)
        abbr_matchup = f"{away} @ {home}"

        # --- Run analyses using ABBR matchup ---
        player_alerts = analyze_game_players(
            event_id,
            abbr_matchup,
            top_scorers,
            home_score,
            away_score
        )

        spread_alerts = analyze_spread_movement(abbr_matchup)
        total_alerts  = analyze_total_movement(abbr_matchup)

        all_alerts = player_alerts + spread_alerts + total_alerts

        if all_alerts:
            alert_text = "\n\n".join(all_alerts)
            send_discord_alert(alert_text, DISCORD_WEBHOOK_URL, title=f"📊 {matchup_full} Halftime")
            send_discord_alert(alert_text, NBA_WEBHOOK_URL, title=f"📊 {matchup_full} Halftime")
            logging.info(f"Halftime Alerts for {matchup_full}:\n{alert_text}\n")
        else:
            msg = "❌ Nothing notable."
            send_discord_alert(msg, DISCORD_WEBHOOK_URL, title=f"📊 {matchup_full} Halftime")
            send_discord_alert(msg, NBA_WEBHOOK_URL, title=f"📊 {matchup_full} Halftime")

        processed_games.add(event_id)
        new_games += 1

    if new_games == 0:
        print("⚙️ All halftimes already processed.")
    else:
        print(f"✅ Processed {new_games} new halftimes.")

with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump({"ids": list(processed_games)}, f, indent=2)

print("💾 State saved. Done.")