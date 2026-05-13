# -*- coding: utf-8 -*-
"""
Local Business Discovery Agent
--------------------------------
Finds local businesses that have no website so you can offer to build one.

Backends (auto-selected):
  * Google Places API  - if GOOGLE_PLACES_API_KEY is set in config.py (recommended)
                         Works anywhere, returns phone numbers directly.
  * OpenStreetMap      - free fallback, works on most home/office networks.

Steps:
  1. Search for local businesses with no website
  2. Widen the search radius and retry if fewer than MIN_BUSINESSES are found
  3. Enrich each result with phone / email / description where missing
  4. Merge with existing data (your notes & outreach history are preserved)
  5. Save businesses.json and regenerate dashboard.html

Usage:
    python3 agent.py

Requirements:
    pip3 install requests ddgs beautifulsoup4
"""

import sys

import config
from dashboard import generate_dashboard
from enrich import enrich_businesses
from storage import load_businesses, merge_businesses, save_businesses


def _search_google(radius):
    from search_google import search_businesses as google_search
    return google_search(
        config.SEARCH_CITY,
        config.SEARCH_STATE,
        config.SEARCH_COUNTRY,
        radius,
        config.GOOGLE_PLACES_API_KEY,
    )


def _search_osm(radius):
    from search import search_businesses as osm_search

    if config.SEARCH_LAT and config.SEARCH_LON:
        from search import build_overpass_query, parse_business, OVERPASS_ENDPOINTS
        import requests as req
        lat, lon = config.SEARCH_LAT, config.SEARCH_LON
        print("[agent] Using hardcoded coords (%s, %s)" % (lat, lon))
        query = build_overpass_query(lat, lon, radius)
        print("[search] Querying Overpass API (radius=%dm)..." % radius)
        resp = None
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                r = req.post(
                    endpoint,
                    data="data=" + req.utils.quote(query),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "LocalBusinessDiscoveryAgent/1.0",
                    },
                    timeout=90,
                )
                r.raise_for_status()
                resp = r
                break
            except Exception as e:
                print("[search] %s failed: %s" % (endpoint, e))
        if resp is None:
            raise RuntimeError("All Overpass endpoints failed.")
        elements = resp.json().get("elements", [])
        businesses, seen = [], set()
        for el in elements:
            biz = parse_business(el)
            if biz and biz["name"].lower() not in seen:
                seen.add(biz["name"].lower())
                businesses.append(biz)
        businesses.sort(key=lambda b: (0 if b["phone"] else 1, b["name"]))
        return businesses

    return osm_search(
        config.SEARCH_CITY,
        config.SEARCH_STATE,
        config.SEARCH_COUNTRY,
        radius,
    )


def run_agent():
    if config.SEARCH_CITY.startswith("YOUR_"):
        sys.exit("ERROR: Please set SEARCH_CITY and SEARCH_STATE in config.py before running.")

    use_google = bool(getattr(config, "GOOGLE_PLACES_API_KEY", None))
    backend = "Google Places API" if use_google else "OpenStreetMap"

    print("")
    print("=" * 60)
    print("  Local Business Discovery Agent")
    print("  Location : %s, %s" % (config.SEARCH_CITY, config.SEARCH_STATE))
    print("  Backend  : %s" % backend)
    print("  Target   : >=%d businesses" % config.MIN_BUSINESSES)
    print("=" * 60)
    print("")

    # Step 1: Search
    radius = config.SEARCH_RADIUS_M
    businesses = []

    while True:
        try:
            businesses = _search_google(radius) if use_google else _search_osm(radius)
        except Exception as e:
            sys.exit("ERROR during search: %s" % e)

        if len(businesses) >= config.MIN_BUSINESSES:
            break
        if radius >= 50000:
            print("[agent] Max radius reached with %d businesses. Proceeding anyway." % len(businesses))
            break
        new_radius = min(radius * 2, 50000)
        print("[agent] Only %d found at %dm - widening radius to %dm..." % (
            len(businesses), radius, new_radius))
        radius = new_radius

    if not businesses:
        sys.exit(
            "ERROR: No businesses found. "
            "Check your city name and API key (if using Google) in config.py."
        )

    print("[agent] Found %d businesses without websites." % len(businesses))
    print("")

    # Step 2: Enrich
    businesses = enrich_businesses(businesses, config.SEARCH_CITY, config.SEARCH_STATE)

    # Step 3: Merge and save
    existing = load_businesses(config.DATA_FILE)
    merged = merge_businesses(existing, businesses)
    save_businesses(merged, config.DATA_FILE)

    # Step 4: Generate dashboard
    generate_dashboard(
        list(merged.values()),
        config.DASHBOARD_FILE,
        config.SEARCH_CITY,
        config.SEARCH_STATE,
    )

    total = len(merged)
    new_count = total - len(existing)
    with_phone = sum(1 for b in merged.values() if b.get("phone"))
    with_email = sum(1 for b in merged.values() if b.get("email"))

    print("")
    print("=" * 60)
    print("  Done! %d businesses (%d new this run)" % (total, new_count))
    pct_phone = (with_phone * 100 // total) if total else 0
    pct_email = (with_email * 100 // total) if total else 0
    print("  Phone : %d/%d (%d%%)" % (with_phone, total, pct_phone))
    print("  Email : %d/%d (%d%%)" % (with_email, total, pct_email))
    print("  Open %s in your browser" % config.DASHBOARD_FILE)
    print("=" * 60)
    print("")


if __name__ == "__main__":
    run_agent()
