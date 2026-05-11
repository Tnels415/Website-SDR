"""
Local Business Discovery Agent
--------------------------------
Uses the Claude API (tool-use agentic loop) to:
  1. Search OpenStreetMap for local businesses that have no website
  2. Enrich each result with email / description via DuckDuckGo
  3. Merge with existing data (preserving your notes & outreach history)
  4. Generate dashboard.html — an interactive tracker you open in your browser

Usage:
    python agent.py

Requirements:
    pip install anthropic requests duckduckgo-search
    export ANTHROPIC_API_KEY=sk-...
"""

import json
import os
import sys

import anthropic

import config
from dashboard import generate_dashboard
from enrich import enrich_businesses
from search import search_businesses
from storage import load_businesses, merge_businesses, save_businesses


# ── Tool definitions ────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_local_businesses",
        "description": (
            "Search OpenStreetMap for local businesses in the configured city "
            "that do NOT have a website listed. Returns a JSON array of business objects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "radius_m": {
                    "type": "integer",
                    "description": "Search radius in meters around the city centre.",
                    "default": 10000,
                }
            },
        },
    },
    {
        "name": "enrich_businesses",
        "description": (
            "Use DuckDuckGo to find email addresses and short descriptions for "
            "a list of businesses. Pass the full list returned by search_local_businesses."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "businesses": {
                    "type": "array",
                    "description": "The list of business objects to enrich.",
                }
            },
            "required": ["businesses"],
        },
    },
    {
        "name": "save_and_generate_dashboard",
        "description": (
            "Merge new businesses with any existing data, save to businesses.json, "
            "and regenerate dashboard.html. Always call this as the final step."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "businesses": {
                    "type": "array",
                    "description": "The enriched list of business objects.",
                }
            },
            "required": ["businesses"],
        },
    },
]


# ── Tool handlers ────────────────────────────────────────────────────────────

def handle_search(radius_m: int) -> str:
    results = search_businesses(
        config.SEARCH_CITY,
        config.SEARCH_STATE,
        config.SEARCH_COUNTRY,
        radius_m,
    )
    return json.dumps(results)


def handle_enrich(businesses: list) -> str:
    enriched = enrich_businesses(businesses, config.SEARCH_CITY, config.SEARCH_STATE)
    return json.dumps(enriched)


def handle_save(businesses: list) -> str:
    existing = load_businesses(config.DATA_FILE)
    merged = merge_businesses(existing, businesses)
    save_businesses(merged, config.DATA_FILE)
    biz_list = list(merged.values())
    generate_dashboard(biz_list, config.DASHBOARD_FILE, config.SEARCH_CITY, config.SEARCH_STATE)
    return json.dumps({"saved": len(merged), "dashboard": config.DASHBOARD_FILE})


TOOL_HANDLERS = {
    "search_local_businesses": lambda inp: handle_search(
        inp.get("radius_m", config.SEARCH_RADIUS_M)
    ),
    "enrich_businesses": lambda inp: handle_enrich(inp["businesses"]),
    "save_and_generate_dashboard": lambda inp: handle_save(inp["businesses"]),
}


# ── Agent loop ───────────────────────────────────────────────────────────────

def run_agent() -> None:
    api_key = config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: No Anthropic API key found.\n"
            "Set the ANTHROPIC_API_KEY environment variable or edit config.py."
        )

    if config.SEARCH_CITY.startswith("YOUR_"):
        sys.exit(
            "ERROR: Please set SEARCH_CITY and SEARCH_STATE in config.py before running."
        )

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = (
        f"You are a local-business discovery agent.\n"
        f"Your goal: find at least {config.MIN_BUSINESSES} local businesses in "
        f"{config.SEARCH_CITY}, {config.SEARCH_STATE} that have NO website, "
        f"so the user can offer to build one for them.\n\n"
        "Steps you MUST follow in order:\n"
        "1. Call search_local_businesses to get raw results from OpenStreetMap.\n"
        "2. If fewer than 10 businesses were found, call search_local_businesses "
        "   again with a larger radius_m (double it each retry, up to 50 000).\n"
        "3. Call enrich_businesses on the best candidates to find emails & descriptions.\n"
        "4. Call save_and_generate_dashboard with the enriched list.\n"
        "5. Summarise what was found (counts, highlights) in plain text — no code blocks.\n"
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"Find local businesses in {config.SEARCH_CITY}, {config.SEARCH_STATE} "
                f"that don't have a website. I need at least {config.MIN_BUSINESSES}. "
                "Enrich them with emails and descriptions, then save and generate the dashboard."
            ),
        }
    ]

    print(f"\n{'='*60}")
    print(f"  Local Business Discovery Agent")
    print(f"  Location : {config.SEARCH_CITY}, {config.SEARCH_STATE}")
    print(f"  Target   : ≥{config.MIN_BUSINESSES} businesses")
    print(f"{'='*60}\n")

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Print the final text summary
            for block in response.content:
                if hasattr(block, "text"):
                    print("\n" + block.text)
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                print(f"[agent] → calling tool: {tool_name}")

                try:
                    result_str = TOOL_HANDLERS[tool_name](block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )
                except Exception as exc:
                    print(f"[agent] Tool {tool_name} raised: {exc}")
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"ERROR: {exc}",
                            "is_error": True,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason
            print(f"[agent] Unexpected stop_reason: {response.stop_reason}")
            break

    print(f"\nDone!  Open {config.DASHBOARD_FILE} in your browser.\n")


if __name__ == "__main__":
    run_agent()
