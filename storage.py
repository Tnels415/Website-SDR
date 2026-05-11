"""
JSON file persistence for the business list.
Merges new results with existing data so outreach notes are never lost.
"""

import json
import os
from datetime import datetime


def load_businesses(filepath: str) -> dict[str, dict]:
    """Load existing businesses keyed by their id."""
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Support both list format and dict-keyed format
    if isinstance(data, list):
        return {b["id"]: b for b in data}
    return data


def merge_businesses(existing: dict[str, dict], new_list: list[dict]) -> dict[str, dict]:
    """
    Merge newly discovered businesses into the existing dataset.
    Existing entries keep their status, outreach history, and notes.
    New fields (email, description, etc.) are back-filled if missing.
    """
    merged = dict(existing)
    added = 0
    updated = 0

    for biz in new_list:
        bid = biz["id"]
        if bid in merged:
            # Back-fill enriched fields only — never overwrite user data
            for field in ("email", "description", "phone", "address", "hours", "category"):
                if not merged[bid].get(field) and biz.get(field):
                    merged[bid][field] = biz[field]
                    updated += 1
        else:
            merged[bid] = biz
            added += 1

    print(f"[storage] {added} new businesses added, {updated} fields updated.")
    return merged


def save_businesses(businesses: dict[str, dict], filepath: str) -> None:
    """Save the business dict to disk as a JSON list."""
    data = list(businesses.values())
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[storage] Saved {len(data)} businesses → {filepath}")


def businesses_to_list(businesses: dict[str, dict]) -> list[dict]:
    return list(businesses.values())
