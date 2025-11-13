# log_alerts.py
import os
import sys
import requests
from datetime import datetime, timedelta

# Ensure access to project modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.keys import LOG_BOT_URL
from app.espn_api import get_yesterday_games

def send_discord_message(content: str, title: str):
    """Send nicely formatted log text to Discord."""
    data = {
        "embeds": [{
            "title": title,
            "description": content or "⚠️ Log file is empty.",
            "color": 5814783,
        }]
    }
    try:
        r = requests.post(LOG_BOT_URL, json=data, timeout=10)
        r.raise_for_status()
        print("✅ Log successfully sent to Discord.")
    except Exception as e:
        print(f"❌ Failed to send log to Discord: {e}")


def read_yesterday_log():
    """Read yesterday’s log from the logs/ folder."""
    yesterday_filename = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d.log")
    log_path = os.path.join("logs/performance_logs", yesterday_filename)

    print(f"📄 Reading log file: {yesterday_filename}")

    if not os.path.exists(log_path):
        print(f"⚠️ No log file found for yesterday: {yesterday_filename}")
        return None, yesterday_filename

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content, yesterday_filename
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return None, yesterday_filename


def get_final_results():
    """Fetch all NBA finals from ESPN and compute final spreads/totals."""
    print("📊 Fetching final results from ESPN...")
    try:
        games = get_yesterday_games()
    except Exception as e:
        print(f"⚠️ Error fetching ESPN games: {e}")
        return []

    finals = []
    for g in games:
        if g["status_name"] and "final" in g["status_name"].lower():
            home = g["home_abbr"]
            away = g["away_abbr"]
            hs = g["home_score"]
            as_ = g["away_score"]
            spread = hs - as_
            total = hs + as_
            finals.append(f"{away} @ {home} → Final: {as_}-{hs} | Spread: {spread:+} | Total: {total}")
    return finals


def main():
    log_content, log_filename = read_yesterday_log()
    log_date = log_filename.replace(".log", "")
    title = f"{log_date}'s Log"

    if not log_content:
        send_discord_message("⚠️ No log file found or log is empty.", title)
        return

    # Append final scores
    finals = get_final_results()
    if finals:
        log_content += "\n\n🏁 **Final Results:**\n" + "\n".join(finals)
    else:
        log_content += "\n\n⚠️ No final results found on ESPN yet."

    # Handle Discord message size
    if len(log_content) <= 1900:
        send_discord_message(log_content, title)
    else:
        print("⚠️ Log too long, sending in chunks...")
        for i in range(0, len(log_content), 1900):
            chunk = log_content[i:i + 1900]
            send_discord_message(chunk, f"{log_date}'s Log (Part {i // 1900 + 1})")


if __name__ == "__main__":
    main()