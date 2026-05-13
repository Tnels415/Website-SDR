"""
Local Business Discovery Agent
--------------------------------
Finds local businesses that have no website so you can offer to build one for them.

Backends (auto-selected):
  • Google Places API  — if GOOGLE_PLACES_API_KEY is set in config.py (recommended)
                         Works anywhere, returns phone numbers directly.
  • OpenStreetMap       — free fallback, works on most home/office networks.

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


def _search_google(radius: int) -> list[dict]:
    from search_google import search_businesses as google_search
    return google_search(
        config.SEARCH_CITY,
        config.SEARCH_STATE,
        config.SEARCH_COUNTRY,
        radius,
        config.GOOGLE_PLACES_API_KEY,
    )


def _search_osm(radius: int) -> list[dict]:
    from search import search_businesses as osm_search

    # Allow manually-configured lat/lon to bypass geocoding
    if config.SEARCH_LAT and config.SEARCH_LON:
        from search import build_overpass_query, parse_business, OVERPASS_ENDPOINTS
        import requests as req
        lat, lon = config.SEARCH_LAT, config.SEARCH_LON
        print(f"[agent] Using hardcoded coords ({lat}, {lon})")
        query = build_overpass_query(lat, lon, radius)
        print(f"[search] Querying Overpass API (radius={radius}m)…")
        resp = None
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                r = req.post(
                    endpoint,
                    data=f"data={req.utils.quote(query)}",
                    headers={"Content-Type": "application/x-www-form-urlencoded",
                             "User-Agent": "LocalBusinessDiscoveryAgent/1.0"},
                    timeout=90,
                )
                r.raise_for_status()
                resp = r
                break
            except Exception as e:
                print(f"[search] {endpoint} failed: {e}")
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


def run_agent() -> None:
    if config.SEARCH_CITY.startswith("YOUR_"):
        sys.exit(
            "ERROR: Please set SEARCH_CITY and SEARCH_STATE in config.py before running."
        )

    use_google = bool(getattr(config, "GOOGLE_PLACES_API_KEY", None))
    backend = "Google Places API" if use_google else "OpenStreetMap"

    print(f"\n{'='*60}")
    print(f"  Local Business Discovery Agent")
    print(f"  Location : {config.SEARCH_CITY}, {config.SEARCH_STATE}")
    print(f"  Backend  : {backend}")
    print(f"  Target   : ≥{config.MIN_BUSINESSES} businesses")
    print(f"{'='*60}\n")

    # ── Step 1: Search ────────────────────────────────────────────────────────
    radius = config.SEARCH_RADIUS_M
    businesses: list[dict] = []

    while len(businesses) < config.MIN_BUSINESSES and radius <= 50_000:
        try:
            businesses = _search_google(radius) if use_google else _search_osm(radius)
        except Exception as e:
            sys.exit(f"ERROR during search: {e}")

        if len(businesses) < config.MIN_BUSINESSES:
            new_radius = min(radius * 2, 50_000)
            print(
                f"[agent] Only {len(businesses)} found at {radius}m "
                f"— widening radius to {new_radius}m…"
            )
            radius = new_radius

    if not businesses:
        sys.exit(
            "ERROR: No businesses found. "
            "Check your city name and API key (if using Google) in config.py."
        )

    print(f"[agent] ✓ Found {len(businesses)} businesses without websites.\n")

    # ── Step 2: Enrich (email, phone, description) ────────────────────────────
    businesses = enrich_businesses(businesses, config.SEARCH_CITY, config.SEARCH_STATE)

    # ── Step 3: Merge with existing data & save ───────────────────────────────
    existing = load_businesses(config.DATA_FILE)
    merged = merge_businesses(existing, businesses)
    save_businesses(merged, config.DATA_FILE)

    # ── Step 4: Generate dashboard ────────────────────────────────────────────
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

    print(f"\n{'='*60}")
    print(f"  Done!  {total} businesses ({new_count} new this run)")
    print(f"  Phone  : {with_phone}/{total} ({with_phone*100//total if total else 0}%)")
    print(f"  Email  : {with_email}/{total} ({with_email*100//total if total else 0}%)")
    print(f"  Open {config.DASHBOARD_FILE} in your browser")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_agent()
