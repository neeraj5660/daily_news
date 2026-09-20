"""
fetch_data.py — regenerates data.json for The Morning Desk.

PIPELINE ORDER (updated — see .github/workflows/daily-india-briefing.yml):
    1. python generate_llm_sections.py   <- NEW. Anthropic API + web search,
                                             writes manual_sections.json with
                                             market/radar/insider/calendar/geo
    2. python fetch_data.py              <- this script, unchanged logic below.
                                             Reads manual_sections.json (now
                                             populated by step 1 instead of by
                                             hand) and merges it with the free
                                             yfinance/RSS data into data.json.

WHAT THIS SCRIPT AUTOMATES FOR REAL (free, no API key):
  - Index levels + % change (Nifty, Sensex, Bank Nifty, S&P 500, Nasdaq, USDINR, Brent) via yfinance
  - A rolling sparkline for the Nifty 50
  - Headline candidates pulled from financial news RSS feeds

WHAT IT DOES NOT FETCH ITSELF (unchanged from before):
  FII/DII net flows, insider trades, IPO calendar, and geopolitical items have no
  reliable free structured API — BSE/NSE publish these as HTML pages, not feeds.
  As of this pipeline update, generate_llm_sections.py fills these in automatically
  via the Anthropic API before this script runs. manual_sections.json can still be
  edited by hand if you ever want to override a specific value for a day.

USAGE:
  pip install -r requirements.txt
  python fetch_data.py
"""

import json
import feedparser
import yfinance as yf
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DATA_FILE = Path(__file__).parent / "data.json"
MANUAL_FILE = Path(__file__).parent / "manual_sections.json"  # now written by generate_llm_sections.py

INDEX_TICKERS = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "USD/INR": "INR=X",
    "BRENT CRUDE": "BZ=F",
}

NEWS_FEEDS = [
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
]


def pct_change(hist):
    if len(hist) < 2:
        return 0.0
    prev, last = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
    return (last - prev) / prev * 100


def fetch_indices():
    ticker_items, nifty_spark, pulse = [], [], {}
    for label, symbol in INDEX_TICKERS.items():
        try:
            hist = yf.Ticker(symbol).history(period="10d")
            if hist.empty:
                continue
            last = hist["Close"].iloc[-1]
            chg = pct_change(hist)
            direction = "up" if chg >= 0 else "down"
            arrow = "▲" if direction == "up" else "▼"
            value = f"{last:,.2f}"
            ticker_items.append({
                "symbol": label, "value": value,
                "change": f"{arrow} {abs(chg):.2f}%", "direction": direction,
            })
            if label == "NIFTY 50":
                nifty_spark = [round(v, 1) for v in hist["Close"].tolist()]
                pulse = {
                    "last_close": value,
                    "change": f"{'+' if chg >= 0 else ''}{chg:.2f}%",
                    "direction": direction,
                    "spark": nifty_spark,
                }
        except Exception as e:
            print(f"[warn] failed to fetch {label} ({symbol}): {e}")
    return ticker_items, pulse


def fetch_headline():
    for url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = feed.entries[0]
                return {
                    "confidence": "MEDIUM",
                    "confidence_note": "financial news portal",
                    "headline": entry.title,
                    "lede": getattr(entry, "summary", "")[:220],
                }
        except Exception as e:
            print(f"[warn] failed to fetch feed {url}: {e}")
    return None


def load_existing():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except json.JSONDecodeError as e:
            print(f"[warn] existing data.json is invalid JSON, ignoring: {e}")
    return {}


def load_manual_overrides():
    if MANUAL_FILE.exists():
        try:
            return json.loads(MANUAL_FILE.read_text())
        except json.JSONDecodeError as e:
            print(f"[warn] manual_sections.json is invalid JSON, ignoring: {e}")
    return {}


def build_feed():
    existing = load_existing()
    manual = load_manual_overrides()

    ticker_items, pulse = fetch_indices()
    headline = fetch_headline()

    data = {
        "updated_at": datetime.now(IST).isoformat(),
        "edition_label": existing.get("edition_label", "Pre-Market Edition"),
        "ticker": ticker_items or existing.get("ticker", []),
        "hero": headline or existing.get("hero", {}),
        "pulse": {**existing.get("pulse", {}), **pulse} if pulse else existing.get("pulse", {}),
        # These sections come from manual_sections.json, now written daily by
        # generate_llm_sections.py (step 1 in the pipeline) rather than by hand.
        "market": manual.get("market", existing.get("market", {})),
        "radar": manual.get("radar", existing.get("radar", [])),
        "insider": manual.get("insider", existing.get("insider", [])),
        "calendar": manual.get("calendar", existing.get("calendar", [])),
        "geo": manual.get("geo", existing.get("geo", [])),
    }

    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Wrote {DATA_FILE} at {data['updated_at']}")


if __name__ == "__main__":
    build_feed()
