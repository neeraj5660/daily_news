"""
generate_llm_sections.py — fills manual_sections.json with the sections
fetch_data.py's own docstring says it can't get for free: FII/DII, the
Pre-Market Momentum Radar, insider/smart-money activity, the IPO/earnings/
macro calendar, and geopolitical items.

PIPELINE ORDER (see .github/workflows/daily-india-briefing.yml):
    1. python generate_llm_sections.py   <- this script, writes manual_sections.json
    2. python fetch_data.py              <- unchanged, reads manual_sections.json,
                                             merges it with free yfinance/RSS data,
                                             writes the final data.json

SCHEMA NOTE (read this before trusting the output):
    fetch_data.py only tells us the *keys* it merges in (market, radar,
    insider, calendar, geo) — it doesn't tell us the shape your site's
    JS expects *inside* each one. The shapes below are a reasonable
    inference from the one object we do have a confirmed shape for
    (`hero`, which uses confidence/confidence_note/headline/lede).
    If your site's rendering code expects different field names, the
    fix is localised: adjust the JSON_SCHEMA description in the system
    prompt below, and this script's output will follow it exactly next
    run — no need to touch fetch_data.py or the site itself.

Requires:
    pip install -r requirements.txt
    env var ANTHROPIC_API_KEY set (GitHub Actions secret in CI)

Run manually to test:
    ANTHROPIC_API_KEY=sk-... python generate_llm_sections.py
"""

import os
import sys
import json
import datetime
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 6000
MANUAL_FILE = Path(__file__).parent / "manual_sections.json"

JSON_SCHEMA_DESCRIPTION = """
Return ONLY a single JSON object, no prose before or after it, matching
exactly this shape:

{
  "market": {
    "fii_dii": {
      "date": "YYYY-MM-DD",
      "fii_net_cr": <number, negative if net sellers>,
      "dii_net_cr": <number, negative if net sellers>,
      "confidence": "🟢" | "🟡" | "🔴",
      "source": "<publication or exchange name>"
    },
    "sectoral": [
      {"index": "Nifty IT", "change_pct": <number>},
      ... one entry per sector actually moved today, IT/Bank/Pharma/Auto/Metal/Realty
    ]
  },
  "radar": [
    {
      "company": "<name>", "ticker": "<NSE/BSE symbol>",
      "summary": "<2-3 line news summary>",
      "source": "<publication>", "confidence": "🟢" | "🟡" | "🔴",
      "impact": "Bullish" | "Bearish" | "Neutral",
      "impact_confidence": "High" | "Medium" | "Low",
      "reasoning": "<one line>",
      "priced_in": "Yes" | "No" | "Partially"
    }
    // only include entries with an actual dated catalyst; empty array if none
  ],
  "insider": [
    {
      "company": "<name>", "ticker": "<symbol>",
      "who": "<name + designation>",
      "transaction_type": "Buy" | "Sell" | "Pledge" | "ESOP",
      "quantity": <number>, "value": "<₹ or $ amount>",
      "date": "YYYY-MM-DD", "source": "<BSE/NSE/SEC filing or portal>",
      "confidence": "🟢" | "🟡" | "🔴",
      "signal_strength": "Strong" | "Moderate" | "Weak" | "Negative",
      "context": "<one line on why it matters>",
      "priced_in": "Yes" | "No" | "Partially"
    }
    // empty array if nothing to report; note explicitly in a "note" field if the
    // underlying disclosure page couldn't be reached this run
  ],
  "calendar": [
    {
      "type": "IPO" | "Earnings" | "Macro",
      "name": "<company or event name>",
      "date": "YYYY-MM-DD",
      "detail": "<price band/GMP for IPO, consensus for earnings, description for macro>",
      "source": "<publication>"
    }
    // next 7-10 days only
  ],
  "geo": [
    {
      "headline": "<short headline>",
      "detail": "<1-2 sentence market read-through>",
      "source": "<publication>",
      "confidence": "🟢" | "🟡" | "🔴"
    }
  ],
  "note": "<anything you could not verify this run, stated plainly, or empty string>"
}

Do not wrap the JSON in markdown code fences. Do not add any text before the
opening brace or after the closing brace.
""".strip()

SYSTEM_PROMPT = f"""
You are filling in the sections of an India pre-market financial briefing
that have no free structured data source: FII/DII flows, event-triggered
stock-specific news (Pre-Market Radar), insider/promoter transactions,
the IPO/earnings/macro calendar, and geopolitical stories with market
read-through.

Rules:
- Search the web for every figure — never recall a price, date, or filing
  from memory. Today's date will be given to you in the user message.
- Radar and insider entries are strictly event-triggered: a company only
  appears if there is an actual dated catalyst (earnings, filing, price
  action, M&A, leadership change). No news = no entry = smaller array,
  not a placeholder entry.
- Never fabricate a number. If FII/DII data for the most recent session
  is not confirmable, use the last confirmed session's data and say so
  in "note" rather than inventing today's figure.
- No buy/sell recommendations — "impact"/"signal_strength" are signals,
  not directives.
- Confidence labels: 🟢 official exchange/SEC filing, 🟡 confirmed by
  2+ financial news portals, 🔴 single source only.

{JSON_SCHEMA_DESCRIPTION}
""".strip()


def generate() -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    today = datetime.date.today().isoformat()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Generate today's sections. Today's date is {today}.",
            }
        ],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
    )

    text_parts = [block.text for block in response.content if block.type == "text"]
    if not text_parts:
        raise RuntimeError("No text content returned from the API.")

    raw = "\n".join(text_parts).strip()
    return extract_json(raw)


def extract_json(text: str) -> dict:
    """Pull a JSON object out of the model's response, tolerating stray
    markdown fences or commentary the prompt asked it not to include."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output:\n{text[:500]}")
    return json.loads(cleaned[start : end + 1])


def load_existing_manual() -> dict:
    if MANUAL_FILE.exists():
        try:
            return json.loads(MANUAL_FILE.read_text())
        except json.JSONDecodeError as e:
            print(f"[warn] existing manual_sections.json is invalid JSON, ignoring: {e}", file=sys.stderr)
    return {}


def write_manual_sections(new_sections: dict) -> None:
    # Merge over the existing file rather than blind-overwrite, so a
    # partial/failed key in this run doesn't wipe a previously good value.
    existing = load_existing_manual()
    merged = {**existing, **new_sections}
    MANUAL_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    print(f"Wrote {MANUAL_FILE}")


if __name__ == "__main__":
    try:
        sections = generate()
    except Exception as e:
        # Deliberately do NOT touch manual_sections.json on failure — a
        # broken run should leave yesterday's good data in place, same
        # philosophy fetch_data.py already uses for its own sections.
        print(f"ERROR: generation failed, leaving manual_sections.json untouched: {e}", file=sys.stderr)
        sys.exit(1)

    write_manual_sections(sections)
