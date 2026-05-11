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
