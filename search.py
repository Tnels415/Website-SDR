"""
Overpass API (OpenStreetMap) search for local businesses without websites.
"""

import requests
import time
from typing import Optional

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# OSM tags that indicate a real commercial/service business
BUSINESS_TAGS = [
    "amenity", "shop", "office", "craft", "tourism",
    "leisure", "healthcare", "professional",
]

# Values we want to skip (non-commercial)
SKIP_AMENITY = {
    "parking", "bicycle_parking", "bench", "waste_basket", "recycling",
    "post_box", "telephone", "toilets", "drinking_water", "fountain",
    "shelter", "clock", "atm", "vending_machine", "charging_station",
    "bus_station", "taxi", "ferry_terminal", "fuel",
}


def geocode_city(city: str, state: str, country: str) -> Optional[tuple[float, float]]:
    """Return (lat, lon) for a city, trying multiple geocoders."""
    query = f"{city}, {state}, {country}"
    headers = {"User-Agent": "LocalBusinessDiscoveryAgent/1.0 (business-finder)"}

    # 1. Photon (Komoot) — permissive, no auth needed
    try:
        resp = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 1},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if features:
            lon, lat = features[0]["geometry"]["coordinates"]
            print(f"[search] Geocoded via Photon")
            return float(lat), float(lon)
    except Exception as e:
        print(f"[search] Photon geocoding failed: {e}")

    # 2. Nominatim fallback
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            print(f"[search] Geocoded via Nominatim")
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"[search] Nominatim geocoding failed: {e}")

    return None


def build_overpass_query(lat: float, lon: float, radius_m: int) -> str:
    """Build an Overpass QL query for named businesses without a website tag."""
    tag_unions = []
    for tag in BUSINESS_TAGS:
        tag_unions.append(
            f'  node["{tag}"]["name"][!"website"](around:{radius_m},{lat},{lon});'
        )
        tag_unions.append(
            f'  way["{tag}"]["name"][!"website"](around:{radius_m},{lat},{lon});'
        )

    query_body = "\n".join(tag_unions)
    return f"""[out:json][timeout:60];
(
{query_body}
);
out body center;"""


def parse_business(element: dict) -> Optional[dict]:
    """Extract relevant fields from an OSM element."""
    tags = element.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    # Determine category
    category = None
    for tag in BUSINESS_TAGS:
        if tag in tags:
            category = tags[tag]
            break

    # Skip non-commercial amenity values
    if tags.get("amenity") in SKIP_AMENITY:
        return None

    # Get coordinates
    if element["type"] == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    phone = (
        tags.get("phone")
        or tags.get("contact:phone")
        or tags.get("telephone")
    )
    email = (
        tags.get("email")
        or tags.get("contact:email")
    )
    address_parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:city", ""),
        tags.get("addr:state", ""),
        tags.get("addr:postcode", ""),
    ]
    address = " ".join(p for p in address_parts if p).strip()
    hours = tags.get("opening_hours", "")

    return {
        "id": f"osm_{element['type']}_{element['id']}",
        "name": name,
        "category": category or "business",
        "phone": phone or "",
        "email": email or "",
        "address": address,
        "hours": hours,
        "lat": lat,
        "lon": lon,
        "description": "",
        "status": "not_contacted",
        "outreach": [],
        "notes": "",
        "source": "openstreetmap",
    }


def search_businesses(city: str, state: str, country: str, radius_m: int) -> list[dict]:
    """
    Search for businesses without websites near the given city.
    Returns a list of business dicts sorted by those that have phone numbers first.
    """
    coords = geocode_city(city, state, country)
    if not coords:
        raise RuntimeError(f"Could not geocode '{city}, {state}'")

    lat, lon = coords
    print(f"[search] Geocoded '{city}' → ({lat:.4f}, {lon:.4f})")

    query = build_overpass_query(lat, lon, radius_m)
    print(f"[search] Querying Overpass API (radius={radius_m}m)…")

    resp = None
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = requests.post(
                endpoint,
                data=f"data={requests.utils.quote(query)}",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "LocalBusinessDiscoveryAgent/1.0",
                },
                timeout=90,
            )
            resp.raise_for_status()
            print(f"[search] Using Overpass endpoint: {endpoint}")
            break
        except requests.exceptions.Timeout:
            last_error = "timed out"
            print(f"[search] {endpoint} timed out, trying next…")
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            print(f"[search] {endpoint} failed ({e}), trying next…")
            resp = None

    if resp is None:
        raise RuntimeError(f"All Overpass endpoints failed. Last error: {last_error}")

    elements = resp.json().get("elements", [])
    print(f"[search] Raw elements returned: {len(elements)}")

    businesses = []
    seen_names = set()
    for el in elements:
        biz = parse_business(el)
        if biz is None:
            continue
        # Deduplicate by name (keep first occurrence)
        key = biz["name"].lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        businesses.append(biz)

    # Prioritise businesses that already have a phone number
    businesses.sort(key=lambda b: (0 if b["phone"] else 1, b["name"]))

    print(f"[search] Unique businesses found: {len(businesses)}")
    return businesses
