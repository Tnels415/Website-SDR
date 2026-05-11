# ─────────────────────────────────────────────
#  EDIT THESE VALUES BEFORE RUNNING THE AGENT
# ─────────────────────────────────────────────

SEARCH_CITY       = "San Ramon"    # e.g. "Cincinnati"
SEARCH_STATE      = "California"   # e.g. "Ohio"
SEARCH_COUNTRY    = "US"                # ISO country code

# Radius (in meters) around the city center to search
SEARCH_RADIUS_M   = 1000             # 10 km  — increase for larger areas

# Minimum number of businesses the agent must find before it finishes
MIN_BUSINESSES    = 10

# Output file paths (relative to this directory)
DATA_FILE         = "businesses.json"
DASHBOARD_FILE    = "dashboard.html"

# ─────────────────────────────────────────────
#  ANTHROPIC API KEY
#  Set via environment variable:  ANTHROPIC_API_KEY=sk-...
#  or paste it directly below (not recommended for shared repos)
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = None   # leave None to read from env
