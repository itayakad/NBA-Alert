import os
import sys
import re
import requests
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.keys import LOG_BOT_URL
from app.espn_api import (
    get_yesterday_games,
    fetch_boxscore_players,
    normalize_name
)

def send_discord_message(content: str, title: str):
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
        print("✅ Sent to Discord.")
    except Exception as e:
        print(f"❌ Discord send error: {e}")

def read_yesterday_log():
    filename = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d.log")
    path = os.path.join("logs/performance_logs", filename)

    if not os.path.exists(path):
        return None, filename

    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip(), filename

def get_final_results_map():
    """Return dict keyed by (AWAY, HOME) with scores and event IDs."""
    games = get_yesterday_games()
    finals = {}

    for g in games:
        if g["status_name"] and "final" in g["status_name"].lower():
            away = g["away_abbr"]
            home = g["home_abbr"]
            finals[(away, home)] = {
                "away": g["away_score"],
                "home": g["home_score"],
                "game_id": g["game_id"]
            }

    return finals

def get_final_boxscores(finals):
    """Load all final boxscores keyed by (AWAY, HOME)."""
    boxscores = {}

    for (away, home), info in finals.items():
        event_id = info.get("game_id")
        if not event_id:
            boxscores[(away, home)] = {}
            continue

        players = fetch_boxscore_players(event_id)
        boxscores[(away, home)] = {
            normalize_name(p["name"]): p for p in players
        }

    return boxscores

def evaluate_spread(team, line, away, home, finals):
    if (away, home) not in finals:
        return "⚠️ No final found", None

    home_score = finals[(away, home)]["home"]
    away_score = finals[(away, home)]["away"]

    # Determine if pick team was home or away
    team_score = home_score if team == home else away_score
    opp_score = away_score if team == home else home_score

    # Margin from perspective of the picked team
    margin = team_score - opp_score

    # Adjusted result with the spread applied
    # Bet wins if team_score + line > opp_score
    adjusted = team_score + line - opp_score

    if adjusted > 0:
        covered = True
        result = "✔️ Covered"
    elif adjusted == 0:
        covered = None  # push (shouldn't happen with .5 lines, but safe)
        result = "➖ Push"
    else:
        covered = False
        result = "❌ Missed"

    msg = (
        f"{result}: Final margin was {margin:+} ({away} {away_score} – {home} {home_score})"
    )

    return msg, covered

def evaluate_total(direction, target, away, home, finals):
    if (away, home) not in finals:
        return "⚠️ No final found", None

    home_score = finals[(away, home)]["home"]
    away_score = finals[(away, home)]["away"]

    total = home_score + away_score

    if direction.lower() == "under":
        hit = total < target
        result = "✔️ Under hit" if hit else "❌ Under missed"
    else:
        hit = total > target
        result = "✔️ Over hit" if hit else "❌ Over missed"

    msg = (
        f"{result}: Final total was {total} ({away} {away_score} – {home} {home_score})"
    )

    return msg, hit

def evaluate_player(player_name, ht_pts, avg, away, home, finals, boxscores):
    key = (away, home)
    if key not in boxscores:
        return "⚠️ No boxscore found", None

    lookup = boxscores[key]
    norm = normalize_name(player_name)

    if norm not in lookup:
        return f"⚠️ Final stats not found for {player_name}", None

    final_pts = lookup[norm]["points"]
    needed = int(avg*0.85) - 0.5 if avg < 30 else 25.5

    covered = final_pts >= needed
    result = "✔️ Covered" if covered else "❌ Missed"

    msg = (
        f"Over {needed} {result}: Final pts {final_pts}"
    )

    return msg, covered

def main():
    log_content, log_filename = read_yesterday_log()
    log_date = log_filename.replace(".log", "")
    title = f"{log_date}'s Log"

    if not log_content:
        send_discord_message("⚠️ No log file or empty.", title)
        return

    # ---- Load finals & boxscores ----
    finals = get_final_results_map()
    boxscores = get_final_boxscores(finals)

    # ---- Record tracking ----
    spread_hits = 0
    spread_misses = 0
    total_hits = 0
    total_misses = 0
    player_hits = 0
    player_misses = 0

    output = [f"📊 **Alert Evaluation for {log_date}**"]
    blocks = re.split(r"Halftime Alerts for ", log_content)[1:]

    for block in blocks:
        header_line = block.split("\n")[0]
        matchup = header_line.replace(":", "").strip()
        away, _, home = matchup.partition("@")
        away = away.strip()
        home = home.strip()

        output.append(f"\n### 🏀 {away} @ {home}")

        # ------- Spread -------
        spread_match = re.search(
            r"Scoey's Take: .*?(?:Take|back|consider taking)\s+([A-Z]{2,3})\s*([+-]?\d+\.\d+)",
            block, re.I
        )
        if spread_match:
            team = spread_match.group(1)
            line = float(spread_match.group(2))
            msg, hit = evaluate_spread(team, line, away, home, finals)
            output.append(f"- **Spread Pick:** {team} {line:+} {msg}")

            if hit is True:
                spread_hits += 1
            elif hit is False:
                spread_misses += 1

        # ------- Totals -------
        total_match = re.search(r"Under\s+(\d+\.\d+)|Over\s+(\d+\.\d+)", block, re.I)
        if total_match:
            under = total_match.group(1)
            over = total_match.group(2)

            if under:
                msg, hit = evaluate_total("under", float(under), away, home, finals)
                output.append(f"- **Total Pick:** Under {under} → {msg}")
                if hit is True:
                    total_hits += 1
                elif hit is False:
                    total_misses += 1

            if over:
                msg, hit = evaluate_total("over", float(over), away, home, finals)
                output.append(f"- **Total Pick:** Over {over} → {msg}")
                if hit is True:
                    total_hits += 1
                elif hit is False:
                    total_misses += 1

        # ------- Player -------
        player_match = re.findall(
            r"🎯 ([A-Za-z .'-]+): (\d+) pts.*?avg (\d+\.\d+)",
            block
        )
        for name, pts, avg in player_match:
            pts = int(pts)
            avg = float(avg)

            msg, hit = evaluate_player(name, pts, avg, away, home, finals, boxscores)
            output.append(f"- **Player:** {name} {msg}")

            if hit is True:
                player_hits += 1
            elif hit is False:
                player_misses += 1

    # ---- FINAL SUMMARY ----

    total_hits_all = spread_hits + total_hits + player_hits
    total_misses_all = spread_misses + total_misses + player_misses
    total_all = total_hits_all + total_misses_all

    winrate = (total_hits_all / total_all * 100) if total_all > 0 else 0.0

    summary = [
        "\n\n🏁 **Final Daily Summary**",
        f"**Overall Record:** {total_hits_all}–{total_misses_all} ({winrate:.1f}%)",
        "",
        f"📊 **Spreads:** {spread_hits}–{spread_misses}",
        f"📈 **Totals:** {total_hits}–{total_misses}",
        f"🎯 **Player Props:** {player_hits}–{player_misses}",
    ]

    output.extend(summary)

    final_message = "\n".join(output)

    if len(final_message) < 1900:
        send_discord_message(final_message, title)
    else:
        for i in range(0, len(final_message), 1900):
            send_discord_message(final_message[i:i+1900], f"{title} (Part {i//1900+1})")

if __name__ == "__main__":
    main()