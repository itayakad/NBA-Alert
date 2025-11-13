import os
from dotenv import load_dotenv  

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
NBA_WEBHOOK_URL = os.getenv("NBA_WEBHOOK_URL")
LOG_BOT_URL = os.getenv("LOG_BOT_URL")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
ODDS_URL = os.getenv("ODDS_URL")
