# -*- coding: utf-8 -*-
"""
Google Places API search backend.
Finds local businesses that have no website using:
  1. Google Geocoding API  - city name -> lat/lon
  2. Google Places Nearby Search (rankby=distance) - small local businesses
  3. Google Place Details  - phone, address, hours, website check

Requires: GOOGLE_PLACES_API_KEY in config.py
"""

import json
import time
import requests
from typing import Optional

GEOCODE_URL    = "https://maps.googleapis.com/maps/api/geocode/json"
NEARBY_URL     = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
TEXTSEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL    = "https://maps.googleapis.com/maps/api/place/details/json"

# Types searched via Nearby Search with rankby=distance (no radius needed)
# Each call returns up to 60 results (3 pages x 20). Small/local businesses
# are more likely to lack a website than prominent chains.
NEARBY_TYPES = [
    "restaurant", "cafe", "bakery", "bar",
    "beauty_salon", "hair_care", "spa",
    "car_repair", "car_wash",
    "laundry", "dry_cleaning",
    "florist", "pet_store",
    "accounting", "lawyer", "insurance_agency",
    "dentist", "doctor", "physiotherapist",
    "electrician", "plumber", "painter", "locksmith",
    "clothing_store", "shoe_store", "jewelry_store",
]

# Text Search keywords — finds small local businesses not surfaced by type search
TEXT_KEYWORDS = [
    "local shop",
    "small business",
    "family owned",
    "nail salon",
    "barber",
    "auto repair",
    "handyman",
    "cleaning service",
    "daycare",
    "tutoring",
    "alterations tailor",
    "photography studio",
    "catering",
    "food truck",
]

DETAILS_FIELDS = ",".join([
    "name",
    "formatted_phone_number",
    "international_phone_number",
    "formatted_address",
    "website",
    "opening_hours",
    "types",
    "editorial_summary",
    "business_status",
])

MAX_CANDIDATES = 400  # fetch details for up to this many candidates


def _get(url: str, params: dict) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return json.loads(resp.text)
    except Exception as e:
        print(f"[google] Request failed: {e}")
        return None


def geocode_city(city: str, state: str, country: str, api_key: str) -> Optional[tuple]:
    """Return (lat, lon) using Google Geocoding API."""
    data = _get(GEOCODE_URL, {
        "address": f"{city}, {state}, {country}",
        "key": api_key,
    })
    if not data or data.get("status") != "OK":
        status = data.get("status") if data else "no response"
        print(f"[google] Geocoding failed: {status}")
        return None
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def _nearby_page(lat: float, lon: float, place_type: str, api_key: str, page_token: str = None) -> dict:
    """One page of Nearby Search results using rankby=distance (no radius)."""
    params = {
        "location": f"{lat},{lon}",
        "rankby": "distance",
        "type": place_type,
        "key": api_key,
    }
    if page_token:
        params["pagetoken"] = page_token
    return _get(NEARBY_URL, params) or {}


def _text_page(lat: float, lon: float, radius_m: int, keyword: str, api_key: str, page_token: str = None) -> dict:
    """One page of Text Search results."""
    params = {
        "query": keyword,
        "location": f"{lat},{lon}",
        "radius": radius_m,
        "key": api_key,
    }
    if page_token:
        params["pagetoken"] = page_token
    return _get(TEXTSEARCH_URL, params) or {}


def _place_details(place_id: str, api_key: str) -> dict:
    data = _get(DETAILS_URL, {
        "place_id": place_id,
        "fields": DETAILS_FIELDS,
        "key": api_key,
    })
    if data and data.get("status") == "OK":
        return data.get("result", {})
    return {}


