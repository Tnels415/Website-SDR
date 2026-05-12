"""
Enrichment layer: use DuckDuckGo (no API key required) to find
email addresses, phone numbers, and a brief description for each business.
"""

import re
import time
from typing import Optional

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

JUNK_EMAIL_DOMAINS = {
    "example.com", "sentry.io", "wix.com", "squarespace.com",
    "wordpress.com", "godaddy.com", "domain.com", "yourcompany.com",
    "email.com", "test.com", "placeholder.com",
}

# Stop enrichment after this many consecutive DDG failures
_MAX_CONSECUTIVE_FAILURES = 3
try:
    from ddgs import DDGS
    _ddg_available = True
except ImportError:
    _ddg_available = False


def _clean_email(raw: str) -> Optional[str]:
    email = raw.lower().strip()
    domain = email.split("@")[-1]
    if domain in JUNK_EMAIL_DOMAINS:
        return None
    if domain.endswith(".png") or domain.endswith(".jpg"):
        return None
    return email


def _extract_emails_from_text(text: str) -> list[str]:
    found = EMAIL_RE.findall(text)
    cleaned = []
    for e in found:
        c = _clean_email(e)
        if c and c not in cleaned:
            cleaned.append(c)
    return cleaned


def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Run a DuckDuckGo text search; return list of result dicts."""
    if not _ddg_available:
        return []
    try:
        return DDGS().text(query, max_results=max_results)
    except Exception:
        return []


def enrich_businesses(businesses: list[dict], city: str, state: str) -> list[dict]:
    """
    Enrich businesses with email and description via DuckDuckGo.
    Bails out early if DDG is consistently unavailable to avoid log spam.
    """
    if not _ddg_available:
        print("[enrich] ddgs is not installed — skipping enrichment.")
        print("         Run:  pip3 install ddgs")
        return businesses

    consecutive_failures = 0
    location = f"{city}, {state}"

    for i, biz in enumerate(businesses):
        if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
            print(
                f"[enrich] DuckDuckGo unavailable after {_MAX_CONSECUTIVE_FAILURES} "
                "consecutive failures — skipping remaining enrichment."
            )
            break

        name = biz["name"]
        print(f"[enrich] ({i+1}/{len(businesses)}) {name} …")
        got_result = False

        # --- Email ---
        if not biz.get("email"):
            for q in [
                f'"{name}" {location} email contact',
                f'"{name}" {location} phone email',
            ]:
                results = _ddg_search(q, max_results=5)
                if results:
                    got_result = True
                    for r in results:
                        emails = _extract_emails_from_text(
                            r.get("title", "") + " " + r.get("body", "")
                        )
                        if emails:
                            biz["email"] = emails[0]
                            break
                if biz.get("email"):
                    break
                time.sleep(0.4)

        # --- Description ---
        if not biz.get("description"):
            results = _ddg_search(f'"{name}" {location}', max_results=3)
            if results:
                got_result = True
                snippet = results[0].get("body", "")
                if snippet:
                    sentences = re.split(r"(?<=[.!?])\s+", snippet)
                    biz["description"] = " ".join(sentences[:2])[:300]

        if got_result:
            consecutive_failures = 0
        else:
            consecutive_failures += 1

        time.sleep(0.3)

    # --- Phone numbers (dedicated lookup pass) ---
    from phone_lookup import enrich_phones
    businesses = enrich_phones(businesses, city, state)

    return businesses
