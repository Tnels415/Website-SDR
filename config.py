# ─────────────────────────────────────────────
#  EDIT THESE VALUES BEFORE RUNNING THE AGENT
# ─────────────────────────────────────────────

SEARCH_CITY       = "San Ramon"    # e.g. "Cincinnati"
SEARCH_STATE      = "California"   # e.g. "Ohio"
SEARCH_COUNTRY    = "US"           # ISO country code

# Radius (in meters) around the city center to search
SEARCH_RADIUS_M   = 10_000         # 10 km — increase for larger areas

# Minimum number of businesses the agent must find before it finishes
MIN_BUSINESSES    = 10

# Output file paths (relative to this directory)
DATA_FILE         = "businesses.json"
DASHBOARD_FILE    = "dashboard.html"

# ─────────────────────────────────────────────
#  GOOGLE PLACES API KEY  (recommended)
#  Get a free key at: console.cloud.google.com
#  Enable "Places API" and "Geocoding API"
#  Paste your key below — this unlocks much richer data
#  and is the only backend that works on all networks.
# ─────────────────────────────────────────────
GOOGLE_PLACES_API_KEY = None   # e.g. "AIzaSy..."

# ─────────────────────────────────────────────
#  OPTIONAL: hardcode your city's coordinates
#  to skip geocoding (useful if geocoding is blocked)
#  Leave as None to geocode automatically.
#  Find your city's lat/lon: right-click on Google Maps → "What's here?"
# ─────────────────────────────────────────────
SEARCH_LAT = None   # e.g. 37.7799
SEARCH_LON = None   # e.g. -121.9780
