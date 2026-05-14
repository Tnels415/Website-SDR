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
#  GOOGLE PLACES API KEY (optional)
#  Leave as "" to use the free Yellow Pages + OpenStreetMap backends
#  (no signup or API key needed - this is the default).
#  To switch to Google Places: get a key at console.cloud.google.com,
#  enable "Places API" and "Geocoding API", then paste it below.
# -----------------------------------------------
GOOGLE_PLACES_API_KEY = ""

# -----------------------------------------------
#  OPTIONAL: hardcode your city coordinates
#  Skips geocoding if it is blocked on your network.
#  Leave as None to geocode automatically.
#  To find lat/lon: right-click on Google Maps, click "What's here?"
# -----------------------------------------------
SEARCH_LAT = 37.7799   # San Ramon, CA
SEARCH_LON = -121.9780  # San Ramon, CA
