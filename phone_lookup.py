"""
Phone number enrichment: find a phone number for a business using DuckDuckGo
snippet extraction and directory page scraping (Yellow Pages / Yelp).
No API key required.
"""

import re
import time
from typing import Optional

PHONE_RE = re.compile(
    r'(?:\+?1[-.\s]?)?'       # optional country code
    r'\(?\d{3}\)?'             # area code
    r'[-.\s]\d{3}[-.\s]\d{4}' # local number
)

# Directory domains worth fetching directly for phone numbers
DIRECTORY_DOMAINS = ("yellowpages.com", "yelp.com", "bbb.org", "manta.com", "superpages.com")

# Stop after this many consecutive businesses with no phone found
_MAX_CONSECUTIVE_MISSES = 3

try:
    from ddgs import DDGS
    _ddg_ok = True
except ImportError:
    _ddg_ok = False

try:
    from bs4 import BeautifulSoup
    _bs4_ok = True
except ImportError:
    _bs4_ok = False


def _normalise(raw: str) -> Optional[str]:
    """Strip to digits, validate 10-digit US number, return formatted string."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _phones_from_text(text: str) -> list[str]:
    """Extract and normalise all phone numbers found in a block of text."""
    results = []
    for match in PHONE_RE.findall(text):
        normed = _normalise(match)
        if normed and normed not in results:
            results.append(normed)
    return results


def _ddg_search(query: str) -> list[dict]:
    if not _ddg_ok:
        return []
    try:
        return DDGS().text(query, max_results=6)
    except Exception:
        return []


def _scrape_phone_from_url(url: str) -> Optional[str]:
    """Fetch a directory page and extract the first phone number found."""
    if not _bs4_ok:
        return None
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script/style noise
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        phones = _phones_from_text(text)
        return phones[0] if phones else None
    except Exception:
        return None


def lookup_phone(name: str, city: str, state: str) -> Optional[str]:
    """
    Try to find a phone number for a business.
    Returns a normalised '(XXX) XXX-XXXX' string, or None if not found.
    """
    query = f'"{name}" {city} {state} phone number'
    results = _ddg_search(query)

    # Strategy 1: extract phones directly from DDG snippets
    for r in results:
        text = (r.get("title", "") + " " + r.get("body", ""))
        phones = _phones_from_text(text)
        if phones:
            return phones[0]

    # Strategy 2: fetch a directory URL found in the results
    for r in results:
        url = r.get("href", "") or r.get("url", "")
        if any(domain in url for domain in DIRECTORY_DOMAINS):
            phone = _scrape_phone_from_url(url)
            if phone:
                return phone

    return None


def enrich_phones(businesses: list[dict], city: str, state: str) -> list[dict]:
    """
    Fill in missing phone numbers for each business in the list.
    Skips businesses that already have a phone. Bails out early after
    several consecutive failures to avoid log spam when DDG is unavailable.
    """
    if not _ddg_ok:
        print("[phone] ddgs not installed — skipping phone enrichment.")
        return businesses

    need_phone = [b for b in businesses if not b.get("phone")]
    if not need_phone:
        print("[phone] All businesses already have phone numbers.")
        return businesses

    print(f"[phone] Looking up phones for {len(need_phone)} businesses…")
    consecutive_misses = 0

    for biz in need_phone:
        if consecutive_misses >= _MAX_CONSECUTIVE_MISSES:
            print(
                f"[phone] {_MAX_CONSECUTIVE_MISSES} consecutive misses — "
                "DDG may be rate-limiting. Stopping phone lookup."
            )
            break

        name = biz["name"]
        phone = lookup_phone(name, city, state)
        if phone:
            biz["phone"] = phone
            consecutive_misses = 0
            print(f"[phone]   ✓ {name}: {phone}")
        else:
            consecutive_misses += 1
            print(f"[phone]   – {name}: not found")

        time.sleep(0.5)

    return businesses
