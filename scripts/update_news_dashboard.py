#!/usr/bin/env python3
"""Refresh the curated GeneDr News & Invest dashboard from public feeds."""

from __future__ import annotations

import csv
import io
import json
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news-dashboard.json"
USER_AGENT = "GeneDrNetwork-Daily-Dashboard/2.0 (+https://genedrnetwork.github.io/)"
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


def leader(company, ticker, sector, role, market_cap="Large Cap", growth="High"):
    return {"company": company, "ticker": ticker, "sector": sector, "role": role,
            "market_cap": market_cap, "growth_potential": growth}


AI_INFRASTRUCTURE = [
    leader("NVIDIA", "NVDA", "AI Chips", "Accelerated computing platform and dominant AI accelerator ecosystem"),
    leader("AMD", "AMD", "AI Chips", "Alternative accelerators and data-center CPUs"),
    leader("TSMC", "TSM", "Semiconductor Manufacturing", "Leading-edge foundry capacity for advanced AI silicon"),
    leader("Broadcom", "AVGO", "Networking / Custom Silicon", "AI networking and hyperscaler custom accelerators"),
    leader("Micron", "MU", "Memory", "High-bandwidth memory required by AI accelerators"),
    leader("Arista Networks", "ANET", "AI Networking", "High-speed Ethernet for scale-out AI clusters"),
    leader("Vertiv", "VRT", "Data Centers / Power", "Cooling and power systems for high-density compute", "Mid Cap", "High"),
    leader("Dell Technologies", "DELL", "AI Servers", "Enterprise AI servers and integrated infrastructure"),
    leader("Super Micro Computer", "SMCI", "AI Servers", "Rack-scale, liquid-cooled AI server systems", "Mid Cap", "High"),
    leader("CoreWeave", "CRWV", "GPU Cloud", "Specialized cloud capacity optimized for AI workloads", "Mid Cap", "High"),
]

AI_PLATFORMS = [
    leader("Microsoft", "MSFT", "Cloud / Foundation Models", "Azure AI distribution and OpenAI ecosystem"),
    leader("Alphabet", "GOOGL", "Cloud / Foundation Models", "Gemini models, TPU infrastructure, and global products"),
    leader("Amazon", "AMZN", "Cloud / Foundation Models", "AWS infrastructure and multi-model enterprise platform"),
    leader("Meta Platforms", "META", "Foundation Models", "Open model ecosystem and consumer distribution"),
    leader("OpenAI", "Private", "Foundation Models", "Frontier model and developer platform", "Private", "High"),
    leader("Anthropic", "Private", "Foundation Models", "Enterprise-focused frontier models and safety research", "Private", "High"),
    leader("xAI", "Private", "Foundation Models", "Rapidly scaling compute, models, and product distribution", "Private", "High"),
]

AI_EMERGING_RAW = [
    (1, "Cerebras Systems", "AI Compute", "Wafer-scale systems can lower training and inference latency for specialized workloads.", "Private", "High", "High"),
    (2, "Groq", "AI Inference", "Purpose-built inference architecture targets predictable, low-latency model serving.", "Private", "High", "High"),
    (3, "Figure AI", "Robotics", "General-purpose humanoids could translate foundation-model progress into physical labor.", "Private", "High", "High"),
    (4, "Astera Labs", "Data-Center Connectivity", "Connectivity silicon addresses bandwidth and memory bottlenecks inside AI systems.", "Mid Cap", "High", "Medium"),
    (5, "Tempus AI", "AI Healthcare", "Clinical data and diagnostics platform can compound as multimodal healthcare AI expands.", "Mid Cap", "High", "High"),
    (6, "Aurora Innovation", "Autonomous Systems", "Driver-as-a-service model provides focused exposure to autonomous trucking.", "Mid Cap", "High", "High"),
    (7, "Cloudflare", "Edge AI", "Global edge network can host inference near users while securing AI applications.", "Mid Cap", "High", "Medium"),
    (8, "Samsara", "Industrial AI", "Connected-operations data creates a base for AI-led fleet and physical-asset optimization.", "Mid Cap", "High", "Medium"),
    (9, "Rubrik", "AI Data Security", "Cyber-resilience and protected enterprise data become more valuable as AI attack surfaces grow.", "Mid Cap", "High", "Medium"),
    (10, "Scale AI", "AI Data Infrastructure", "Evaluation and high-quality training data remain critical infrastructure for advanced models.", "Private", "High", "High"),
    (11, "Physical Intelligence", "Robotics", "Generalist robot models target cross-platform embodied intelligence.", "Private", "High", "High"),
    (12, "Oklo", "AI Energy", "Advanced nuclear development offers long-duration clean power exposure for data centers.", "Mid Cap", "High", "High"),
]
AI_EMERGING = [{"rank": r, "company": c, "sector": s, "thesis": t, "market_cap": m,
                "growth_potential": g, "risk": risk} for r, c, s, t, m, g, risk in AI_EMERGING_RAW]

