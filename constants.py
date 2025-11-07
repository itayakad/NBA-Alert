# General runtime
HALFTIME_CHECK_INTERVAL = 300   # seconds between scoreboard polls
SEASON = "2025-26"
TOP_SCORER_LIMIT = 25

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
