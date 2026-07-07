# The Morning Desk — dynamic setup

## Files
- `index.html` — the site. Now fetches `data.json` on load and re-fetches every 5 minutes. No more hardcoded numbers.
- `data.json` — the data the site renders. Currently seeded with the sample edition; `fetch_data.py` overwrites it.
- `fetch_data.py` — the script that regenerates `data.json`. Run it manually, on a cron, or via GitHub Actions.
- `requirements.txt` — `pip install -r requirements.txt`.
- `update-data.yml` — GitHub Actions workflow (move it to `.github/workflows/update-data.yml` in your repo).
- `manual_sections.json` *(you create this, optional)* — see below.

## What's actually automated vs. what needs your input
| Section | Status |
|---|---|
| Ticker (Nifty, Sensex, S&P, Nasdaq, USD/INR, Brent) | ✅ Live via `yfinance`, free, no key |
| Market Pulse + Nifty sparkline | ✅ Live via `yfinance` |
| Hero headline | ✅ Pulled from Moneycontrol/ET RSS |
| Top gainers/losers, AI & Green watch | ⚠️ Manual — no free structured feed for this |
| Pre-Market Radar, Insider Intelligence, IPO/Earnings Calendar, Geopolitical | ⚠️ Manual — BSE/NSE publish these as HTML pages, not APIs |

The "⚠️ Manual" sections aren't faked with placeholder numbers — the script preserves whatever was last written to `data.json` for those, so nothing silently goes stale-looking. To update them yourself without touching code, create `manual_sections.json` next to the script:

```json
{
  "market": { "gainers": [...], "losers": [...], "watch": [...] },
  "radar": [...],
  "insider": [...],
  "calendar": [...],
  "geo": [...]
}
```

Use the same shape as the matching keys in `data.json`. The script merges this in on every run, so you edit one small file during your actual briefing routine and the site picks it up on the next scheduled run — that's the piece that stays closest to how you already compile the briefing today.

If you want those sections fully automated later, the realistic paths are a paid data vendor (Twelve Data, a BSE/NSE data subscription) or a maintained scraper with retry/backoff against the BSE/NSE HTML pages — both are separate scoped pieces of work, not something to bolt on casually given rate limiting.

## Running it
**Locally, once:**
```bash
pip install -r requirements.txt
python fetch_data.py
python -m http.server 8000   # then open http://localhost:8000
```

**On a schedule, hands-off (recommended — GitHub Pages + Actions):**
1. Push this folder to a GitHub repo, enable GitHub Pages on it.
2. Move `update-data.yml` to `.github/workflows/update-data.yml`.
3. That's it — Actions runs the script every 30 min during market hours, commits the new `data.json`, Pages redeploys automatically.

**On your existing Tidal scheduler:** point a Tidal job at `python fetch_data.py` on the same box that serves the HTML — same pattern as your `send_excel_outlook.py` job, just swapped target.

## Weather-driven masthead backdrop
The masthead + hero band now carries a live canvas effect instead of a flat color:
- On load, it calls Open-Meteo (`api.open-meteo.com`, free, no key) for the current weather at the coordinates set in `index.html` (`LAT`/`LON` — currently Hyderabad; change these to your city).
- Thunderstorm codes → rain + lightning flashes. Rain codes → rain, no lightning. Fog codes → drifting haze. High temp with clear sky → rising heat-shimmer particles.
- If the API is unreachable, it falls back to the Indian seasonal calendar (monsoon Jun–Sep, post-monsoon Oct–Nov, winter Dec–Feb, summer Mar–May) — so it always shows *something* relevant, live data or not.
- A small caption in the top-right of the band shows which mode it's in (e.g. "Monsoon skies · 27°C") and whether that came from live data or the seasonal fallback.
- Respects `prefers-reduced-motion` — shows a static tinted gradient instead of animating for anyone with that OS setting on.

## Visitor counter
The footer now shows a hit counter via [hits.seeyoufarm.com](https://hits.seeyoufarm.com) — a free badge service, no signup, no key. **Before you rely on it:**
- It increments once per page load of the exact `url=` parameter you give it in `index.html` — right now that's a placeholder (`themorningdesk.example.com`). Swap it for your real deployed URL once you have one, or the count means nothing.
- It's approximate: refreshes, bots, and ad-blockers can all skew it. Fine for "roughly how many hits am I getting," not for real traffic analysis.
- For actual analytics (unique visitors, referrers, time on page, no cookie banners needed) swap this for **Plausible**, **GoatCounter**, or **Umami** — all lightweight, privacy-friendly, and a one-`<script>` install once you're ready to take this seriously.