DEMAND_DRIVERS = [
    (1, "AI Compute", "Training and inference workloads continue to scale in size, frequency, and model complexity.", "NVIDIA, AMD, Broadcom", "Cerebras, Groq, Tenstorrent"),
    (2, "Advanced Semiconductors", "AI systems require leading-edge logic, packaging, and high-bandwidth memory.", "TSMC, ASML, Micron", "Astera Labs, Celestial AI"),
    (3, "Data Centers", "Accelerated clusters need purpose-built facilities, cooling, and dense rack integration.", "Vertiv, Equinix, Dell", "CoreWeave, Crusoe"),
    (4, "Energy & Power Infrastructure", "AI campuses strain grids and create demand for generation, storage, and transmission.", "Constellation, GE Vernova, Eaton", "Oklo, Fervo Energy, Form Energy"),
    (5, "AI Networking", "Distributed training requires faster, lower-latency movement of data between accelerators.", "Broadcom, Arista, Marvell", "Lightmatter, Celestial AI"),
    (6, "Robotics", "Better perception and foundation models are expanding addressable tasks in factories and services.", "Tesla, ABB, Teradyne", "Figure AI, Physical Intelligence"),
    (7, "Autonomous Systems", "Improving models and lower compute costs support commercial autonomy in transport and defense.", "Tesla, Mobileye, Aurora", "Waabi, Shield AI"),
    (8, "AI Cybersecurity", "AI increases attack volume while creating new identity, model, and data-protection requirements.", "CrowdStrike, Palo Alto, Cloudflare", "Wiz, HiddenLayer"),
    (9, "Edge AI", "On-device inference reduces latency, bandwidth use, and privacy exposure.", "Qualcomm, Arm, Apple", "Hailo, SiMa.ai"),
    (10, "AI Healthcare", "Multimodal clinical data can improve diagnostics, discovery, and operational efficiency.", "Tempus AI, GE HealthCare, Illumina", "Owkin, PathAI"),
]
DEMAND_DRIVERS = [{"rank": r, "area": a, "why": w, "public_companies": p, "emerging_companies": e}
                  for r, a, w, p, e in DEMAND_DRIVERS]

BIOTECH_LEADERS_RAW = [
    ("Vertex Pharmaceuticals", "VRTX", "Rare Disease / Precision Medicine", "TRIKAFTA; CASGEVY", "Pain, kidney disease, cell therapy"),
    ("Sarepta Therapeutics", "SRPT", "Rare Disease / Gene Therapy", "Duchenne muscular dystrophy therapies", "Gene therapy and RNA medicines"),
    ("Regeneron", "REGN", "Antibodies / Genetics", "EYLEA; Dupixent", "Oncology, immunology, genetic medicines"),
    ("Alnylam Pharmaceuticals", "ALNY", "RNA Interference", "ONPATTRO; AMVUTTRA", "Cardiometabolic and rare disease"),
    ("BioMarin Pharmaceutical", "BMRN", "Rare Disease", "VOXZOGO; enzyme therapies", "Genetic disease programs"),
    ("Ultragenyx Pharmaceutical", "RARE", "Rare Disease / Gene Therapy", "Multiple metabolic disease therapies", "Gene therapy and metabolic disease"),
    ("argenx", "ARGX", "Immunology", "VYVGART", "Broad antibody-fragment indication expansion"),
    ("Ionis Pharmaceuticals", "IONS", "RNA Therapeutics", "RNA-targeted medicines", "Neurology and cardiometabolic disease"),
]
BIOTECH_LEADERS = [{"company": c, "ticker": t, "sector": s, "proven_therapy": p, "pipeline": q,
                    "market_cap": "Large Cap" if t in ("VRTX", "REGN", "ALNY", "ARGX") else "Mid Cap", "growth_potential": "High"}
                   for c, t, s, p, q in BIOTECH_LEADERS_RAW]

