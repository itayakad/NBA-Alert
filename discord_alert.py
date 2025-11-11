import requests
from apikeys import DISCORD_WEBHOOK_URL

def send_discord_alert(message, webhook, title="🏀 NBA Alert"):
    """Send a message to your Discord channel via webhook."""
    payload = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": 16753920  # Orange-ish embed color
            }
        ]
    }
    try:
        r = requests.post(webhook, json=payload, timeout=5)
        r.raise_for_status()
        print("✅ Discord alert sent.")
    except Exception as e:
        print(f"⚠️ Failed to send Discord alert: {e}")
