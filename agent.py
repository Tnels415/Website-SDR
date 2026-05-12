"""
Local Business Discovery Agent
--------------------------------
Finds local businesses that have no website so you can offer to build one for them.

Steps:
  1. Search OpenStreetMap for businesses without a website tag
  2. Widen the search radius and retry if fewer than MIN_BUSINESSES are found
  3. Enrich each result with email / description via DuckDuckGo (no API key needed)
  4. Merge with existing data (your notes & outreach history are preserved)
  5. Save businesses.json and regenerate dashboard.html

Usage:
    python agent.py

Requirements:
    pip install requests duckduckgo-search
"""

import sys

import config
from dashboard import generate_dashboard
from enrich import enrich_businesses
from search import search_businesses
from storage import load_businesses, merge_businesses, save_businesses


def run_agent() -> None:
    if config.SEARCH_CITY.startswith("YOUR_"):
        sys.exit(
            "ERROR: Please set SEARCH_CITY and SEARCH_STATE in config.py before running."
        )

    print(f"\n{'='*60}")
    print(f"  Local Business Discovery Agent")
    print(f"  Location : {config.SEARCH_CITY}, {config.SEARCH_STATE}")
    print(f"  Target   : ≥{config.MIN_BUSINESSES} businesses")
    print(f"{'='*60}\n")

    # ── Step 1: Search (retry with expanding radius until target is met) ──────
    radius = config.SEARCH_RADIUS_M
    businesses: list[dict] = []

    while len(businesses) < config.MIN_BUSINESSES and radius <= 50_000:
        businesses = search_businesses(
            config.SEARCH_CITY,
            config.SEARCH_STATE,
            config.SEARCH_COUNTRY,
            radius,
        )
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
            "Check your city name in config.py and your network connection."
        )

    print(f"[agent] ✓ Found {len(businesses)} businesses without websites.\n")

    # ── Step 2: Enrich ────────────────────────────────────────────────────────
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
    print(f"  📞  {with_phone}/{total} have phone numbers ({with_phone*100//total if total else 0}%)")
    print(f"  ✉️   {with_email}/{total} have email addresses ({with_email*100//total if total else 0}%)")
    print(f"  Open {config.DASHBOARD_FILE} in your browser")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_agent()