BIOTECH_EMERGING_RAW = [
    (1, "CRISPR Therapeutics", "CRISPR gene editing", "Hemoglobinopathies; oncology", "Commercial execution and pipeline data", "Mid Cap", "High", "High"),
    (2, "Intellia Therapeutics", "In vivo CRISPR", "ATTR; hereditary angioedema", "Late-stage clinical readouts", "Mid Cap", "High", "High"),
    (3, "Beam Therapeutics", "Base editing", "Hematology; genetic disease", "Clinical proof-of-concept data", "Small Cap", "High", "High"),
    (4, "Prime Medicine", "Prime editing", "Chronic granulomatous disease", "Early clinical updates", "Small Cap", "High", "High"),
    (5, "Krystal Biotech", "Redosable gene therapy", "Dermatologic and respiratory disease", "Launch execution and label expansion", "Mid Cap", "High", "Medium"),
    (6, "Rocket Pharmaceuticals", "AAV gene therapy", "Danon disease; rare disorders", "Regulatory and pivotal milestones", "Small Cap", "High", "High"),
    (7, "Stoke Therapeutics", "RNA splicing", "Dravet syndrome", "Dose and durability updates", "Small Cap", "High", "High"),
    (8, "Scholar Rock", "Growth-factor biology", "Spinal muscular atrophy; obesity", "Regulatory and launch preparation", "Mid Cap", "High", "High"),
    (9, "Maze Therapeutics", "Human genetics platform", "Kidney and metabolic disease", "Phase 2 clinical data", "Small Cap", "High", "High"),
    (10, "Metagenomi", "Metagenomics-derived editing", "Genetic diseases", "IND and partnership progress", "Small Cap", "High", "High"),
    (11, "Generate Biomedicines", "Generative protein design", "Antibodies and therapeutic proteins", "Clinical and partnership updates", "Private", "High", "High"),
    (12, "ProQR Therapeutics", "RNA editing", "Cholestatic and genetic disease", "Clinical trial initiation and data", "Small Cap", "High", "High"),
]
BIOTECH_EMERGING = [{"rank": r, "company": c, "technology": t, "sector": t, "lead_programs": p,
                     "catalysts": k, "market_cap": m, "growth_potential": g, "risk": risk}
                    for r, c, t, p, k, m, g, risk in BIOTECH_EMERGING_RAW]

AI_WATCH = [
    ("Astera Labs", "ALAB", "Data-Center Connectivity", "AI connectivity content grows with cluster complexity.", "Product ramps and hyperscaler deployments", "Mid Cap", "High", "Medium"),
    ("Tempus AI", "TEM", "AI Healthcare", "Proprietary clinical data supports diagnostics and AI applications.", "Clinical adoption and data partnerships", "Mid Cap", "High", "High"),
    ("Aurora Innovation", "AUR", "Autonomous Systems", "Commercial autonomous trucking offers asymmetric platform potential.", "Driverless route and fleet expansion", "Mid Cap", "High", "High"),
    ("Rubrik", "RBRK", "AI Data Security", "Cyber-resilience demand rises with AI-generated threats.", "Subscription growth and platform expansion", "Mid Cap", "High", "Medium"),
    ("Oklo", "OKLO", "AI Energy", "Advanced nuclear could serve data-center baseload demand.", "Licensing and customer agreements", "Mid Cap", "High", "High"),
    ("Serve Robotics", "SERV", "Robotics", "Last-mile autonomy offers a focused real-world AI deployment.", "Fleet expansion and unit economics", "Small Cap", "High", "High"),
    ("Innodata", "INOD", "AI Data Infrastructure", "Complex training-data services benefit from model quality requirements.", "Customer diversification and margin growth", "Small Cap", "High", "High"),
]
BIOTECH_WATCH = [
    ("Beam Therapeutics", "BEAM", "Base Editing", "Differentiated precision-editing platform with multiple shots on goal.", "Clinical proof-of-concept readouts", "Small Cap", "High", "High"),
    ("Intellia Therapeutics", "NTLA", "In Vivo Gene Editing", "Systemic one-time editing could validate a broad modality.", "Late-stage HAE and ATTR updates", "Mid Cap", "High", "High"),
    ("Stoke Therapeutics", "STOK", "RNA Medicines", "RNA splicing may restore protein expression in severe genetic disease.", "Dravet durability and pivotal planning", "Small Cap", "High", "High"),
    ("Rocket Pharmaceuticals", "RCKT", "Gene Therapy", "Late-stage rare-disease assets address substantial unmet need.", "Regulatory milestones", "Small Cap", "High", "High"),
    ("Maze Therapeutics", "MAZE", "Human Genetics", "Genetically validated targets may improve drug-development odds.", "Phase 2 kidney data", "Small Cap", "High", "High"),
    ("Scholar Rock", "SRRK", "Muscle Biology", "Muscle-targeted biology spans neuromuscular disease and obesity.", "Regulatory progress and obesity data", "Mid Cap", "High", "High"),
    ("ProQR Therapeutics", "PRQR", "RNA Editing", "Programmable RNA editing could offer repeatable, reversible correction.", "First clinical data and partnerships", "Small Cap", "High", "High"),
]


