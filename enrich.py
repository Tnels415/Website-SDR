"""
Enrichment layer: use DuckDuckGo (no API key required) to find
email addresses and a brief description for each business.
"""

import re
import time
from typing import Optional

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Domains we want to ignore when extracting emails
JUNK_EMAIL_DOMAINS = {
    "example.com", "sentry.io", "wix.com", "squarespace.com",
    "wordpress.com", "godaddy.com", "domain.com", "yourcompany.com",
    "email.com", "test.com", "placeholder.com",
}

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


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
    if not DDGS_AVAILABLE:
        return []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        print(f"[enrich] DDG search failed for '{query}': {e}")
        return []


def enrich_business(biz: dict, city: str, state: str) -> dict:
    """
    Attempt to find email and description for a business via web search.
    Modifies the business dict in-place and returns it.
    """
    if not DDGS_AVAILABLE:
        return biz

    name = biz["name"]
    location = f"{city}, {state}"
    print(f"[enrich] {name} …")

    # --- Try to find an email address ---
    if not biz.get("email"):
        queries = [
            f'"{name}" {location} email contact',
            f'"{name}" {location} phone email',
        ]
        for q in queries:
            results = _ddg_search(q, max_results=5)
            for r in results:
                combined = (r.get("title", "") + " " + r.get("body", ""))
                emails = _extract_emails_from_text(combined)
                if emails:
                    biz["email"] = emails[0]
                    break
            if biz.get("email"):
                break
            time.sleep(0.4)   # polite delay

    # --- Build a short description if we don't have one ---
    if not biz.get("description"):
        results = _ddg_search(f'"{name}" {location}', max_results=3)
        if results:
            snippet = results[0].get("body", "")
            if snippet:
                # Trim to a couple of sentences
                sentences = re.split(r"(?<=[.!?])\s+", snippet)
                biz["description"] = " ".join(sentences[:2])[:300]

    time.sleep(0.3)
    return biz


def enrich_businesses(businesses: list[dict], city: str, state: str) -> list[dict]:
    """Enrich a list of businesses, skipping those already enriched."""
    if not DDGS_AVAILABLE:
        print(
            "[enrich] duckduckgo-search is not installed — skipping enrichment.\n"
            "         Run:  pip install duckduckgo-search"
        )
        return businesses

    for i, biz in enumerate(businesses):
        print(f"[enrich] ({i+1}/{len(businesses)}) {biz['name']}")
        enrich_business(biz, city, state)

    return businesses
