# -*- coding: utf-8 -*-
# -----------------------------------------------
#  EDIT THESE VALUES BEFORE RUNNING THE AGENT
# -----------------------------------------------

SEARCH_CITY     = "San Ramon"   # e.g. "Cincinnati"
SEARCH_STATE    = "California"  # e.g. "Ohio"
SEARCH_COUNTRY  = "US"          # ISO country code

# Radius in meters around the city center to search
SEARCH_RADIUS_M = 10000         # 10 km - increase for larger areas

# Minimum businesses the agent must find before finishing
MIN_BUSINESSES  = 10

# Output file paths (relative to this directory)
DATA_FILE       = "businesses.json"
DASHBOARD_FILE  = "dashboard.html"

# -----------------------------------------------
#  GOOGLE PLACES API KEY (recommended)
#  Get a free key at: console.cloud.google.com
#  Enable "Places API" and "Geocoding API"
#  Paste your key below (must be inside the quotes).
# -----------------------------------------------
GOOGLE_PLACES_API_KEY = "AIzaSyA_Tor-6fb8EVp6sXICH3h1bj23s1S06fs"

# -----------------------------------------------
#  OPTIONAL: hardcode your city coordinates
#  Skips geocoding if it is blocked on your network.
#  Leave as None to geocode automatically.
#  To find lat/lon: right-click on Google Maps, click "What's here?"
# -----------------------------------------------
SEARCH_LAT = None   # e.g. 37.7799
SEARCH_LON = None   # e.g. -121.9780
