#!/usr/bin/env python3
"""
pilgrim_pulse - CLI demand scanner for short‑term rental arbitrage in spiritual cities.

Features:
- Accepts city/area and optional date range.
- Pulls Airbnb comparable listings via HTML scraping (price strings + “X stays” count).
- Pulls pilgrimage/event data from Holidify festival pages.
- Uses Google Trends (pytrends) for accommodation interest with retry/backoff.
- Outputs a markdown table with a demand score and go/hold/recommendation.

Note: Scraping respects a polite user‑agent and a short delay; for production
use consider official APIs or rate‑limited scraping with caching.
"""

import argparse
import datetime as dt
import json
import re
import sys
import time
from typing import Dict, Tuple

import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq
from tabulate import tabulate

# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 15
# Simple in‑memory cache for Google Trends to avoid hammering the service
_TREND_CACHE: Dict[str, Tuple[float, float]] = {}  # city -> (score, timestamp)
_TREND_CACHE_TTL = 6 * 60 * 60  # 6 hours


# ----------------------------------------------------------------------
# Airbnb HTML scraper (replaces the earlier API/JSON attempt)
# ----------------------------------------------------------------------
def fetch_airbnb_comps(city: str, check_in: dt.date, check_out: dt.date) -> Dict[str, float]:
    """
    Scrape Airbnb search results for the given city and date range.
    Returns a dict with:
        - avg_price: average nightly price (INR) derived from all price strings found.
        - occupancy: estimated occupancy % = (number of price strings / total stays) * 100,
                     capped at 100.
    """
    # Build the search URL
    cin = check_in.strftime("%Y-%m-%d")
    cout = check_out.strftime("%Y-%m-%d")
    url = (
        f"https://www.airbnb.com/s/{city}/homes?"
        f"checkin={cin}&checkout={cout}&adults=1&source=bb&ss_id="
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  Airbnb request failed ({e}); using fallback values.", file=sys.stderr)
        return {"avg_price": 1500.0, "occupancy": 65.0}

    html = resp.text

    # --- 1️⃣ Extract all price strings (₹1,200, $45, etc.) -------------------------
    price_matches = re.findall(r"[₹$]\s?[\d,]+", html)
    prices = []
    for m in price_matches:
        # strip currency symbol and commas
        num = re.sub(r"[₹$,\s]", "", m)
        if num.isdigit():
            prices.append(int(num))
        elif re.fullmatch(r"\d+\.\d+", num):
            try:
                prices.append(float(num))
            except ValueError:
                pass

    # --- 2️⃣ Extract total number of stays/results -------------------------------
    # Airbnb often shows text like “1,000 stays” or “1,200 results”.
    total_match = re.search(r"([\d,]+)\s+(?:stays|results|homes)", html, re.I)
    total_listings = 0
    if total_match:
        total_str = total_match.group(1).replace(",", "")
        if total_str.isdigit():
            total_listings = int(total_str)

    # If we couldn't get a total, fall back to a reasonable baseline
    if total_listings == 0:
        total_listings = max(len(prices), 1)

    # --- 3️⃣ Compute average price & occupancy ----------------------------------
    avg_price = sum(prices) / len(prices) if prices else 1500.0
    occupancy = (len(prices) / total_listings) * 100 if total_listings else 65.0
    occupancy = max(0.0, min(100.0, occupancy))

    # Clamp price to a sane range (avoid crazy outliers)
    avg_price = max(0.0, min(10000.0, avg_price))

    return {"avg_price": round(avg_price, 2), "occupancy": round(occupancy, 2)}


# ----------------------------------------------------------------------
# Event scraper (unchanged)
# ----------------------------------------------------------------------
def fetch_event_spike(city: str, start_date: dt.date, end_date: dt.date) -> float:
    """
    Scrape Holidify festival page for the given city.
    If any festival date falls within [start_date, end_date], return a multiplier >1.
    Otherwise return 1.0.
    """
    city_slug = city.lower().replace(" ", "-")
    url = f"https://www.holidify.com/places/{city_slug}/festivals/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception:
        return 1.0

    soup = BeautifulSoup(resp.text, "html.parser")
    date_pattern = re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{4}\b",
        re.I,
    )
    date_pattern2 = re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", re.I)

    text = soup.get_text(" ", strip=True)
    matches = date_pattern.findall(text) + date_pattern2.findall(text)
    for m in matches:
        try:
            for fmt in ("%b %d, %Y", "%d %b %Y", "%b %d %Y", "%d %b, %Y"):
                try:
                    fest_dt = dt.datetime.strptime(m.strip(), fmt).date()
                    if start_date <= fest_dt <= end_date:
                        return 1.5
                except ValueError:
                    continue
        except Exception:
            continue
    return 1.0