def watch_rows(values):
    return [{"company": c, "ticker": t, "sector": s, "why": w, "catalyst": k, "market_cap": m,
             "growth_potential": g, "risk": r} for c, t, s, w, k, m, g, r in values]


MONTHLY_PICKS = {
    "ai": [
        {"rank": 1, "company": "NVIDIA", "thesis": "Full-stack leadership in accelerated computing.", "catalyst": "New architecture ramps and cloud capex", "opportunity": "Expanding training, inference, and enterprise AI", "risk": "Medium"},
        {"rank": 2, "company": "Broadcom", "thesis": "Networking plus custom silicon captures two AI bottlenecks.", "catalyst": "Hyperscaler accelerator ramps", "opportunity": "Custom AI compute and scale-out networking", "risk": "Medium"},
        {"rank": 3, "company": "Vertiv", "thesis": "Power and thermal density make cooling mission-critical.", "catalyst": "Data-center backlog conversion", "opportunity": "Long-cycle buildout of high-density facilities", "risk": "Medium"},
        {"rank": 4, "company": "Astera Labs", "thesis": "Connectivity content rises with heterogeneous AI systems.", "catalyst": "New product deployments", "opportunity": "Growing share of AI server connectivity", "risk": "High"},
        {"rank": 5, "company": "Tempus AI", "thesis": "Clinical data flywheel supports diagnostics and AI products.", "catalyst": "Volume growth and partnerships", "opportunity": "AI-native precision medicine platform", "risk": "High"},
    ],
    "biotech": [
        {"rank": 1, "company": "Vertex Pharmaceuticals", "thesis": "Durable rare-disease franchise funds a diversified pipeline.", "catalyst": "Launch execution and pipeline readouts", "opportunity": "Expansion beyond cystic fibrosis", "risk": "Low"},
        {"rank": 2, "company": "Alnylam Pharmaceuticals", "thesis": "Validated RNAi platform is expanding into large indications.", "catalyst": "Cardiometabolic launch execution", "opportunity": "Broad repeatable RNAi pipeline", "risk": "Medium"},
        {"rank": 3, "company": "Intellia Therapeutics", "thesis": "Late-stage in vivo editing may validate one-time systemic therapy.", "catalyst": "Clinical and regulatory updates", "opportunity": "Reusable in vivo CRISPR platform", "risk": "High"},
        {"rank": 4, "company": "Krystal Biotech", "thesis": "Commercial validation supports a redosable gene-therapy platform.", "catalyst": "Launch growth and pipeline data", "opportunity": "Expansion across skin, lung, and rare disease", "risk": "Medium"},
        {"rank": 5, "company": "Stoke Therapeutics", "thesis": "Protein-restoration approach could transform Dravet treatment.", "catalyst": "Durability and pivotal-path updates", "opportunity": "Platform across haploinsufficient diseases", "risk": "High"},
    ],
}

MARKETS = {"^GSPC": ("^spx", "S&P 500"), "^IXIC": ("^ndq", "Nasdaq"),
           "^DJI": ("^dji", "Dow Jones"), "^RUT": ("^rty", "Russell 2000")}


