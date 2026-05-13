"""
Google Places API search backend.
Finds local businesses that have no website using:
  1. Google Geocoding API  — city name → lat/lon
  2. Google Places Nearby Search — businesses near that location
  3. Google Place Details  — phone, address, hours, website check

Requires: GOOGLE_PLACES_API_KEY in config.py
Cost: well within Google's $200/month free credit for normal use.
"""

import time
import requests
from typing import Optional

GEOCODE_URL    = "https://maps.googleapis.com/maps/api/geocode/json"
NEARBY_URL     = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL    = "https://maps.googleapis.com/maps/api/place/details/json"

# Place types we search for — covers most small local businesses
SEARCH_TYPES = [
    "restaurant", "cafe", "bakery", "bar", "food",
    "beauty_salon", "hair_care", "spa", "gym",
    "car_repair", "car_wash",
    "laundry", "dry_cleaning",
    "florist", "pet_store",
    "accounting", "lawyer", "insurance_agency", "real_estate_agency",
    "dentist", "doctor", "physiotherapist",
    "electrician", "plumber", "painter", "locksmith",
    "clothing_store", "shoe_store", "jewelry_store", "book_store",
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


def _get(url: str, params: dict) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[google] Request failed: {e}")
        return None


def geocode_city(city: str, state: str, country: str, api_key: str) -> Optional[tuple[float, float]]:
    """Return (lat, lon) using Google Geocoding API."""
    data = _get(GEOCODE_URL, {
        "address": f"{city}, {state}, {country}",
        "key": api_key,
    })
    if not data or data.get("status") != "OK":
        print(f"[google] Geocoding failed: {data.get('status') if data else 'no response'}")
        return None
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def _nearby_search(lat: float, lon: float, radius_m: int, place_type: str, api_key: str, page_token: str = None) -> dict:
    params = {
        "location": f"{lat},{lon}",
        "radius": radius_m,
        "type": place_type,
        "key": api_key,
    }
    if page_token:
        params["pagetoken"] = page_token
    return _get(NEARBY_URL, params) or {}


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

    # Skip permanently closed
    if details.get("business_status") == "PERMANENTLY_CLOSED":
        return None

    types = details.get("types", [])
    # Filter out pure infrastructure (routes, geocodes, etc.)
    skip_types = {"route", "geocode", "political", "locality", "country",
                  "administrative_area_level_1", "administrative_area_level_2",
                  "postal_code", "street_address"}
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


def search_businesses(city: str, state: str, country: str, radius_m: int, api_key: str) -> list[dict]:
    """
    Search Google Places for local businesses without websites near the given city.
    Returns a list of business dicts sorted with phone-bearing entries first.
    """
    coords = geocode_city(city, state, country, api_key)
    if not coords:
        raise RuntimeError(f"Google geocoding failed for '{city}, {state}'")

    lat, lon = coords
    print(f"[google] Geocoded '{city}' → ({lat:.4f}, {lon:.4f})")

    seen_ids: set[str] = set()
    candidates: list[dict] = []  # place_ids of businesses with no website in basic result

    for place_type in SEARCH_TYPES:
        page_token = None
        pages = 0
        while pages < 2:  # max 2 pages (40 results) per type
            data = _nearby_search(lat, lon, radius_m, place_type, api_key, page_token)
            results = data.get("results", [])

            for place in results:
                pid = place.get("place_id")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                # Basic result: if website is already present, skip (they have one)
                if place.get("website"):
                    continue
                candidates.append(pid)

            page_token = data.get("next_page_token")
            pages += 1
            if not page_token:
                break
            time.sleep(2)  # Google requires a short delay before using next_page_token

        if len(candidates) >= 100:
            break  # plenty to work with

    print(f"[google] {len(candidates)} candidate businesses found — fetching details…")

    businesses: list[dict] = []
    seen_names: set[str] = set()

    for i, place_id in enumerate(candidates):
        details = _place_details(place_id, api_key)
        if not details:
            continue

        # Skip if they DO have a website (double-check in details)
        if details.get("website"):
            continue

        biz = _parse_place(details, place_id)
        if biz is None:
            continue

        # Deduplicate by name
        key = biz["name"].lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        businesses.append(biz)

        if (i + 1) % 10 == 0:
            print(f"[google]   …{i+1}/{len(candidates)} processed, {len(businesses)} kept so far")

        time.sleep(0.1)  # polite rate limiting

    # Sort: phone first, then alphabetical
    businesses.sort(key=lambda b: (0 if b["phone"] else 1, b["name"]))

    print(f"[google] Done — {len(businesses)} businesses without websites found.")
    return businesses