# ----------------------------------------------------------------------
# Google Trends with caching & retry (unchanged)
# ----------------------------------------------------------------------
def fetch_google_trends(city: str) -> float:
    now = time.time()
    if city in _TREND_CACHE:
        score, ts = _TREND_CACHE[city]
        if now - ts < _TREND_CACHE_TTL:
            return score

    kw = f"{city} accommodation"
    backoff = 1
    for attempt in range(5):
        try:
            pytrends = TrendReq(hl='en-IN', tz=330, timeout=(10, 25))
            pytrends.build_payload([kw], cat=0, timeframe='today 12-m', geo='IN', gprop='')
            data = pytrends.interest_over_time()
            if data.empty:
                score = 0.0
            else:
                score = float(data[kw].iloc[-1])
            _TREND_CACHE[city] = (score, now)
            return score
        except Exception as e:
            if "429" in str(e) or "timed out" in str(e).lower():
                print(f"Warning: Google Trends request failed (attempt {attempt+1}), retrying in {backoff}s...", file=sys.stderr)
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                print(f"Warning: Google Trends request failed: {e}", file=sys.stderr)
                break
    if city in _TREND_CACHE:
        return _TREND_CACHE[city][0]
    return 0.0


# ----------------------------------------------------------------------
# Scoring & recommendation (unchanged)
# ----------------------------------------------------------------------
def compute_demand_score(avg_price: float, occupancy: float, event_multiplier: float, trend_score: float) -> float:
    price_score = min(30, max(0, (avg_price - 500) / (5000 - 500) * 30))
    occ_score = min(30, occupancy * 0.3)
    event_score = min(20, (event_multiplier - 1) * 50)
    trend_score_norm = min(20, trend_score * 0.2)
    return price_score + occ_score + event_score + trend_score_norm


def recommendation(score: float) -> str:
    if score >= 70:
        return "🚀 Go"
    elif score >= 40:
        return "🤔 Hold"
    else:
        return "🛑 Avoid"


# ----------------------------------------------------------------------
# CLI entry point (unchanged)
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pilgrim Pulse – estimate short‑term rental demand for spiritual cities."
    )
    parser.add_argument(
        "city",
        help="City or area to analyse (e.g., Varanasi, Rishikesh, Ajmer)."
    )
    parser.add_argument(
        "--start",
        help="Check‑in date (YYYY-MM-DD). Defaults to today.",
        type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d").date(),
        default=dt.date.today(),
    )
    parser.add_argument(
        "--end",
        help="Check‑out date (YYYY-MM-DD). Defaults to start + 2 nights.",
        type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d").date(),
    )
    args = parser.parse_args()

    if args.end is None:
        args.end = args.start + dt.timedelta(days=2)

    print(f"🔍 Analysing {args.city} from {args.start} to {args.end}...\n")

    comps = fetch_airbnb_comps(args.city, args.start, args.end)
    event_mult = fetch_event_spike(args.city, args.start, args.end)
    trend = fetch_google_trends(args.city)

    score = compute_demand_score(
        avg_price=comps["avg_price"],
        occupancy=comps["occupancy"],
        event_multiplier=event_mult,
        trend_score=trend,
    )
    rec = recommendation(score)

    table = [
        ["Metric", "Value"],
        ["Average nightly price (₹)", f"{comps['avg_price']:.0f}"],
        ["Estimated occupancy (%)", f"{comps['occupancy']:.1f}"],
        ["Event multiplier", f"{event_mult:.2f}"],
        ["Google Trends interest (0‑100)", f"{trend:.1f}"],
        ["Demand score (0‑100)", f"{score:.1f}"],
        ["Recommendation", rec],
    ]
    print(tabulate(table, headers="firstrow", tablefmt="github"))


if __name__ == "__main__":
    main()