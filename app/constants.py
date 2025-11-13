# General runtime
HALFTIME_CHECK_INTERVAL = 300   # seconds between scoreboard polls
SEASON = "2025-26"
TOP_SCORER_LIMIT = 50

# Thresholds
PERCENT_UNDERPERFORMANCE_TRIGGER = 0.4   # 40% of average at halftime
MIN_MINUTES_FOR_VALID_SAMPLE = 5.0       # ignore players with less than 5 min

# Confidence model weights
CONFIDENCE_WEIGHTS = {
    "U": 0.35,  # underperformance ratio (colder → higher upside)
    "M": 0.20,  # minutes factor
    "Y": 0.20,  # usage factor (FGA pace)
    "C": 0.15,  # competitiveness factor (score differential)
    "P": 0.10,  # superstar weighting
}

# Expected baselines
EXPECTED_HALF_MINUTES = 18.0
EXPECTED_LEAGUE_LEADER_PPG = 30.0
EXPECTED_HALF_FGA = 10.0

TEAM_MAP = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

POINTS_CONFIDENCE_MAP = [
    (0.30, "Fade him"),
    (0.50, "Lowkey coud turn it up"),
    (0.60, "Get the line while its low"),
    (1.01, "Hammer the over 🔨🔒"),
]

TOTAL_CONFIDENCE_MAP = [          
    (0.05, "Not worth touching"),        
    (0.10, "It's worth considering"),      
    (0.15, "Tail the"),           
    (1.01, "Hammer the")   
]

SPREADS_CONFIDENCE_MAP = [
    (3.0, "Not worth touching"),    
    (6.0, "Consider taking the cover for"),   
    (9.0, "Tail the"),   
    (999, "Hammer the"),       
]

def confidence_to_label(conf,alert_type):
    if alert_type=="TOTAL":
        map = TOTAL_CONFIDENCE_MAP
    elif alert_type=="SPREAD":
        map = SPREADS_CONFIDENCE_MAP
    else:
        map = POINTS_CONFIDENCE_MAP
    for threshold, label in map:
        if conf <= threshold:
            return label
    return "🟦 UNKNOWN"