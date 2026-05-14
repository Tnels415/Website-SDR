# -*- coding: utf-8 -*-
"""
DuckDuckGo-based local business discovery.

Searches DuckDuckGo for each business type in the target city, then parses
individual business listings from Yelp, Yellow Pages, and BBB results.
Those sources surface small local businesses — many of which have no website.

No API key required. Uses the ddgs package (already in requirements.txt).
"""

import re
import time
from typing import Optional

BUSINESS_TYPES = [
    "restaurant", "cafe", "bakery", "bar",
    "hair salon", "nail salon", "barber",
    "spa", "massage",
    "auto repair", "car wash",
    "plumber", "electrician", "painter", "handyman", "locksmith",
    "dentist", "chiropractor", "doctor", "physical therapy",
    "florist", "pet grooming", "dry cleaning", "laundry",
    "photographer", "catering",
    "accountant", "insurance agent", "lawyer",
    "gym", "yoga studio",
    "landscaping", "house cleaning",
    "real estate agent", "mortgage broker",
]

# Domains that list individual local businesses (not chains / aggregators)
LISTING_DOMAINS = ("yelp.com/biz/", "yellowpages.com/", "bbb.org/us/")

# Domains that mean the result IS the business's own website (has a website)
OWNED_DOMAINS_SKIP = (
    "yelp.com", "yellowpages.com", "tripadvisor.com", "facebook.com",
    "instagram.com", "twitter.com", "google.com", "foursquare.com",
    "bbb.org", "manta.com", "superpages.com", "angieslist.com",
    "homeadvisor.com", "thumbtack.com", "nextdoor.com", "bing.com",
    "mapquest.com", "citysearch.com", "merchantcircle.com",
    "chamberofcommerce.com", "houzz.com", "angi.com",
)

PHONE_RE = re.compile(
    r'(?:\+?1[-.\s]?)?'
    r'\(?\d{3}\)?'
    r'[-.\s]\d{3}[-.\s]\d{4}'
)


def _normalise_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return "(%s) %s-%s" % (digits[:3], digits[3:6], digits[6:])


def _extract_phone(text: str) -> str:
    for match in PHONE_RE.findall(text):
        phone = _normalise_phone(match)
        if phone:
            return phone
    return ""


def _parse_title(title: str, city: str) -> Optional[str]:
    """
    Extract a business name from a directory search result title.

    Yelp individual:   "Mario's Bistro - Italian Restaurant - San Ramon - Yelp"
    YP individual:     "Mario's Bistro - San Ramon, CA - Yellow Pages"
    BBB individual:    "Mario's Bistro | Better Business Bureau"
    Generic:           "Mario's Bistro | San Ramon, CA"

    Returns None for list/category pages ("Best Restaurants in San Ramon - Yelp").
    """
    # Skip obvious list/aggregator pages
    lower = title.lower()
    skip_phrases = ("best ", "top ", "near me", "find ", "results for",
                    "search results", "restaurants in ", "salons in ",
                    " reviews", "directory")
    if any(p in lower for p in skip_phrases):
        return None

    # Split on common separators; the first segment is usually the business name
    for sep in (" - ", " | ", " · ", " — "):
        if sep in title:
            name = title.split(sep)[0].strip()
            # Sanity: must be 3-60 chars and not just the city name
            if 3 <= len(name) <= 60 and city.lower() not in name.lower():
                return name

    return None


def _is_own_website(href: str) -> bool:
    """Return True if href looks like the business's own website (skip it)."""
    return not any(d in href for d in OWNED_DOMAINS_SKIP)


def search_businesses(city: str, state: str, country: str, radius_m: int) -> list:
    """
    Find local businesses in the given city via DuckDuckGo text search.
    Parses individual business listings from directory-site snippets.
    Returns businesses sorted with phone-bearing entries first.
    radius_m is accepted for interface compatibility but unused (search is city-based).
    """
    try:
        from ddgs import DDGS
    except ImportError:
        print("[ddg] ddgs package not installed. Run: pip3 install ddgs")
        return []

    print("[ddg] Searching DuckDuckGo for businesses in %s, %s..." % (city, state))

    businesses: list = []
    seen_names: set = set()
    consecutive_failures = 0

    for btype in BUSINESS_TYPES:
        if len(businesses) >= 120:
            break
        if consecutive_failures >= 4:
            print("[ddg] Too many consecutive failures — DDG may be rate-limiting. Stopping.")
            break

        query = '%s "%s" %s' % (btype, city, state)
        try:
            results = DDGS().text(query, max_results=15)
        except Exception as e:
            print("[ddg]   Search failed for '%s': %s" % (btype, e))
            consecutive_failures += 1
            time.sleep(2)
            continue

        if not results:
            consecutive_failures += 1
            time.sleep(1)
            continue

        consecutive_failures = 0
        btype_count = 0

        for r in results:
            href = r.get("href", "") or ""
            title = r.get("title", "") or ""
            body = r.get("body", "") or ""

            # If the result goes directly to a business's own website, they
            # already have one — skip (unless it's a directory listing)
            if href and _is_own_website(href):
                continue

            name = _parse_title(title, city)
            if not name:
                continue

            key = name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)

            phone = _extract_phone(body + " " + title)

            businesses.append({
                "id": "ddg_%s_%s" % (
                    re.sub(r"\W+", "_", key).strip("_"),
                    city.lower().replace(" ", "_"),
                ),
                "name": name,
                "category": btype,
                "phone": phone,
                "email": "",
                "address": "%s, %s" % (city, state),
                "hours": "",
                "lat": None,
                "lon": None,
                "description": "",
                "status": "not_contacted",
                "outreach": [],
                "notes": "",
                "source": "duckduckgo",
            })
            btype_count += 1

        if btype_count:
            print("[ddg]   %s: %d businesses" % (btype, btype_count))

        time.sleep(0.5)

    businesses.sort(key=lambda b: (0 if b["phone"] else 1, b["name"]))
    print("[ddg] Done — %d local businesses found." % len(businesses))
    return businesses
