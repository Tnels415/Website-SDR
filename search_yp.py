# -*- coding: utf-8 -*-
"""
Yellow Pages scraping backend.
Finds local businesses that have NO website listed on Yellow Pages.
The presence/absence of the "Visit Website" link on each listing card
is a reliable indicator - businesses without a link are prime prospects.

No API key or signup required.
Dependencies: requests, beautifulsoup4 (both already in requirements.txt)
"""

import re
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

YP_BASE_URL = "https://www.yellowpages.com/search"

YP_CATEGORIES = [
    "restaurants", "hair salons", "auto repair", "plumbers",
    "electricians", "dentists", "nail salons", "barbers",
    "dry cleaners", "florists", "pet grooming", "landscaping",
    "photographers", "caterers", "accountants", "insurance agents",
    "lawyers", "chiropractors", "massage therapy", "gyms",
    "bakeries", "laundry", "alterations", "handyman",
    "painting contractors", "roofing contractors",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.yellowpages.com/",
}

PHONE_RE = re.compile(
    r'(?:\+?1[-.\s]?)?'
    r'\(?\d{3}\)?'
    r'[-.\s]\d{3}[-.\s]\d{4}'
)

MAX_BUSINESSES = 100
MAX_PAGES_PER_CATEGORY = 5


def _normalise_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return "(%s) %s-%s" % (digits[:3], digits[3:6], digits[6:])


def _id_for(name: str, city: str) -> str:
    slug_name = re.sub(r"\W+", "_", name.lower()).strip("_")
    slug_city = city.lower().replace(" ", "_")
    return "yp_%s_%s" % (slug_name, slug_city)


def _fetch_page(category: str, city: str, state: str, page: int, session: requests.Session) -> Optional[BeautifulSoup]:
    time.sleep(random.uniform(1.5, 2.5))
    params = {
        "search_terms": category,
        "geo_location_terms": "%s, %s" % (city, state),
    }
    if page > 1:
        params["page"] = str(page)
    try:
        resp = session.get(YP_BASE_URL, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print("[yp]   HTTP %d for category '%s' page %d" % (resp.status_code, category, page))
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print("[yp]   Request failed: %s" % e)
        return None


def _parse_card(card, city: str) -> Optional[dict]:
    # Skip businesses that already have a website listed
    if card.find("a", class_="track-visit-website"):
        return None

    name_tag = card.find("a", class_="business-name")
    if not name_tag:
        return None
    name = name_tag.get_text(strip=True)
    if not name:
        return None

    # Phone number
    phone = ""
    phone_div = card.find("div", class_="phones")
    if phone_div:
        raw = phone_div.get_text(strip=True)
        phone = _normalise_phone(raw) or ""

    # Address
    address = ""
    adr = card.find("p", class_="adr")
    if adr:
        street = adr.find("span", class_="street-address")
        locality = adr.find("span", class_="locality")
        parts = []
        if street:
            parts.append(street.get_text(strip=True))
        if locality:
            parts.append(locality.get_text(strip=True))
        address = ", ".join(parts)

    # Category
    category = ""
    cats_div = card.find("div", class_="categories")
    if cats_div:
        first_cat = cats_div.find("a")
        if first_cat:
            category = first_cat.get_text(strip=True)

    return {
        "id": _id_for(name, city),
        "name": name,
        "category": category,
        "phone": phone,
        "email": "",
        "address": address,
        "hours": "",
        "lat": None,
        "lon": None,
        "description": "",
        "status": "not_contacted",
        "outreach": [],
        "notes": "",
        "source": "yellowpages",
    }


def search_businesses(city: str, state: str, country: str, radius_m: int) -> list:
    """
    Scrape Yellow Pages for local businesses without a website listing.
    Returns a list of business dicts sorted with phone-bearing entries first.
    radius_m is accepted for interface compatibility but not used (YP searches by city).
    """
    print("[yp] Searching Yellow Pages for businesses in %s, %s..." % (city, state))

    session = requests.Session()
    businesses = []
    seen_names: set = set()
    total_cards_checked = 0
    total_skipped_website = 0

    for cat in YP_CATEGORIES:
        if len(businesses) >= MAX_BUSINESSES:
            break

        cat_new = 0
        for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
            soup = _fetch_page(cat, city, state, page, session)
            if soup is None:
                break

            cards = soup.find_all("div", class_="result")
            if not cards:
                break

            page_new = 0
            for card in cards:
                total_cards_checked += 1
                # Check for website before parsing (fast path)
                if card.find("a", class_="track-visit-website"):
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
                cat_new += 1
                page_new += 1

            if page_new == 0:
                break  # no new results on this page, stop paginating this category

        if cat_new > 0:
            print("[yp]   %s: %d businesses without websites" % (cat, cat_new))

    businesses.sort(key=lambda b: (0 if b["phone"] else 1, b["name"]))

    pct_no_site = (
        (len(businesses) * 100 // total_cards_checked) if total_cards_checked else 0
    )
    print(
        "[yp] Done - %d businesses without websites found "
        "(%d of %d listings had no website, %d skipped for having one)."
        % (len(businesses), len(businesses), total_cards_checked, total_skipped_website)
    )
    return businesses
