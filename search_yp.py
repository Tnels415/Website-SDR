# -*- coding: utf-8 -*-
"""
Manta.com scraping backend.
Finds local businesses that have no website using Manta's small-business directory.
Manta is server-side rendered and specifically tracks businesses without websites.

No API key or signup required.
Dependencies: requests, beautifulsoup4 (both already in requirements.txt)
"""

import re
import random
import time
from typing import Optional

import requests

try:
    from bs4 import BeautifulSoup
    _bs4_ok = True
except ImportError:
    _bs4_ok = False

MANTA_SEARCH = "https://www.manta.com/search"

BUSINESS_TYPES = [
    "restaurants", "hair salon", "nail salon", "barber",
    "auto repair", "plumber", "electrician", "dentist",
    "chiropractor", "massage", "florist", "pet grooming",
    "landscaping", "cleaning service", "catering",
    "accountant", "insurance agent", "lawyer",
    "gym", "bakery", "dry cleaning", "handyman",
    "real estate", "photographer", "auto body",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.manta.com/",
}

PHONE_RE = re.compile(
    r'(?:\+?1[-.\s]?)?'
    r'\(?\d{3}\)?'
    r'[-.\s]\d{3}[-.\s]\d{4}'
)

MAX_BUSINESSES = 100
MAX_PAGES_PER_TYPE = 4


def _normalise_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return "(%s) %s-%s" % (digits[:3], digits[3:6], digits[6:])


def _id_for(name: str, city: str) -> str:
    slug = re.sub(r"\W+", "_", name.lower()).strip("_")
    city_slug = city.lower().replace(" ", "_")
    return "yp_%s_%s" % (slug, city_slug)


def _fetch_page(session: requests.Session, btype: str, city: str, state: str, page: int) -> Optional[BeautifulSoup]:
    time.sleep(random.uniform(1.5, 2.5))
    params = {
        "search_source": "nav",
        "search[name]": btype,
        "search[location]": "%s, %s" % (city, state),
    }
    if page > 1:
        params["page"] = str(page)
    try:
        resp = session.get(MANTA_SEARCH, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print("[manta]   HTTP %d for '%s' page %d" % (resp.status_code, btype, page))
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print("[manta]   Request failed: %s" % e)
        return None


def _has_website(card: BeautifulSoup) -> bool:
    """Return True if the card contains a link to the business's own website."""
    for a in card.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "manta.com" not in href:
            return True
    return False


def _parse_card(card: BeautifulSoup, city: str) -> Optional[dict]:
    # Skip businesses that have their own website linked in the card
    if _has_website(card):
        return None

    # Business name — try several heading/link patterns
    name = ""
    for selector in [
        lambda c: c.find("h2"),
        lambda c: c.find("h3"),
        lambda c: c.find("a", class_=lambda x: x and "name" in x.lower()),
        lambda c: c.find("strong"),
    ]:
        tag = selector(card)
        if tag:
            name = tag.get_text(strip=True)
            if name:
                break
    if not name:
        return None

    # Phone — prefer tel: href links (most reliable)
    phone = ""
    tel = card.find("a", href=lambda h: h and h.startswith("tel:"))
    if tel:
        raw = tel["href"].replace("tel:", "").replace("%20", "").strip()
        phone = _normalise_phone(raw) or ""
    if not phone:
        text = card.get_text(" ", strip=True)
        for match in PHONE_RE.findall(text):
            phone = _normalise_phone(match) or ""
            if phone:
                break

    # Address
    address = ""
    addr_tag = card.find("address")
    if addr_tag:
        address = addr_tag.get_text(", ", strip=True)
    if not address:
        # Look for a div/span containing the city name as a fallback
        for tag in card.find_all(["span", "div", "p"]):
            txt = tag.get_text(strip=True)
            if city.lower() in txt.lower() and len(txt) < 120:
                address = txt
                break

    # Category — first non-empty link text that isn't the business name
    category = ""
    for a in card.find_all("a", href=True):
        txt = a.get_text(strip=True)
        if txt and txt != name and len(txt) < 40:
            category = txt
            break

    return {
        "id": _id_for(name, city),
        "name": name,
        "category": category or "business",
        "phone": phone,
        "email": "",
        "address": address or city,
        "hours": "",
        "lat": None,
        "lon": None,
        "description": "",
        "status": "not_contacted",
        "outreach": [],
        "notes": "",
        "source": "manta",
    }


def _find_cards(soup: BeautifulSoup) -> list:
    """Try several common card container selectors."""
    for selector, kwargs in [
        ("article", {}),
        ("div", {"class_": lambda c: c and "result" in c.lower()}),
        ("li", {"class_": lambda c: c and "listing" in c.lower()}),
        ("div", {"class_": lambda c: c and "card" in c.lower()}),
        ("section", {"class_": lambda c: c and "business" in c.lower()}),
    ]:
        cards = soup.find_all(selector, **kwargs)
        if cards:
            return cards
    return []


def search_businesses(city: str, state: str, country: str, radius_m: int) -> list:
    """
    Scrape Manta.com for local businesses without a website.
    radius_m is accepted for interface compatibility but not used (Manta searches by city).
    Returns a list of business dicts sorted with phone-bearing entries first.
    """
    if not _bs4_ok:
        print("[manta] beautifulsoup4 is not installed.")
        print("[manta] Fix: run  pip3 install beautifulsoup4  then re-run the agent.")
        return []

    print("[manta] Searching Manta.com for businesses in %s, %s..." % (city, state))

    session = requests.Session()
    businesses = []
    seen_names: set = set()
    total_checked = 0
    total_skipped_website = 0

    for btype in BUSINESS_TYPES:
        if len(businesses) >= MAX_BUSINESSES:
            break

        btype_new = 0
        for page in range(1, MAX_PAGES_PER_TYPE + 1):
            soup = _fetch_page(session, btype, city, state, page)
            if soup is None:
                break

            cards = _find_cards(soup)
            if not cards:
                print("[manta]   No cards found for '%s' page %d (HTML may have changed)" % (btype, page))
                break

            page_new = 0
            for card in cards:
                total_checked += 1
                if _has_website(card):
                    total_skipped_website += 1
                    continue

                biz = _parse_card(card, city)
                if biz is None:
                    continue

                key = biz["name"].lower()
                if key in seen_names:
                    continue
                seen_names.add(key)
                businesses.append(biz)
                btype_new += 1
                page_new += 1

            if page_new == 0:
                break

        if btype_new > 0:
            print("[manta]   %s: %d businesses without websites" % (btype, btype_new))

    businesses.sort(key=lambda b: (0 if b["phone"] else 1, b["name"]))
    print(
        "[manta] Done - %d businesses found "
        "(%d cards checked, %d had websites)."
        % (len(businesses), total_checked, total_skipped_website)
    )
    return businesses