def _parse_place(details: dict, place_id: str) -> Optional[dict]:
    """Convert a Google Place Details result to our standard business dict."""
    name = details.get("name", "").strip()
    if not name:
        return None

    if details.get("business_status") == "PERMANENTLY_CLOSED":
        return None

    types = details.get("types", [])
    skip_types = {
        "route", "geocode", "political", "locality", "country",
        "administrative_area_level_1", "administrative_area_level_2",
        "postal_code", "street_address",
    }
    if set(types).issubset(skip_types):
        return None

    category = next(
        (t.replace("_", " ") for t in types
         if t not in skip_types and t != "point_of_interest" and t != "establishment"),
        "business"
    )

    phone = (
        details.get("formatted_phone_number")
        or details.get("international_phone_number")
        or ""
    )
    address = details.get("formatted_address", "")
    hours_data = details.get("opening_hours", {})
    hours = "; ".join(hours_data.get("weekday_text", [])) if hours_data else ""
    desc = details.get("editorial_summary", {}).get("overview", "")

    return {
        "id": f"google_{place_id}",
        "name": name,
        "category": category,
        "phone": phone,
        "email": "",
        "address": address,
        "hours": hours,
        "lat": None,
        "lon": None,
        "description": desc,
        "status": "not_contacted",
        "outreach": [],
        "notes": "",
        "source": "google_places",
    }


def _collect_candidates(lat: float, lon: float, radius_m: int, api_key: str) -> list:
    """
    Collect place_ids of candidate businesses (no website visible in basic result).
    Uses two strategies:
      1. Nearby Search with rankby=distance for each place type
      2. Text Search with local-business keywords
    """
    seen_ids = set()
    candidates = []

    # Strategy 1: Nearby Search by type (rankby=distance finds local shops first)
    for place_type in NEARBY_TYPES:
        if len(candidates) >= MAX_CANDIDATES:
            break
        page_token = None
        pages = 0
        while pages < 3:  # up to 60 results per type
            data = _nearby_page(lat, lon, place_type, api_key, page_token)
            for place in data.get("results", []):
                pid = place.get("place_id")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                candidates.append(pid)

            page_token = data.get("next_page_token")
            pages += 1
            if not page_token:
                break
            time.sleep(2)

    print(f"[google]   {len(candidates)} candidates after type search")

    # Strategy 2: Text Search with local-business keywords
    for keyword in TEXT_KEYWORDS:
        if len(candidates) >= MAX_CANDIDATES:
            break
        page_token = None
        pages = 0
        while pages < 2:
            data = _text_page(lat, lon, radius_m, keyword, api_key, page_token)
            for place in data.get("results", []):
                pid = place.get("place_id")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                candidates.append(pid)

            page_token = data.get("next_page_token")
            pages += 1
            if not page_token:
                break
            time.sleep(2)

    print(f"[google]   {len(candidates)} total candidates after keyword search")
    return candidates[:MAX_CANDIDATES]


def search_businesses(city: str, state: str, country: str, radius_m: int, api_key: str) -> list:
    """
    Search Google Places for local businesses without websites near the given city.
    Returns a list of business dicts sorted with phone-bearing entries first.
    """
    coords = geocode_city(city, state, country, api_key)
    if not coords:
        raise RuntimeError(f"Google geocoding failed for '{city}, {state}'")

    lat, lon = coords
    print(f"[google] Geocoded '{city}' -> ({lat:.4f}, {lon:.4f})")
    print(f"[google] Collecting candidates (radius={radius_m}m)...")

    candidates = _collect_candidates(lat, lon, radius_m, api_key)
    print(f"[google] Fetching details for {len(candidates)} candidates...")

    businesses = []
    seen_names = set()
    no_website_count = 0

    for i, place_id in enumerate(candidates):
        details = _place_details(place_id, api_key)
        if not details:
            continue

        # Skip if they have a website
        if details.get("website"):
            continue

        no_website_count += 1
        biz = _parse_place(details, place_id)
        if biz is None:
            continue

        key = biz["name"].lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        businesses.append(biz)

        if (i + 1) % 20 == 0:
            print(f"[google]   ...{i+1}/{len(candidates)} processed, {len(businesses)} without websites")

        time.sleep(0.1)

    businesses.sort(key=lambda b: (0 if b["phone"] else 1, b["name"]))

    pct = (no_website_count * 100 // len(candidates)) if candidates else 0
    print(f"[google] Done - {len(businesses)} unique businesses without websites "
          f"({pct}% of {len(candidates)} candidates lacked a website).")
    return businesses
