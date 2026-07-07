"""
fetch_data.py — regenerates data.json for The Morning Desk.

WHAT THIS SCRIPT AUTOMATES FOR REAL (free, no API key):
  - Index levels + % change (Nifty, Sensex, Bank Nifty, S&P 500, Nasdaq, USDINR, Brent) via yfinance
  - A rolling sparkline for the Nifty 50
  - Headline candidates pulled from financial news RSS feeds

WHAT IT DOES NOT FAKE:
  FII/DII net flows, insider trades, IPO calendar, and geopolitical items have no
  reliable free structured API — BSE/NSE publish these as HTML pages, not feeds,
  and scraping them reliably needs either a paid data vendor (e.g. Twelve Data,
  a BSE/NSE data subscription) or a maintained scraper with retry/backoff.
  This script therefore PRESERVES whatever is already in those sections of
  data.json (or in manual_sections.json, if present) rather than overwriting
  them with placeholder numbers. Update those sections yourself, or plug in
  your paid data source inside fetch_fii_dii() / fetch_insider() / etc. below.

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
MANUAL_FILE = Path(__file__).parent / "manual_sections.json"  # optional, you maintain this

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
        return json.loads(DATA_FILE.read_text())
    return {}


def load_manual_overrides():
    if MANUAL_FILE.exists():
        return json.loads(MANUAL_FILE.read_text())
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
        # These sections have no free structured source (see docstring) —
        # prefer manual_sections.json if you maintain one, else keep last known values.
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
