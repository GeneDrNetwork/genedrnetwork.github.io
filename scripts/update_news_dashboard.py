#!/usr/bin/env python3
"""Refresh the GeneDrNews & Invest dashboard using free public feeds."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news-dashboard.json"
USER_AGENT = "GeneDrNetwork-Daily-Dashboard/1.0 (+https://genedrnetwork.github.io/)"

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


def news_url(query: str) -> str:
    return "https://news.google.com/search?q=" + urllib.parse.quote(query)


def entity(name, status, focus, **details):
    return {"name": name, "status": status, "focus": focus, "details": details,
            "news": {"title": "View latest coverage", "url": news_url(name)}}


AI_LEADERS = [
    entity("OpenAI", "Private", "Frontier models and AI products", Importance="Frontier model development and broad platform adoption"),
    entity("Anthropic", "Private", "AI safety and enterprise models", Importance="Safety-focused frontier research and enterprise deployment"),
    entity("Google DeepMind", "Public parent", "Foundation models and scientific AI", Importance="Deep research capacity across AI and life sciences"),
    entity("Microsoft AI", "Public", "Enterprise AI and cloud", Importance="Global enterprise distribution and cloud infrastructure"),
    entity("NVIDIA", "Public", "Accelerated computing and AI chips", Importance="Core compute platform for model training and inference"),
    entity("Meta AI", "Public", "Open models and consumer AI", Importance="Open-weight ecosystem and global product reach"),
    entity("Amazon AI", "Public", "Cloud AI and foundation models", Importance="Cloud infrastructure and enterprise model marketplace"),
    entity("xAI", "Private", "Frontier models and real-time AI", Importance="Rapidly scaling models, compute, and consumer distribution"),
]

AI_EMERGING = [
    ("Perplexity", "AI answer engine", "Venture-backed", "Consumer and enterprise search"),
    ("Mistral AI", "Efficient foundation models", "Venture-backed", "European open and commercial models"),
    ("Cohere", "Enterprise language models", "Venture-backed", "Secure enterprise AI deployments"),
    ("Scale AI", "AI data infrastructure", "Private", "Training data and evaluation platforms"),
    ("CoreWeave", "GPU cloud infrastructure", "Public", "Specialized accelerated cloud capacity"),
    ("Runway", "Generative video", "Venture-backed", "Creative video generation models"),
    ("ElevenLabs", "Synthetic voice AI", "Venture-backed", "High-fidelity multilingual audio"),
    ("Figure AI", "Humanoid robotics", "Venture-backed", "General-purpose embodied AI"),
    ("Physical Intelligence", "Robotics foundation models", "Venture-backed", "Generalist intelligence for robots"),
    ("Cerebras", "AI compute systems", "Private", "Wafer-scale AI acceleration"),
    ("Lambda", "GPU cloud", "Private", "AI developer compute infrastructure"),
    ("Together AI", "Open-model cloud", "Venture-backed", "Training and inference for open models"),
    ("Adept", "Agentic AI", "Private", "AI systems that operate software"),
    ("Harvey", "Legal AI", "Venture-backed", "Vertical AI for professional services"),
    ("Sierra", "Customer-service agents", "Venture-backed", "Enterprise conversational agents"),
]
AI_EMERGING = [entity(n, s, t, **{"Funding status": s, "Recent milestone": m, "Why promising": m}) for n, t, s, m in AI_EMERGING]

BIOTECH_LEADERS = [
    ("Vertex Pharmaceuticals", "VRTX", "CF therapies; CASGEVY", "Pain, kidney disease, cell therapy"),
    ("Regeneron", "REGN", "EYLEA; Dupixent", "Antibodies, oncology, genetics"),
    ("Moderna", "MRNA", "mRNA vaccines", "Oncology and infectious disease vaccines"),
    ("BioMarin", "BMRN", "Rare disease enzyme and gene therapies", "Genetic disease programs"),
    ("Ultragenyx", "RARE", "Rare disease therapeutics", "Gene therapy and metabolic disease"),
    ("Alnylam", "ALNY", "RNA interference medicines", "Cardiometabolic and rare disease"),
    ("Sarepta", "SRPT", "Duchenne muscular dystrophy therapies", "Gene therapy and RNA medicines"),
    ("argenx", "ARGX", "VYVGART", "Immunology indications"),
    ("Ionis Pharmaceuticals", "IONS", "RNA-targeted medicines", "Neurology and cardiometabolic disease"),
]
BIOTECH_LEADERS = [entity(n, "Public", "Biotechnology and therapeutics", Ticker=t, **{"Market cap": "See current market source", "Lead products": p, "Key pipeline": k, "Strategic importance": "Established platform with clinically relevant pipeline"}) for n,t,p,k in BIOTECH_LEADERS]

BIOTECH_EMERGING = [
    ("CRISPR Therapeutics", "CRSP", "CRISPR gene editing", "Hemoglobinopathies", "Commercial/clinical"),
    ("Beam Therapeutics", "BEAM", "Base editing", "Hematology and genetic disease", "Clinical"),
    ("Intellia Therapeutics", "NTLA", "In vivo CRISPR editing", "ATTR and hereditary angioedema", "Clinical"),
    ("Prime Medicine", "PRME", "Prime editing", "Genetic diseases", "Early clinical"),
    ("Verve Therapeutics", "VERV", "In vivo base editing", "Cardiovascular disease", "Clinical"),
    ("Editas Medicine", "EDIT", "CRISPR gene editing", "Hematology", "Clinical"),
    ("Rocket Pharmaceuticals", "RCKT", "Gene therapy", "Rare genetic diseases", "Late clinical"),
    ("Scholar Rock", "SRRK", "Growth-factor biology", "Neuromuscular disease", "Late clinical"),
    ("Stoke Therapeutics", "STOK", "RNA splicing", "Dravet syndrome", "Clinical"),
    ("ProQR", "PRQR", "RNA editing", "Genetic diseases", "Preclinical/clinical"),
    ("Krystal Biotech", "KRYS", "Redosable gene therapy", "Rare dermatologic disease", "Commercial/clinical"),
    ("Maze Therapeutics", "MAZE", "Human genetics platform", "Renal and metabolic disease", "Clinical"),
    ("Metagenomi", "MGX", "Metagenomics-derived editing", "Genetic diseases", "Preclinical"),
    ("Generate Biomedicines", "Private", "Generative protein design", "Antibodies and proteins", "Clinical"),
]
BIOTECH_EMERGING = [entity(n, "Public" if t != "Private" else "Private", platform, Ticker=t, **{"Lead program": lead, "Development stage": stage, "Upcoming catalysts": "Clinical, regulatory, or partnership updates", "Why promising": f"Differentiated {platform.lower()} platform"}) for n,t,platform,lead,stage in BIOTECH_EMERGING]

WATCHLIST = {
    "NVDA": "NVIDIA", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon",
    "META": "Meta Platforms", "TSM": "Taiwan Semiconductor", "VRTX": "Vertex Pharmaceuticals",
    "REGN": "Regeneron", "MRNA": "Moderna", "CRSP": "CRISPR Therapeutics",
    "BEAM": "Beam Therapeutics", "NTLA": "Intellia Therapeutics", "SRPT": "Sarepta Therapeutics",
    "RARE": "Ultragenyx", "BMRN": "BioMarin", "TEM": "Tempus AI",
}

MARKETS = {"^GSPC": ("^spx", "S&P 500"), "^IXIC": ("^ndq", "Nasdaq"),
           "^DJI": ("^dji", "Dow Jones"), "^RUT": ("^rty", "Russell 2000")}


def fetch(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read()


def rss_items(query: str, limit: int = 5):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en"
    try:
        root = ET.fromstring(fetch(url))
        items = []
        for item in root.findall(".//item")[:limit]:
            items.append({"title": item.findtext("title", "Latest coverage"), "url": item.findtext("link", news_url(query)), "date": item.findtext("pubDate", "")})
        return items
    except Exception as exc:
        print(f"RSS unavailable for {query}: {exc}")
        return []


def enrich_news(entities):
    for item in entities:
        results = rss_items(f'"{item["name"]}" when:7d', 1)
        if results:
            item["news"] = results[0]


def stooq_history(symbol: str):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=50)
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(symbol)}&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
    try:
        rows = list(csv.DictReader(io.StringIO(fetch(url).decode("utf-8"))))
        return [r for r in rows if r.get("Close") not in (None, "", "N/D")]
    except Exception as exc:
        print(f"Market data unavailable for {symbol}: {exc}")
        return []


def percent_change(current, previous):
    return round((current / previous - 1) * 100, 2) if previous else 0


def yahoo_history(symbol: str):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol, safe="") + "?range=1mo&interval=1d"
    try:
        payload = json.loads(fetch(url, timeout=12))
        result = payload["chart"]["result"][0]
        return [float(value) for value in result["indicators"]["quote"][0]["close"] if value is not None]
    except Exception as exc:
        print(f"Yahoo data unavailable for {symbol}: {exc}")
        return []


def quote(yahoo_symbol: str, stooq_symbol: str, fallback=None):
    closes = yahoo_history(yahoo_symbol)
    rows = [] if closes else stooq_history(stooq_symbol)
    if rows:
        closes = [float(row["Close"]) for row in rows]
    if not rows:
        if not closes:
            return fallback or {"price": "N/A", "daily": 0, "weekly": 0, "monthly": 0}
    current = closes[-1]
    return {"price": f"{current:,.2f}", "daily": percent_change(current, closes[-2] if len(closes) > 1 else current),
            "weekly": percent_change(current, closes[-6] if len(closes) > 5 else closes[0]),
            "monthly": percent_change(current, closes[-22] if len(closes) > 21 else closes[0])}


def prior_data():
    try: return json.loads(OUTPUT.read_text())
    except (OSError, json.JSONDecodeError): return {}


def summarize(headlines, label):
    if not headlines: return f"No new {label} headlines were found in today's public feeds. Monitoring continues."
    clean = [re.sub(r"\s+-\s+[^-]+$", "", h["title"]).strip() for h in headlines[:3]]
    return "Key developments: " + "; ".join(clean) + "."


def parse_fda(items):
    updates = []
    for item in items[:8]:
        title = re.sub(r"\s+-\s+[^-]+$", "", item["title"])
        updates.append({"company": "See source", "product": "See source", "indication": "See source",
                        "event": title, "date": item.get("date", "")[:16], "url": item["url"]})
    return updates


def build():
    previous = prior_data()
    groups = [AI_LEADERS, AI_EMERGING, BIOTECH_LEADERS, BIOTECH_EMERGING]
    for group in groups: enrich_news(group)

    ai_news = rss_items("artificial intelligence industry breakthrough when:1d", 6)
    biotech_news = rss_items("biotechnology rare disease drug development when:1d", 6)
    fda_news = rss_items("FDA approval OR orphan drug OR fast track OR breakthrough therapy rare disease when:7d", 8)
    market_news = rss_items("US stock market Nasdaq S&P 500 today when:1d", 4)

    markets = []
    old_markets = {m["name"]: m for m in previous.get("markets", [])}
    for yahoo_symbol, (stooq_symbol, name) in MARKETS.items():
        q = quote(yahoo_symbol, stooq_symbol, {"price": old_markets.get(name, {}).get("value", "N/A"), "daily": old_markets.get(name, {}).get("daily", 0), "weekly": old_markets.get(name, {}).get("weekly", 0), "monthly": old_markets.get(name, {}).get("monthly", 0)})
        markets.append({"name": name, "value": q.pop("price"), **q})

    old_watch = {w["ticker"]: w for w in previous.get("watchlist", [])}
    watchlist = []
    for ticker, company in WATCHLIST.items():
        old = old_watch.get(ticker, {})
        q = quote(ticker, ticker.lower() + ".us", {"price": old.get("price", "N/A"), "daily": old.get("daily", 0), "weekly": old.get("weekly", 0), "monthly": 0})
        news = rss_items(f'"{company}" stock when:7d', 1)
        news = news[0] if news else old.get("news", {"title": "Latest coverage", "url": news_url(company)})
        watchlist.append({"ticker": ticker, "company": company, "price": q["price"], "daily": q["daily"], "weekly": q["weekly"], "news": news,
                          "summary": "Monitor company-specific scientific, regulatory, financial, and partnership developments."})

    if any(market["value"] != "N/A" for market in markets):
        top_market = max(markets, key=lambda x: x["daily"])
        weak_market = min(markets, key=lambda x: x["daily"])
        market_movers = f'{top_market["name"]} led the tracked indexes at {top_market["daily"]:+.2f}% today; {weak_market["name"]} was the weakest at {weak_market["daily"]:+.2f}%. ' + summarize(market_news, "market")
    else:
        market_movers = "Price feeds are temporarily unavailable. " + summarize(market_news, "market")
    ai_summary = summarize(ai_news, "AI")
    biotech_summary = summarize(biotech_news, "biotech")
    market_summary = summarize(market_news, "market")
    takeaways = [h["title"] for h in (ai_news[:2] + biotech_news[:2] + fda_news[:2] + market_news[:1])]
    if not takeaways: takeaways = previous.get("takeaways", ["Daily source monitoring is active; no new feed items were available at this update."])

    signal_words = ("approval", "breakthrough", "clinical", "funding", "financing", "partnership", "launch", "data", "milestone", "trial")
    candidates = []
    for item in AI_EMERGING + BIOTECH_EMERGING:
        headline = item["news"].get("title", "")
        signal_count = sum(word in headline.lower() for word in signal_words)
        score = min(10, 6 + signal_count)
        candidates.append((score, item, headline))
    opportunities = []
    for score, item, headline in sorted(candidates, key=lambda candidate: (-candidate[0], candidate[1]["name"]))[:6]:
        opportunities.append({"company": item["name"], "score": score, "potential": item["focus"],
                              "risk": "High" if item["status"] in ("Private", "Venture-backed") else "Medium",
                              "catalyst": headline if headline != "View latest coverage" else item["details"].get("Upcoming catalysts", "Product, funding, or partnership milestone"),
                              "url": item["news"]["url"]})

    data = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "summaries": {"ai": ai_summary, "market": market_summary, "biotech": biotech_summary, "market_movers": market_movers},
            "takeaways": takeaways[:10], "ai": {"leaders": AI_LEADERS, "emerging": AI_EMERGING},
            "biotech": {"leaders": BIOTECH_LEADERS, "emerging": BIOTECH_EMERGING},
            "fda": parse_fda(fda_news) or previous.get("fda", []), "markets": markets, "watchlist": watchlist, "opportunities": opportunities}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")
    print(f"Updated {OUTPUT}")


if __name__ == "__main__":
    build()