def fetch(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read()


def news_url(query):
    return "https://news.google.com/search?q=" + urllib.parse.quote(query)


def rss_items(query, limit=5):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en"
    try:
        root = ET.fromstring(fetch(url))
        return [{"title": item.findtext("title", "Latest coverage"), "url": item.findtext("link", news_url(query)),
                 "date": item.findtext("pubDate", "")} for item in root.findall(".//item")[:limit]]
    except Exception as exc:
        print(f"RSS unavailable for {query}: {exc}")
        return []


def market_history(yahoo_symbol, stooq_symbol):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(yahoo_symbol, safe="") + "?range=1mo&interval=1d"
        payload = json.loads(fetch(url, timeout=12))
        return [float(v) for v in payload["chart"]["result"][0]["indicators"]["quote"][0]["close"] if v is not None]
    except Exception:
        try:
            end = datetime.now(timezone.utc).date(); start = end - timedelta(days=50)
            url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(stooq_symbol)}&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
            rows = csv.DictReader(io.StringIO(fetch(url).decode("utf-8")))
            return [float(row["Close"]) for row in rows if row.get("Close") not in (None, "", "N/D")]
        except Exception as exc:
            print(f"Market data unavailable for {yahoo_symbol}: {exc}")
            return []


def percent_change(current, previous):
    return round((current / previous - 1) * 100, 2) if previous else 0


def prior_data():
    try:
        return json.loads(OUTPUT.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def summarize(headlines, label):
    if not headlines:
        return f"No new {label} headlines were found in today's public feeds. Monitoring continues."
    clean = [re.sub(r"\s+-\s+[^-]+$", "", item["title"]).strip() for item in headlines[:3]]
    return "Key developments: " + "; ".join(clean) + "."


def build():
    previous = prior_data()
    ai_news = rss_items("artificial intelligence infrastructure chips data center when:1d", 6)
    biotech_news = rss_items("biotechnology rare disease clinical trial when:1d", 6)
    fda_news = rss_items("FDA approval orphan drug fast track rare disease when:7d", 8)
    market_news = rss_items("US stock market Nasdaq S&P 500 today when:1d", 4)

    old_markets = {item["name"]: item for item in previous.get("markets", [])}
    markets = []
    for yahoo_symbol, (stooq_symbol, name) in MARKETS.items():
        closes = market_history(yahoo_symbol, stooq_symbol)
        if closes:
            current = closes[-1]
            markets.append({"name": name, "value": f"{current:,.2f}", "daily": percent_change(current, closes[-2] if len(closes) > 1 else current),
                            "weekly": percent_change(current, closes[-6] if len(closes) > 5 else closes[0]),
                            "monthly": percent_change(current, closes[-22] if len(closes) > 21 else closes[0])})
        else:
            markets.append(old_markets.get(name, {"name": name, "value": "N/A", "daily": 0, "weekly": 0, "monthly": 0}))

    if any(item["value"] != "N/A" for item in markets):
        best = max(markets, key=lambda item: item["daily"]); worst = min(markets, key=lambda item: item["daily"])
        market_movers = f'{best["name"]} led tracked indexes at {best["daily"]:+.2f}% today; {worst["name"]} was weakest at {worst["daily"]:+.2f}%. ' + summarize(market_news, "market")
    else:
        market_movers = "Price feeds are temporarily unavailable. " + summarize(market_news, "market")

    fda = [{"company": "See source", "product": "See source", "indication": "See source",
            "event": re.sub(r"\s+-\s+[^-]+$", "", item["title"]), "date": item.get("date", "")[:16], "url": item["url"]}
           for item in fda_news] or previous.get("fda", [])
    takeaways = [item["title"] for item in (ai_news[:2] + biotech_news[:2] + fda_news[:2] + market_news[:1])]
    if not takeaways:
        takeaways = previous.get("takeaways", ["Daily source monitoring is active."])

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summaries": {"ai": summarize(ai_news, "AI"), "biotech": summarize(biotech_news, "biotech"),
                      "market": summarize(market_news, "market"), "market_movers": market_movers},
        "takeaways": takeaways[:8],
        "ai": {"infrastructure_leaders": AI_INFRASTRUCTURE, "platform_leaders": AI_PLATFORMS,
               "emerging": AI_EMERGING, "demand_drivers": DEMAND_DRIVERS},
        "biotech": {"leaders": BIOTECH_LEADERS, "emerging": BIOTECH_EMERGING},
        "watchlists": {"ai": watch_rows(AI_WATCH), "biotech": watch_rows(BIOTECH_WATCH)},
        "monthly_picks": MONTHLY_PICKS, "fda": fda, "markets": markets,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")
    print(f"Updated {OUTPUT}")


if __name__ == "__main__":
    build()
