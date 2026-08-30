#!/usr/bin/env python3
"""Refresh the curated GeneDr News & Invest dashboard from public feeds."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import ssl
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    from .ai_reasoning_discovery import build_ai_reasoning_discovery
    from .company_quality import build_company_quality_layer
    from .dashboard_commentary import (annotate_high_conviction, annotate_watchlists,
                                       build_news_commentary, build_radar_commentary)
    from .entry_timing import build_entry_timing_layer, calculate_entry_inputs
except ImportError:
    from ai_reasoning_discovery import build_ai_reasoning_discovery
    from company_quality import build_company_quality_layer
    from dashboard_commentary import (annotate_high_conviction, annotate_watchlists,
                                      build_news_commentary, build_radar_commentary)
    from entry_timing import build_entry_timing_layer, calculate_entry_inputs

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news-dashboard.json"
USER_AGENT = "GeneDrNetwork-Daily-Dashboard/2.0 (+https://genedrnetwork.github.io/)"
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


def company_registry_record(company, ticker, aliases=(), exchange="", listing_status="Public", domain="both"):
    return {"company": company, "ticker": ticker, "aliases": tuple(dict.fromkeys((company.lower(), *aliases))),
            "exchange": exchange, "listing_status": listing_status, "domain": domain}


COMPANY_REGISTRY = [
    company_registry_record("NVIDIA", "NVDA", ("nvidia",), domain="ai"),
    company_registry_record("AMD", "AMD", ("advanced micro devices", "amd"), domain="ai"),
    company_registry_record("TSMC", "TSM", ("taiwan semiconductor", "tsmc"), domain="ai"),
    company_registry_record("Broadcom", "AVGO", domain="ai"), company_registry_record("Micron", "MU", domain="ai"),
    company_registry_record("Arista Networks", "ANET", ("arista",), domain="ai"),
    company_registry_record("Vertiv", "VRT", domain="ai"), company_registry_record("Eaton", "ETN", domain="ai"),
    company_registry_record("Dell Technologies", "DELL", ("dell",), domain="ai"),
    company_registry_record("Super Micro Computer", "SMCI", ("supermicro", "super micro"), domain="ai"),
    company_registry_record("CoreWeave", "CRWV", domain="ai"), company_registry_record("Microsoft", "MSFT", domain="ai"),
    company_registry_record("Alphabet", "GOOGL", ("google", "google cloud"), domain="ai"),
    company_registry_record("Amazon", "AMZN", ("amazon web services", "aws"), domain="ai"),
    company_registry_record("Meta Platforms", "META", ("meta",), domain="ai"),
    company_registry_record("Oracle", "ORCL", domain="ai"), company_registry_record("Intel", "INTC", domain="ai"),
    company_registry_record("Qualcomm", "QCOM", domain="ai"), company_registry_record("Arm Holdings", "ARM", ("arm",), domain="ai"),
    company_registry_record("Apple", "AAPL", domain="ai"), company_registry_record("Cisco", "CSCO", domain="ai"),
    company_registry_record("Marvell Technology", "MRVL", ("marvell",), domain="ai"),
    company_registry_record("Applied Materials", "AMAT", domain="ai"), company_registry_record("CBRE", "CBRE", domain="ai"),
    company_registry_record("S&P Global", "SPGI", ("s&p global", "s&p global ratings"), domain="ai"),
    company_registry_record("ASML", "ASML", domain="ai"), company_registry_record("Equinix", "EQIX", domain="ai"),
    company_registry_record("Constellation Energy", "CEG", ("constellation",), domain="ai"),
    company_registry_record("GE Vernova", "GEV", domain="ai"), company_registry_record("Tesla", "TSLA", domain="ai"),
    company_registry_record("ABB", "ABB", domain="ai"), company_registry_record("Teradyne", "TER", domain="ai"),
    company_registry_record("Mobileye", "MBLY", domain="ai"), company_registry_record("CrowdStrike", "CRWD", domain="ai"),
    company_registry_record("Palo Alto Networks", "PANW", ("palo alto",), domain="ai"),
    company_registry_record("Cloudflare", "NET", domain="ai"), company_registry_record("Samsara", "IOT", domain="ai"),
    company_registry_record("Rubrik", "RBRK", domain="ai"), company_registry_record("Oklo", "OKLO", domain="ai"),
    company_registry_record("Astera Labs", "ALAB", domain="ai"), company_registry_record("Tempus AI", "TEM", domain="both"),
    company_registry_record("Aurora Innovation", "AUR", ("aurora",), domain="ai"),
    company_registry_record("GE HealthCare", "GEHC", domain="both"), company_registry_record("Illumina", "ILMN", domain="both"),
    company_registry_record("IREN", "IREN", domain="ai"),
    company_registry_record("Infineon Technologies", "IFX:XETRA", ("infineon",), exchange="XETRA", domain="ai"),
    company_registry_record("SK hynix", "000660:KRX", ("sk hynix",), exchange="KRX", domain="ai"),
    company_registry_record("OpenAI", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Anthropic", "Private", listing_status="Private", domain="ai"),
    company_registry_record("xAI", "Private", ("xai",), listing_status="Private", domain="ai"),
    company_registry_record("SpaceX", "Private", ("spacex", "spacexai"), listing_status="Private", domain="ai"),
    company_registry_record("Cerebras Systems", "Private", ("cerebras",), listing_status="Private", domain="ai"),
    company_registry_record("Groq", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Figure AI", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Scale AI", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Physical Intelligence", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Tenstorrent", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Celestial AI", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Crusoe", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Fervo Energy", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Form Energy", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Lightmatter", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Waabi", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Shield AI", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Wiz", "Private", listing_status="Private", domain="ai"),
    company_registry_record("HiddenLayer", "Private", listing_status="Private", domain="ai"),
    company_registry_record("Hailo", "Private", listing_status="Private", domain="ai"),
    company_registry_record("SiMa.ai", "Private", ("sima.ai",), listing_status="Private", domain="ai"),
    company_registry_record("Owkin", "Private", listing_status="Private", domain="both"),
    company_registry_record("PathAI", "Private", listing_status="Private", domain="both"),
    company_registry_record("Vertex Pharmaceuticals", "VRTX", ("vertex",), domain="biotech"),
    company_registry_record("Sarepta Therapeutics", "SRPT", ("sarepta",), domain="biotech"),
    company_registry_record("Regeneron", "REGN", domain="biotech"),
    company_registry_record("Alnylam Pharmaceuticals", "ALNY", ("alnylam",), domain="biotech"),
    company_registry_record("BioMarin Pharmaceutical", "BMRN", ("biomarin",), domain="biotech"),
    company_registry_record("Ultragenyx Pharmaceutical", "RARE", ("ultragenyx",), domain="biotech"),
    company_registry_record("argenx", "ARGX", domain="biotech"), company_registry_record("Ionis Pharmaceuticals", "IONS", ("ionis",), domain="biotech"),
    company_registry_record("CRISPR Therapeutics", "CRSP", domain="biotech"),
    company_registry_record("Intellia Therapeutics", "NTLA", ("intellia",), domain="biotech"),
    company_registry_record("Beam Therapeutics", "BEAM", domain="biotech"), company_registry_record("Prime Medicine", "PRME", domain="biotech"),
    company_registry_record("Krystal Biotech", "KRYS", domain="biotech"), company_registry_record("Rocket Pharmaceuticals", "RCKT", domain="biotech"),
    company_registry_record("Stoke Therapeutics", "STOK", domain="biotech"), company_registry_record("Scholar Rock", "SRRK", domain="biotech"),
    company_registry_record("Maze Therapeutics", "MAZE", domain="biotech"), company_registry_record("Metagenomi", "MGX", domain="biotech"),
    company_registry_record("ProQR Therapeutics", "PRQR", ("proqr",), domain="biotech"),
    company_registry_record("Moderna", "MRNA", domain="biotech"), company_registry_record("Cytokinetics", "CYTK", domain="biotech"),
    company_registry_record("Implantica", "IMP A SDB:STO", exchange="Nasdaq Stockholm", domain="biotech"),
    company_registry_record("Roche", "ROP:SIX", ("genentech",), exchange="SIX", domain="biotech"),
    company_registry_record("Jazz Pharmaceuticals", "JAZZ", ("jazz",), domain="biotech"),
    company_registry_record("Biohaven", "BHVN", domain="biotech"),
    company_registry_record("SK Biopharmaceuticals", "326030:KRX", ("sk biopharma", "sk biopharmaceuticals"), exchange="KRX", domain="biotech"),
    company_registry_record("Biogen", "BIIB", domain="biotech"), company_registry_record("Gilead Sciences", "GILD", ("gilead",), domain="biotech"),
    company_registry_record("Amgen", "AMGN", domain="biotech"), company_registry_record("Eli Lilly", "LLY", domain="biotech"),
    company_registry_record("Novo Nordisk", "NVO", domain="biotech"), company_registry_record("Merck", "MRK", domain="biotech"),
    company_registry_record("Pfizer", "PFE", domain="biotech"), company_registry_record("Bristol Myers Squibb", "BMY", domain="biotech"),
    company_registry_record("AstraZeneca", "AZN", domain="biotech"), company_registry_record("Sanofi", "SNY", domain="biotech"),
    company_registry_record("Novartis", "NVS", domain="biotech"), company_registry_record("Generate Biomedicines", "Private", listing_status="Private", domain="biotech"),
    company_registry_record("Cellares", "Private", listing_status="Private", domain="biotech"),
    company_registry_record("Sentivera", "Private", listing_status="Private", domain="biotech"),
    company_registry_record("U.S. Food and Drug Administration", "N/A", ("food and drug administration", "fda"), listing_status="Non-public", domain="both"),
    company_registry_record("National Institutes of Health", "N/A", ("nih",), listing_status="Non-public", domain="both"),
    company_registry_record("Jiangsu provincial government", "N/A", ("china's jiangsu", "jiangsu provincial government"), listing_status="Non-public", domain="biotech"),
]

COMPANY_ALIAS_INDEX = {alias: record for record in COMPANY_REGISTRY for alias in record["aliases"]}
COMPANY_TICKER_INDEX = {record["ticker"].upper(): record for record in COMPANY_REGISTRY if record["ticker"] not in ("Private", "N/A")}


def company_identity(company, ticker=None):
    name = (company or "").strip()
    supplied_ticker = (ticker or "").strip()
    record = COMPANY_ALIAS_INDEX.get(name.lower()) or COMPANY_TICKER_INDEX.get(supplied_ticker.upper())
    if record:
        return {key: record[key] for key in ("company", "ticker", "exchange", "listing_status")}
    if any(term in name.lower() for term in ("university", "government", "ministry", "regulator", "administration")):
        return {"company": name or "Organization not identified", "ticker": "N/A", "exchange": "", "listing_status": "Non-public"}
    if supplied_ticker in ("Private", "N/A"):
        return {"company": name or "Company not identified", "ticker": supplied_ticker, "exchange": "",
                "listing_status": "Private" if supplied_ticker == "Private" else "Non-public"}
    return {"company": name or "Missing / not established", "ticker": supplied_ticker or "Missing",
            "exchange": "", "listing_status": "Public" if supplied_ticker and supplied_ticker != "Missing" else "Unknown"}


def company_identities_in_text(text, domain=None):
    lowered = text.lower()
    matches = []
    for alias, record in COMPANY_ALIAS_INDEX.items():
        if domain and record["domain"] not in (domain, "both"):
            continue
        match = re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered)
        if match:
            matches.append((match.start(), -len(alias), record))
    identities = []
    seen = set()
    for _, _, record in sorted(matches):
        if record["company"] in seen:
            continue
        seen.add(record["company"])
        identities.append({key: record[key] for key in ("company", "ticker", "exchange", "listing_status")})
    return identities


def company_identity_fields(text, company=None, ticker=None, domain=None):
    identities = company_identities_in_text(text, domain)
    if not identities:
        organization = re.search(r"\b([A-Z][A-Za-z&.' -]{2,70}?(?:University|Administration|Ministry|Government))\b", text)
        if organization:
            identities.append(company_identity(organization.group(1)))
    investable = next((item for item in identities if item["ticker"] != "N/A"), None)
    if investable and identities[0] is not investable:
        identities.remove(investable)
        identities.insert(0, investable)
    fallback = company_identity(company, ticker) if company or ticker else None
    if fallback and not fallback["company"].startswith("Missing") and fallback["company"] not in {item["company"] for item in identities}:
        identities.insert(0, fallback)
    primary = identities[0] if identities else fallback or company_identity("", "")
    related = identities[1:]
    return {**primary, "related_companies": [item["company"] for item in related],
            "related_tickers": [item["ticker"] for item in related], "company_identities": identities}


def normalize_news_company_story(story, domain):
    clean = dict(story)
    evidence_text = " ".join((clean.get("headline", ""), clean.get("new_information", ""),
                              clean.get("company", ""), " ".join(clean.get("related_companies", []))))
    clean.update(company_identity_fields(evidence_text, clean.get("company"), clean.get("ticker"), domain))
    return clean


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

BIOTECH_RADAR_WEIGHTS = {
    "scientific_evidence": 30,
    "catalyst_impact_company_sensitivity": 25,
    "expectation_gap": 20,
    "sector_trend_capital_flow": 15,
    "timing_technicals": 10,
}
# Retained for compatibility with existing imports while the Radar uses the V1 factor model above.
CATALYST_WEIGHTS = BIOTECH_RADAR_WEIGHTS


def source(title, url, date):
    return {"title": title, "url": url, "date": date}


BIOTECH_CATALYSTS = [
    {
        "ticker": "NTLA", "company": "Intellia Therapeutics", "program": "lonvoguran ziclumeran (lonvo-z)", "indication": "Hereditary angioedema",
        "catalyst": "FDA acceptance of the lonvo-z BLA", "expected_timing": "Second half of 2026",
        "window_start": "2026-08-27", "window_end": "2026-12-31", "stage": "BLA submission / review",
        "why_important": "Acceptance would move a potentially first-in-class, one-time in vivo CRISPR therapy for HAE into FDA review.",
        "clinical_evidence": "Positive Phase 3 HAELO results were reported and published in the New England Journal of Medicine.",
        "previous_results": "The company reported positive pivotal HAELO results; this v1 source set does not independently reproduce the full endpoint tables.",
        "regulatory_status": "The company anticipates FDA acceptance of the BLA in the second half of 2026 and a potential U.S. launch in the first half of 2027.",
        "commercial_potential": "A provider survey cited by the company found high stated prescribing interest; actual price, penetration and addressable treated population remain unverified here.",
        "market_expectation": "Missing: no verified consensus probability, event-implied move, or valuation sensitivity is connected.",
        "positioning": "Missing: no dated short-interest, ownership-flow, or technical-setup dataset is connected.",
        "risks": "FDA filing acceptance is not approval; manufacturing, safety, durability and commercialization risks remain.",
        "watch_next": "BLA acceptance notice, review designation, PDUFA timing and any FDA requests.",
        "components": {
            "catalyst_importance": (25, "A pivotal regulatory filing acceptance can materially change approval probability."),
            "prior_evidence": (20, "Positive Phase 3 results support the filing."),
            "commercial_impact": (12, "One-time therapy in HAE has differentiated potential, but v1 lacks an independently verified revenue model."),
            "expectation_gap": (0, "Missing verified market-expectation data."),
            "positioning": (0, "Missing verified positioning and technical data."),
        },
        "sources": [
            source("Intellia Q2 2026 results", "https://ir.intelliatx.com/node/12826", "2026-08-06"),
            source("Intellia full-year 2025 results", "https://ir.intelliatx.com/node/12501", "2026-02-26"),
        ],
    },
    {
        "ticker": "BEAM", "company": "Beam Therapeutics", "program": "BEAM-302", "indication": "Alpha-1 antitrypsin deficiency",
        "catalyst": "Updated Phase 1/2 BEAM-302 data at ERS", "expected_timing": "September 8, 2026",
        "window_start": "2026-09-08", "window_end": "2026-09-08", "stage": "Phase 1/2; pivotal cohort dosing",
        "why_important": "The update may further validate in vivo base editing and the accelerated pivotal path in alpha-1 antitrypsin deficiency.",
        "clinical_evidence": "Earlier clinical data showed durable correction of the disease-causing protein phenotype and reduction of mutant Z-AAT.",
        "previous_results": "At 60 mg, the company reported mean steady-state total AAT of 16.1 µM, all patients above the 11 µM protective threshold, 94% corrected M-AAT and 84% mutant Z-AAT reduction.",
        "regulatory_status": "A pivotal cohort is dosing under an accelerated development path; the program is not approved.",
        "commercial_potential": "The company estimates about 100,000 U.S. PiZZ patients and low diagnosis rates, with substantial unmet need.",
        "market_expectation": "Missing: no verified consensus expectations or options-implied event move is connected.",
        "positioning": "Missing: no dated short-interest, fund-flow, or technical-setup dataset is connected.",
        "risks": "Small early cohorts, durability, liver safety, dose selection and translation into clinical outcomes may invalidate the thesis.",
        "watch_next": "Dose-response, durability, safety, pivotal-cohort design and regulator-aligned endpoints.",
        "components": {
            "catalyst_importance": (20, "Registrational-enabling clinical data can alter program and platform probability."),
            "prior_evidence": (16, "Positive human proof-of-concept exists, but evidence remains early-stage and cohort sizes are limited."),
            "commercial_impact": (12, "Large rare-disease population and differentiated one-time correction are documented; pricing and penetration are not."),
            "expectation_gap": (0, "Missing verified market-expectation data."),
            "positioning": (0, "Missing verified positioning and technical data."),
        },
        "sources": [
            source("Beam ERS presentation announcement", "https://investors.beamtx.com/news-releases/news-release-details/beam-therapeutics-present-updated-data-phase-12-trial-beam-302", "2026-07-23"),
            source("Beam updated BEAM-302 clinical data", "https://investors.beamtx.com/news-releases/news-release-details/beam-therapeutics-announces-compelling-updated-clinical-data", "2026-03-25"),
            source("Beam Q2 2026 results", "https://investors.beamtx.com/news-releases/news-release-details/beam-therapeutics-reports-second-quarter-2026-financial-results", "2026-08-04"),
        ],
    },
    {
        "ticker": "MAZE", "company": "Maze Therapeutics", "program": "MZE829", "indication": "APOL1-mediated kidney disease",
        "catalyst": "Additional HORIZON Phase 2 cohort data", "expected_timing": "Late 2026 / early 2027",
        "window_start": "2026-11-01", "window_end": "2027-02-27", "stage": "Phase 2",
        "why_important": "Additional cohorts may confirm a genetically defined response signal and support pivotal development in APOL1-mediated kidney disease.",
        "clinical_evidence": "The company reported positive Phase 2 proof-of-concept results with proteinuria reductions in broad AMKD and severe FSGS cohorts.",
        "previous_results": "Mean proteinuria reduction was reported as 35.6% at week 12 in broad AMKD and 61.8% in severe FSGS, with no serious or severe treatment-related adverse events.",
        "regulatory_status": "The company is preparing for a potential pivotal study in the first half of 2027; MZE829 is not approved.",
        "commercial_potential": "The company estimates more than one million U.S. patients with APOL1-mediated kidney disease.",
        "market_expectation": "Missing: no verified consensus expectations or valuation sensitivity is connected.",
        "positioning": "Missing: no dated short-interest or technical-setup dataset is connected.",
        "risks": "Small cohorts, open-label interpretation, biomarker-to-outcome translation and safety in larger populations remain risks.",
        "watch_next": "Consistency across cohorts, durability, safety, subgroup response and pivotal-study design.",
        "components": {
            "catalyst_importance": (20, "Confirmatory Phase 2 data can enable pivotal development."),
            "prior_evidence": (16, "Positive human proof-of-concept exists, but cohort sizes are still limited."),
            "commercial_impact": (12, "A large genetically defined population is cited, but pricing and penetration are not independently modeled."),
            "expectation_gap": (0, "Missing verified market-expectation data."),
            "positioning": (0, "Missing verified positioning and technical data."),
        },
        "sources": [
            source("Maze Q2 2026 results", "https://ir.mazetx.com/news-releases/news-release-details/maze-therapeutics-reports-second-quarter-2026-financial-results", "2026-08-11"),
            source("Maze Q1 2026 results", "https://ir.mazetx.com/news-releases/news-release-details/maze-therapeutics-reports-first-quarter-2026-financial-results", "2026-05-12"),
        ],
    },
    {
        "ticker": "STOK", "company": "Stoke Therapeutics", "program": "zorevunersen", "indication": "Dravet syndrome",
        "catalyst": "FDA pre-NDA meeting and regulatory-path update", "expected_timing": "Second half of 2026",
        "window_start": "2026-08-27", "window_end": "2026-12-31", "stage": "Phase 3 / pre-NDA",
        "why_important": "A constructive pre-NDA outcome could clarify the rolling NDA path for a potential disease-modifying Dravet syndrome therapy.",
        "clinical_evidence": "The company reports supportive safety and efficacy across four years of follow-up; a Phase 3 readout is expected in 2027.",
        "previous_results": "Long-term clinical evidence is described as supportive by the company; full patient-level evidence is not reproduced in this v1 dataset.",
        "regulatory_status": "Pre-NDA meeting planned for the second half of 2026 and rolling NDA submission planned for the first quarter of 2027.",
        "commercial_potential": "Potential first-in-class disease-modifying treatment in a severe rare epilepsy; a verified revenue model is missing.",
        "market_expectation": "Missing: no verified probability-weighted consensus or event-implied move is connected.",
        "positioning": "Missing: no dated short-interest, ownership-flow, or technical-setup dataset is connected.",
        "risks": "Meeting outcomes may not be disclosed in detail; FDA may require Phase 3 data or additional evidence before approval.",
        "watch_next": "Company disclosure after the pre-NDA meeting and confirmation of the rolling NDA plan.",
        "components": {
            "catalyst_importance": (20, "Regulatory-path clarification can materially change time-to-filing and approval probability."),
            "prior_evidence": (16, "Multi-year human evidence is supportive, but pivotal confirmation remains pending."),
            "commercial_impact": (12, "Potential disease modification in a severe rare disease is meaningful; v1 lacks a verified revenue model."),
            "expectation_gap": (0, "Missing verified market-expectation data."),
            "positioning": (0, "Missing verified positioning and technical data."),
        },
        "sources": [source("Stoke Q2 2026 results", "https://investor.stoketherapeutics.com/news-releases/news-release-details/stoke-therapeutics-announces-second-quarter-2026-financial/", "2026-08-03")],
    },
    {
        "ticker": "PRQR", "company": "ProQR Therapeutics", "program": "AX-0810 / AX-0811", "indication": "Missing: program-level indication is not specified in the connected catalyst record",
        "catalyst": "Full AX-0810 and initial AX-0811 Phase 1 data", "expected_timing": "By year-end 2026",
        "window_start": "2026-10-01", "window_end": "2026-12-31", "stage": "Phase 1",
        "why_important": "The readout could strengthen the first clinical validation of ProQR's Axiomer RNA-editing platform and show next-generation activity.",
        "clinical_evidence": "Initial AX-0810 data showed target engagement, up to eight-fold bile-acid increases, favorable reported safety and no serious adverse events or pruritus.",
        "previous_results": "Initial Phase 1 target engagement supports platform activity, but clinical efficacy and larger-cohort safety remain unproven.",
        "regulatory_status": "AX-0811 CTA was submitted in July 2026; both programs remain investigational.",
        "commercial_potential": "Platform validation could affect multiple programs, but indication-level pricing, population and penetration are not established in v1.",
        "market_expectation": "Missing: no verified consensus, probability-weighted valuation, or event-implied move is connected.",
        "positioning": "Missing: no dated short-interest, ownership-flow, or technical-setup dataset is connected.",
        "risks": "Early target engagement may not translate into clinical benefit; dose, durability, safety and platform reproducibility remain uncertain.",
        "watch_next": "Editing level, dose-response, durability, safety and evidence that AX-0811 improves potency or duration.",
        "components": {
            "catalyst_importance": (15, "Early clinical platform validation may change valuation but is not registrational."),
            "prior_evidence": (12, "Initial human target engagement exists; clinical efficacy is not established."),
            "commercial_impact": (8, "Platform read-through is meaningful, but commercial inputs are largely missing."),
            "expectation_gap": (0, "Missing verified market-expectation data."),
            "positioning": (0, "Missing verified positioning and technical data."),
        },
        "sources": [
            source("ProQR Q2 2026 results", "https://www.proqr.com/press-releases/proqr-announces-second-quarter-2026-operating-and-financial-results", "2026-08-13"),
            source("ProQR positive AX-0810 data", "https://www.proqr.com/press-releases/proqr-announces-positive-phase-1-target-engagement-data-for-ax-0810-establishing-first-clinical-validation-of-the-axiomer-rna-editing-platform", "2026-06-25"),
        ],
    },
    {
        "ticker": "KRYS", "company": "Krystal Biotech", "program": "KB803", "indication": "Corneal abrasions in dystrophic epidermolysis bullosa",
        "catalyst": "IOLITE registrational top-line results", "expected_timing": "Fourth quarter 2026",
        "window_start": "2026-10-01", "window_end": "2026-12-31", "stage": "Registrational study",
        "why_important": "A registrational readout could establish a second ophthalmic use of the company's redosable gene-delivery platform in dystrophic epidermolysis bullosa.",
        "clinical_evidence": "Missing: the cited Q2 source confirms full enrollment but does not provide program-specific clinical efficacy results.",
        "previous_results": "Missing from the connected source set; no result is assumed.",
        "regulatory_status": "The IOLITE registrational study is fully enrolled; KB803 is not approved.",
        "commercial_potential": "Could treat or prevent corneal abrasions in DEB, but v1 lacks verified patient, pricing and penetration inputs.",
        "market_expectation": "Missing: no verified consensus expectations or event-implied move is connected.",
        "positioning": "Missing: no dated short-interest, ownership-flow, or technical-setup dataset is connected.",
        "risks": "No connected program-specific efficacy evidence; registrational endpoints, safety and regulatory acceptability remain uncertain.",
        "watch_next": "Top-line efficacy, safety, durability and regulatory next steps.",
        "components": {
            "catalyst_importance": (25, "A registrational top-line result can materially change approval probability."),
            "prior_evidence": (0, "Missing program-specific clinical evidence in the connected source set."),
            "commercial_impact": (8, "A meaningful rare-disease complication is addressed, but commercial inputs are missing."),
            "expectation_gap": (0, "Missing verified market-expectation data."),
            "positioning": (0, "Missing verified positioning and technical data."),
        },
        "sources": [source("Krystal Q2 2026 results", "https://ir.krystalbio.com/news-releases/news-release-details/krystal-biotech-announces-second-quarter-2026-financial-and", "2026-08-03")],
    },
]

MRNA_VALIDATION_CASE = {
    "ticker": "MRNA", "company": "Moderna", "program": "mRNA-1010 (mFLUSIVA)", "indication": "Seasonal influenza",
    "catalyst": "FDA PDUFA decision for mFLUSIVA", "expected_timing": "August 5, 2026",
    "window_start": "2026-08-05", "window_end": "2026-08-05", "stage": "BLA review",
    "why_important": "Approval would represent Moderna's fifth product and expand the commercial respiratory portfolio into seasonal influenza.",
    "clinical_evidence": "The amended BLA was accepted and the FDA recommendation was based on the Phase 3 program; the v1 cutoff source set does not reproduce all endpoint tables.",
    "previous_results": "A Phase 3 regulatory package supported the accepted amended BLA. No post-July 31 outcome information is used.",
    "regulatory_status": "FDA PDUFA date of August 5, 2026, as disclosed by July 31, 2026.",
    "commercial_potential": "A fifth approved product could broaden Moderna's respiratory franchise, but the v1 case has no independently verified product-level forecast.",
    "market_expectation": "Missing as of the cutoff: no verified consensus approval probability or event-implied move in the connected sources.",
    "positioning": "Missing as of the cutoff: no dated short-interest, ownership-flow, or technical-setup dataset is connected.",
    "risks": "Regulatory rejection or delay, label restrictions, competitive flu vaccines and commercial execution.",
    "watch_next": "FDA decision on August 5, 2026; outcome deliberately excluded from the retrospective input set.",
    "components": {
        "catalyst_importance": (25, "An FDA approval decision is a maximum-importance valuation catalyst."),
        "prior_evidence": (18, "An accepted BLA backed by Phase 3 evidence is strong, but full endpoint detail is not present in the connected cutoff sources."),
        "commercial_impact": (12, "Portfolio expansion is material, but a verified product forecast is missing."),
        "expectation_gap": (0, "Missing verified cutoff-date market-expectation data."),
        "positioning": (0, "Missing verified cutoff-date positioning and technical data."),
    },
    "sources": [
        source("Moderna Q2 2026 results", "https://investors.modernatx.com/quarterly-results", "2026-07-31"),
        source("Moderna June 2026 Form 10-Q", "https://www.sec.gov/Archives/edgar/data/1682852/000168285226000150/mrna-20260630.htm", "2026-07-31"),
    ],
}


def watch_rows(values):
    return [{"company": c, "ticker": t, "sector": s, "why": w, "catalyst": k, "market_cap": m,
             "growth_potential": g, "risk": r} for c, t, s, w, k, m, g, r in values]


def catalyst_classification(score):
    if score >= 85:
        return "High Priority"
    if score >= 70:
        return "Priority Watch"
    if score >= 55:
        return "Monitoring"
    return "Low Priority"


def timing_component(item, as_of):
    start = datetime.fromisoformat(item["window_start"]).date()
    end = datetime.fromisoformat(item["window_end"]).date()
    days_to_start = (start - as_of).days
    days_to_end = (end - as_of).days
    window_days = (end - start).days
    if days_to_end < 0 or days_to_start > 183:
        return 0, "Outside the forward six-month radar window.", True
    if start == end and 0 <= days_to_start <= 90:
        return 15, "Exact catalyst date is within 90 days.", False
    if window_days <= 92 and days_to_start <= 183:
        return 12, "A defined quarter or similarly narrow window falls within six months.", False
    return 10, "Company guidance places the catalyst within the forward six-month window, but not on a narrow date.", False


def biotech_radar_factor(key, label, weight, score, available_weight, rationale, sources, missing_fields=None):
    if score is not None and not 0 <= score <= weight:
        raise ValueError(f"{label} score {score} exceeds 0-{weight}")
    return {
        "key": key, "label": label, "weight": weight, "score": score,
        "available_weight": available_weight, "missing": available_weight == 0,
        "partial": 0 < available_weight < weight, "missing_fields": missing_fields or [],
        "rationale": rationale,
        "evidence": [] if available_weight == 0 else [
            {"title": entry["title"], "date": entry["date"], "url": entry["url"]} for entry in sources
        ],
    }


def biotech_event_relation(item, event):
    if event.get("ticker") != item.get("ticker"):
        return None
    event_program = str(event.get("drug_program") or "").lower()
    event_indication = str(event.get("indication") or "").lower()
    missing_markers = ("missing", "not established", "unknown")
    program_terms = [term.strip().lower() for term in re.split(r"[/()]", item.get("program", "")) if len(term.strip()) >= 4]
    indication_terms = [term.strip().lower() for term in re.split(r"[/()]", item.get("indication", "")) if len(term.strip()) >= 5 and "missing" not in term.lower()]
    if not any(marker in event_program for marker in missing_markers) and any(term in event_program for term in program_terms):
        return "program-level"
    if not any(marker in event_indication for marker in missing_markers) and any(term in event_indication for term in indication_terms):
        return "indication-level"
    return "company-level"


def biotech_radar_evidence(item, biotech_news_section, as_of):
    raw_events = (biotech_news_section or {}).get("radar_evidence_interface", {}).get("events", [])
    deduplicated = {}
    for event in raw_events:
        relation = biotech_event_relation(item, event)
        if not relation:
            continue
        event_id = event.get("id") or news_fingerprint(
            f"{event.get('ticker', '')} {event.get('published_at', '')} {event.get('new_information', '')}", "biotech-radar")
        if event_id in deduplicated:
            continue
        direction = str(event.get("direction") or "").lower()
        signal = "mixed" if "mixed" in direction else "confirming" if any(
            term in direction for term in ("positive", "advancing", "expanding")) else "contradicting" if any(
            term in direction for term in ("negative", "delayed", "contracting", "failed")) else "mixed"
        try:
            event_time = datetime.fromisoformat(event.get("published_at")) if event.get("published_at") else None
        except (TypeError, ValueError):
            event_time = None
        if event_time and event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        reference_time = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
        age = ai_evidence_age(event_time.isoformat() if event_time else None, reference_time)
        deduplicated[event_id] = {**event, **age, "event_id": event_id, "relation": relation, "signal": signal}
    return list(deduplicated.values())


def biotech_radar_why_changed(previous, current):
    if not previous:
        return "Initial Biotech Radar V1 evidence baseline."
    changes = []
    for label, key in (
        ("Opportunity Score", "opportunity_score"), ("Scientific Evidence", "scientific_evidence_score"),
        ("Catalyst Impact", "catalyst_impact_score"), ("Data Completeness", "data_completeness"),
        ("Binary Risk", "binary_risk"), ("Status", "opportunity_status"),
    ):
        old, new = previous.get(key), current.get(key)
        if old != new:
            changes.append(f"{label} changed from {old if old is not None else 'Missing'} to {new if new is not None else 'Missing'}")
    return "; ".join(changes) + "." if changes else "No material score change; evidence history was refreshed and deduplicated."


def biotech_binary_risk(item, scientific_score, catalyst_impact, integrity_concern, thesis_broken):
    stage = item.get("stage", "").lower()
    if thesis_broken or (scientific_score is None and catalyst_impact >= 12):
        level = "Extreme"
    elif integrity_concern or scientific_score is None or (scientific_score < 18 and catalyst_impact >= 11):
        level = "High"
    elif "phase 1" in stage and catalyst_impact >= 11:
        level = "High"
    else:
        level = "Moderate"
    rationale = (
        f"Evidence uncertainty is {'missing' if scientific_score is None else f'{scientific_score}/30'}; "
        f"catalyst magnitude is {catalyst_impact}/25. Verified company valuation sensitivity and portfolio dependence are missing, so risk cannot be classified Low."
    )
    return level, rationale


def score_biotech_catalyst(item, as_of, biotech_news_section=None, previous=None, market_data=None):
    timing_score, timing_rationale, timing_missing = timing_component(item, as_of)
    prior_points, prior_rationale = item["components"]["prior_evidence"]
    prior_missing = prior_points == 0 and prior_rationale.lower().startswith("missing")
    scientific_score = None if prior_missing else round(prior_points / 20 * 30)
    importance_points, importance_rationale = item["components"]["catalyst_importance"]
    commercial_points, commercial_rationale = item["components"]["commercial_impact"]
    catalyst_impact = round((importance_points / 25 * 0.6 + commercial_points / 15 * 0.4) * 15)
    expectation_points, expectation_rationale = item["components"]["expectation_gap"]
    expectation_missing = expectation_points == 0 and expectation_rationale.lower().startswith("missing")
    expectation_score = None if expectation_missing else round(expectation_points / 15 * 20)
    security_market_record = market_snapshot(market_data, item.get("ticker"))
    expectation = expectation_assessment(security_market_record, "biotech", 20)
    if expectation["score"] is not None:
        expectation_score = expectation["score"]
        expectation_rationale = expectation["rationale"]
        expectation_missing = False
    positioning_points, positioning_rationale = item["components"]["positioning"]
    short_record = (security_market_record or {}).get("expectation_data", {}).get("short_interest", {})
    positioning_missing = short_record.get("days_to_cover") is None
    if not positioning_missing:
        positioning_rationale = (f"Nasdaq short interest settled {short_record.get('settlement_date') or 'date missing'}: "
                                 f"{short_record['days_to_cover']:.2f} days to cover; change from prior period "
                                 f"{short_record.get('change_from_prior_pct') if short_record.get('change_from_prior_pct') is not None else 'missing'}%.")
    sector_market = (market_data or {}).get("benchmarks", {}).get("xbi")
    sector_trend_score, sector_available, sector_rationale = market_component_score(sector_market, "sp500", 10)
    stock_technical_score, stock_technical_available, stock_technical_rationale = market_component_score(security_market_record, "xbi", 5)
    timing_available = 0 if timing_missing else 5
    technical_available = stock_technical_available
    timing_technicals_score = None if timing_available + technical_available == 0 else (
        (round(timing_score / 15 * 5) if timing_available else 0) +
        (stock_technical_score if technical_available else 0)
    )
    breakdown = [
        biotech_radar_factor("scientific_evidence", "Scientific Evidence", 30, scientific_score, 0 if prior_missing else 30,
                              prior_rationale, item["sources"], ["Program-specific scientific evidence"] if prior_missing else []),
        biotech_radar_factor("catalyst_impact_company_sensitivity", "Catalyst Impact / Company Sensitivity", 25, catalyst_impact, 15,
                              f"{importance_rationale} {commercial_rationale} Verified program-level valuation sensitivity and portfolio dependence are missing.", item["sources"],
                              ["Company valuation sensitivity", "Portfolio dependence"]),
        biotech_radar_factor("expectation_gap", "Expectation Gap", 20, expectation_score, 0 if expectation_missing else 20,
                              expectation_rationale,
                              item["sources"] + [{"title": source["name"], "date": source.get("data_date") or source.get("retrieved_at", "")[:10], "url": source["url"]}
                                                 for source in expectation.get("sources", [])],
                              ["Verified valuation, analyst, run-up, and positioning inputs"] if expectation_missing else []),
        biotech_radar_factor("sector_trend_capital_flow", "Sector Trend & Capital Flow", 15, sector_trend_score, sector_available,
                              f"{sector_rationale} Advanced capital-flow data is outside this MVP.", item["sources"],
                              (["XBI market trend"] if not sector_available else []) + ["Advanced capital flow"]),
        biotech_radar_factor("timing_technicals", "Timing & Technicals", 10, timing_technicals_score, timing_available + technical_available,
                              f"{timing_rationale} {stock_technical_rationale} {positioning_rationale}", item["sources"],
                              (["Catalyst timing"] if timing_missing else []) + (["Price/volume technical setup"] if not technical_available else []) +
                              (["Short interest / advanced positioning"] if positioning_missing else [])),
    ]
    available_weight = sum(component["available_weight"] for component in breakdown)
    available_points = sum(component["score"] for component in breakdown if component["score"] is not None)
    opportunity_score = round(available_points / available_weight * 100) if available_weight else None
    news_evidence = biotech_radar_evidence(item, biotech_news_section, as_of)
    confirming = [event for event in news_evidence if event["signal"] == "confirming"]
    mixed = [event for event in news_evidence if event["signal"] == "mixed"]
    contradicting = [event for event in news_evidence if event["signal"] == "contradicting"]
    integrity_terms = ("data integrity", "misconduct", "fraud", "retraction", "fabricated data")
    integrity_evidence = [event for event in news_evidence if any(
        term in str(event.get("new_information") or "").lower() for term in integrity_terms)]
    integrity_concern = bool(integrity_evidence)
    thesis_terms = ("failed primary endpoint", "trial terminated", "program discontinued", "application withdrawn", "fda rejected")
    thesis_broken = any(event.get("relation") != "company-level" and any(
        term in str(event.get("new_information") or "").lower() for term in thesis_terms) for event in contradicting)
    confidence = "High" if available_weight >= 80 and scientific_score is not None and scientific_score >= 24 else (
        "Medium" if available_weight >= 50 and scientific_score is not None and scientific_score >= 18 else "Low")
    if integrity_concern:
        confidence = "Low"
    binary_risk, binary_risk_rationale = biotech_binary_risk(
        item, scientific_score, catalyst_impact, integrity_concern, thesis_broken)
    evidence_gate_passed = scientific_score is not None and scientific_score >= 18 and not integrity_concern
    high_conviction_eligible = evidence_gate_passed and scientific_score >= 24 and available_weight >= 75 and confidence == "High"
    if thesis_broken:
        status = "Thesis Broken"
    elif integrity_concern or binary_risk == "Extreme":
        status = "High Downside Risk"
    elif not evidence_gate_passed or binary_risk == "High":
        status = "Speculative Binary"
    elif high_conviction_eligible and opportunity_score is not None and opportunity_score >= 80:
        status = "High Conviction"
    elif scientific_score is not None and scientific_score >= 24 and catalyst_impact >= 12:
        status = "Evidence-Supported / High Impact"
    else:
        status = "Monitoring"
    result = {key: value for key, value in item.items() if key not in ("components", "window_start", "window_end")}
    result.update({
        "opportunity_score": opportunity_score,
        "catalyst_score": opportunity_score,
        "scientific_evidence_score": scientific_score,
        "catalyst_impact_score": catalyst_impact,
        "expectation_gap_score": expectation_score,
        "expectation_state": expectation["state"] if expectation["score"] is not None else ("Data Insufficient" if expectation_missing else "Fairly Priced"),
        "expectation": expectation,
        "sector_trend_score": sector_trend_score,
        "timing_technicals_score": timing_technicals_score,
        "market_data": compact_market_snapshot(security_market_record),
        "sector_market_data": sector_market,
        "market_expectation": expectation_rationale,
        "positioning": positioning_rationale,
        "upcoming_catalyst": f"{item['catalyst']} — {item['expected_timing']}",
        "opportunity_status": status,
        "binary_risk": binary_risk,
        "binary_risk_rationale": binary_risk_rationale,
        "binary_risk_inputs": {
            "evidence_uncertainty": None if scientific_score is None else 30 - scientific_score,
            "company_sensitivity": None,
            "catalyst_magnitude": catalyst_impact,
            "portfolio_dependence": None,
        },
        "company_sensitivity": "Missing: no verified program-level valuation sensitivity is connected.",
        "portfolio_dependence": "Missing: no verified portfolio-dependence measure is connected.",
        "evidence_gate": {
            "passed": evidence_gate_passed,
            "high_conviction_eligible": high_conviction_eligible,
            "rule": "Scientific Evidence below 18/30 cannot be High Conviction; High Conviction also requires at least 75% completeness and High confidence.",
        },
        "evidence_integrity_gate": {
            "concern_identified": integrity_concern,
            "confidence_cap": "Low" if integrity_concern else None,
            "evidence_ids": [event["event_id"] for event in integrity_evidence],
            "rule": "Explicit credibility or data-integrity concerns cap confidence at Low.",
        },
        "score_as_of": as_of.isoformat(),
        "engine_version": "biotech-radar-v1",
        "score_components": breakdown,
        "missing_data": [field for component in breakdown for field in component["missing_fields"]],
        "data_completeness": available_weight,
        "confidence": confidence,
        "confirming_evidence": confirming,
        "mixed_evidence": mixed,
        "contradicting_evidence": contradicting,
        "evidence_count": len(news_evidence),
    })
    result["why_changed"] = biotech_radar_why_changed(previous, result)
    prior_history = list(previous.get("score_history", [])) if previous else []
    snapshot = {
        "as_of": as_of.isoformat(), "opportunity_score": opportunity_score,
        "scientific_evidence_score": scientific_score, "catalyst_impact_score": catalyst_impact,
        "expectation_gap_score": expectation_score, "binary_risk": binary_risk,
        "data_completeness": available_weight, "confidence": confidence,
        "opportunity_status": status, "evidence_count": len(news_evidence), "why_changed": result["why_changed"],
    }
    snapshot_day = snapshot["as_of"][:10]
    prior_history = [entry for entry in prior_history if str(entry.get("as_of", ""))[:10] != snapshot_day]
    result["score_history"] = (prior_history + [snapshot])[-60:]
    return result


def build_biotech_radar(as_of, biotech_news_section=None, previous_rows=None, market_data=None):
    horizon = as_of + timedelta(days=183)
    previous_by_key = {
        (row.get("ticker"), row.get("program"), row.get("indication"), row.get("catalyst")): row
        for row in (previous_rows or [])
    }
    eligible = []
    for item in BIOTECH_CATALYSTS:
        start = datetime.fromisoformat(item["window_start"]).date()
        end = datetime.fromisoformat(item["window_end"]).date()
        if end >= as_of and start <= horizon:
            key = (item.get("ticker"), item.get("program"), item.get("indication"), item.get("catalyst"))
            eligible.append(score_biotech_catalyst(
                item, as_of, biotech_news_section, previous_by_key.get(key), market_data))
    return sorted(eligible, key=lambda item: (-(item["opportunity_score"] or -1), item["expected_timing"], item["ticker"]))


def radar_methodology():
    return {
        "engine_version": "biotech-radar-v1",
        "horizon": "Potentially valuation-changing catalysts expected within the next 183 days (approximately six months).",
        "weights": BIOTECH_RADAR_WEIGHTS,
        "opportunity_score_policy": "Opportunity Score is normalized over available weighted inputs. Missing inputs are excluded, never treated as zero, and Data Completeness must be reviewed with the score.",
        "evidence_gate": "Scientific Evidence below 18/30 cannot be High Conviction. High Conviction additionally requires Scientific Evidence of at least 24/30, 75% completeness, and High confidence.",
        "integrity_gate": "Explicit credibility or data-integrity concerns cap evidence confidence at Low.",
        "news_boundary": "Biotech News is retained as dated confirming, mixed, or contradicting evidence. News importance never sets a Radar factor or Opportunity Score.",
        "market_data_policy": "XBI price trend supplies up to 10 of 15 Sector Trend points; security price/volume technicals supply up to 5 of 10 Timing & Technicals points. Phase 5B supplies Expectation Gap from current valuation, run-up, analyst-revision and short-interest inputs. Options IV and advanced capital-flow data remain excluded.",
        "binary_risk": "Low / Moderate / High / Extreme uses available evidence uncertainty and catalyst magnitude; missing company valuation sensitivity or portfolio dependence prevents a Low classification.",
        "status_policy": ["High Conviction", "Evidence-Supported / High Impact", "Monitoring", "Speculative Binary", "High Downside Risk", "Thesis Broken"],
        "scope_note": "V1 scores the existing curated Company → Drug/Program → Indication → Catalyst set. Unavailable valuation, analyst, short-interest, trial, portfolio-dependence, options-IV and advanced capital-flow inputs remain missing.",
    }


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

AI_INDUSTRY_MAP = [
    ("AI Models/Applications", ("artificial intelligence", " ai ", "model", "inference", "agent", "software", "copilot")),
    ("Physical AI / Robotics", ("physical ai", "robotics", "robot", "humanoid", "embodied ai", "autonomous system")),
    ("Compute", ("gpu", "accelerator", "compute", "chip", "semiconductor", "nvidia", "amd")),
    ("HBM/Memory", ("hbm", "high-bandwidth memory", "memory", "dram", "micron", "sk hynix")),
    ("Foundry/Advanced Packaging", ("foundry", "wafer", "packaging", "tsmc", "asml", "fab")),
    ("Networking/Optical", ("networking", "ethernet", "optical", "interconnect", "broadcom", "arista")),
    ("Data Centers", ("data center", "datacenter", "ai infrastructure", "ai cloud", "cloud capacity", "server", "hyperscaler")),
    ("Power/Electrical", ("power infrastructure", "power delivery", "megawatt", "electricity", "electrical", "transformer", "switchgear", "vertiv", "eaton")),
    ("Cooling", ("cooling", "thermal", "liquid-cooled", "liquid cooling")),
    ("Grid/Energy/Materials", ("grid", "energy", "nuclear", "natural gas", "copper", "uranium", "materials")),
]

AI_NEWS_QUERIES = [
    'artificial intelligence (earnings OR guidance OR investment OR acquisition OR regulation) when:4d',
    '(semiconductor OR HBM OR foundry OR networking OR data center) (capacity OR investment OR orders OR launch) when:4d',
    '(AI data center) (power OR cooling OR grid OR energy) investment when:4d',
    '(AI OR GPU OR data center) (contract OR partnership OR acquisition OR earnings) when:4d',
    '(AI infrastructure) (supply OR demand OR backlog OR construction OR financing) when:4d',
]

OFFICIAL_AI_FEEDS = [
    ("NVIDIA Newsroom", "https://nvidianews.nvidia.com/cats/press_release.xml", "https://nvidianews.nvidia.com/"),
    ("AMD Investor Relations", "https://ir.amd.com/rss/news-releases.xml", "https://ir.amd.com/"),
    ("AWS News Blog", "https://aws.amazon.com/blogs/aws/feed/", "https://aws.amazon.com/blogs/aws/"),
    ("Microsoft Official Blog", "https://blogs.microsoft.com/feed/", "https://blogs.microsoft.com/"),
]

BIOTECH_NEWS_QUERIES = [
    '(biotech OR biopharma) ("phase 2" OR "phase 3" OR pivotal OR clinical results OR readout) when:4d',
    '(FDA OR regulatory) (approval OR "complete response letter" OR "clinical hold" OR BLA OR NDA OR PDUFA) biotech when:4d',
    '(biotech OR biopharma) (acquisition OR merger OR licensing OR partnership) when:4d',
    '(drug launch OR commercial biotech) (sales OR guidance OR reimbursement OR manufacturing) when:4d',
    '(gene therapy OR gene editing OR RNA therapy OR cell therapy) (clinical data OR platform OR partnership) when:4d',
]

OFFICIAL_BIOTECH_FEEDS = [
    ("Intellia Therapeutics Investor Relations", "https://ir.intelliatx.com/rss/news-releases.xml", "https://ir.intelliatx.com/"),
    ("Beam Therapeutics Investor Relations", "https://investors.beamtx.com/rss/news-releases.xml", "https://investors.beamtx.com/"),
]

BIOTECH_COMPANIES = {
    alias: (record["company"], record["ticker"])
    for record in COMPANY_REGISTRY if record["domain"] in ("biotech", "both") and record["ticker"] != "N/A"
    for alias in record["aliases"]
}

BIOTECH_PROGRAMS = (
    "mRNA-1083", "mRNA-1010", "mRNA-1403", "mRNA-1647", "mRNA-4157", "intismeran autogene",
    "lonvoguran ziclumeran", "lonvo-z", "BEAM-302", "MZE829", "zorevunersen", "VYJUVEK",
    "Casgevy", "Leqvio", "Amvuttra", "Onpattro",
)

BIOTECH_EVENT_TERMS = (
    "clinical results", "trial results", "trial win", "topline", "readout", "primary endpoint", "phase 1", "phase 2", "phase 3", "pivotal",
    "approval", "approved", "complete response letter", "crl", "clinical hold", "bla", "nda", "pdufa", "fast track", "breakthrough therapy",
    "delayed", "delay", "accelerated", "timeline", "expects", "acquisition", "acquires", "merger", "license", "licensing", "partnership", "deal", "ipo", "financing",
    "launch", "commercial", "sales", "reimbursement", "manufacturing", "platform", "proof-of-concept", "publication",
)

BIOTECH_PRIMARY_SOURCE_TERMS = tuple(BIOTECH_COMPANIES) + (
    "u.s. food and drug administration", "food and drug administration", "fda", "nih", "national institutes of health",
)
BIOTECH_SCIENTIFIC_SOURCES = (
    "new england journal of medicine", "nejm", "the lancet", "jama", "nature", "science", "cell",
)
BIOTECH_INDUSTRY_SOURCES = (
    "stat", "endpoints news", "fierce biotech", "biopharma dive", "biospace", "evaluate vantage", "pink sheet",
)

PRIMARY_SOURCE_TERMS = (
    "nvidia", "amd", "broadcom", "micron", "tsmc", "asml", "arista", "vertiv", "eaton",
    "microsoft", "alphabet", "google", "amazon", "aws", "meta", "openai", "anthropic",
    "oracle", "intel", "qualcomm", "arm", "apple", "dell", "supermicro", "coreweave",
    "cisco", "infineon", "iren", "marvell", "applied materials", "cbre",
)
RELIABLE_FINANCIAL_SOURCES = (
    "reuters", "bloomberg", "financial times", "the wall street journal", "wall street journal",
    "wsj", "associated press", "ap news", "cnbc", "marketwatch", "barron's", "fortune",
    "s&p global", "investor's business daily", "business insider", "nikkei asia",
)
RELIABLE_INDUSTRY_SOURCES = (
    "semiconductor engineering", "ee times", "data center dynamics", "the register",
    "ieee spectrum", "mit technology review", "techcrunch", "tom's hardware",
    "data center frontier", "fierce network", "light reading", "utility dive", "cbre",
)
PRIMARY_RESEARCH_SOURCES = ("s&p global", "cbre")
INVESTMENT_EVENT_TERMS = (
    "earnings", "financial results", "revenue", "guidance", "outlook", "forecast", "capex", "capital expenditure", "investment",
    "acquisition", "acquires", "merger", "partnership", "funding", "contract", "orders", "capacity",
    "launch", "unveils", "deploy", "deliver", "expands", "adopts", "export", "sanction", "regulation", "antitrust", "approval", "raises",
)
FORWARD_SIGNAL_TERMS = (
    "guidance", "outlook", "forecast", "expects", "expected", "plans", "will", "capacity", "capex", "investment", "orders",
    "backlog", "contract", "partnership", "launch", "deploy", "deliver", "roadmap", "export", "regulation", "funding",
)
TREND_CHANGE_TERMS = (
    "acquisition", "acquires", "merger", "export ban", "sanction", "antitrust", "regulation",
    "breakthrough", "halts", "cancels", "bankruptcy",
)


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
        results = []
        for item in root.findall(".//item")[:limit]:
            publisher = item.find("source")
            results.append({
                "title": item.findtext("title", "Latest coverage"),
                "url": item.findtext("link", news_url(query)),
                "date": item.findtext("pubDate", ""),
                "source": (publisher.text or "").strip() if publisher is not None else "",
                "publisher_url": publisher.get("url", "") if publisher is not None else "",
            })
        return results
    except Exception as exc:
        print(f"RSS unavailable for {query}: {exc}")
        return []


def plain_text(value):
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value or "", flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def official_feed_items(source_name, url, publisher_url, limit=20):
    try:
        root = ET.fromstring(fetch(url))
        results = []
        for item in root.findall(".//item")[:limit]:
            description = item.findtext("description", "")
            encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", "")
            results.append({
                "title": item.findtext("title", "Latest company update"),
                "url": item.findtext("link", publisher_url),
                "date": item.findtext("pubDate", ""),
                "source": source_name,
                "publisher_url": publisher_url,
                "description": plain_text(description),
                "feed_content": plain_text(encoded)[:12000],
                "is_primary": True,
            })
        return results
    except Exception as exc:
        print(f"Official feed unavailable for {source_name}: {exc}")
        return []


def stooq_symbol_for(yahoo_symbol):
    index_map = {"^GSPC": "^spx", "^IXIC": "^ndq", "^DJI": "^dji", "^RUT": "^rty"}
    if yahoo_symbol in index_map:
        return index_map[yahoo_symbol]
    return f"{yahoo_symbol.lower()}.us" if re.fullmatch(r"[A-Z][A-Z0-9.-]*", yahoo_symbol) else None


def fetch_market_series(yahoo_symbol, stooq_symbol=None):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(yahoo_symbol, safe="") + "?range=2y&interval=1d"
        payload = json.loads(fetch(url, timeout=12))
        result = payload["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        timestamps = result.get("timestamp", [])
        rows = [
            {"date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
             "close": float(close), "volume": float(volume) if volume is not None else None}
            for timestamp, close, volume in zip(timestamps, quote.get("close", []), quote.get("volume", []))
            if close is not None
        ]
        return {"symbol": yahoo_symbol, "rows": rows, "source": "Yahoo Finance chart", "currency": result.get("meta", {}).get("currency")}
    except Exception:
        try:
            stooq_symbol = stooq_symbol or stooq_symbol_for(yahoo_symbol)
            if not stooq_symbol:
                raise ValueError("No Stooq fallback symbol is configured")
            end = datetime.now(timezone.utc).date(); start = end - timedelta(days=760)
            url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(stooq_symbol)}&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
            rows = csv.DictReader(io.StringIO(fetch(url).decode("utf-8")))
            parsed = [
                {"date": row.get("Date"), "close": float(row["Close"]),
                 "volume": float(row["Volume"]) if row.get("Volume") not in (None, "", "N/D") else None}
                for row in rows if row.get("Close") not in (None, "", "N/D")
            ]
            return {"symbol": yahoo_symbol, "rows": parsed, "source": "Stooq daily data", "currency": None}
        except Exception as exc:
            print(f"Market data unavailable for {yahoo_symbol}: {exc}")
            return {"symbol": yahoo_symbol, "rows": [], "source": None, "currency": None}


def market_history(yahoo_symbol, stooq_symbol):
    return [row["close"] for row in fetch_market_series(yahoo_symbol, stooq_symbol)["rows"]]


def moving_average(values, window):
    return round(sum(values[-window:]) / window, 4) if len(values) >= window else None


def period_return(values, sessions):
    return round((values[-1] / values[-sessions - 1] - 1) * 100, 2) if len(values) > sessions and values[-sessions - 1] else None


def rsi(values, window=14):
    if len(values) <= window:
        return None
    changes = [values[index] - values[index - 1] for index in range(len(values) - window, len(values))]
    gains = sum(max(change, 0) for change in changes) / window
    losses = sum(max(-change, 0) for change in changes) / window
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    return round(100 - 100 / (1 + gains / losses), 2)


def ema_series(values, window):
    if len(values) < window:
        return []
    multiplier = 2 / (window + 1)
    ema = sum(values[:window]) / window
    result = [None] * (window - 1) + [ema]
    for value in values[window:]:
        ema = (value - ema) * multiplier + ema
        result.append(ema)
    return result


def macd(values):
    if len(values) < 35:
        return {"value": None, "signal": None, "histogram": None,
                "previous_histogram": None, "improving": None, "crossover": None}
    fast, slow = ema_series(values, 12), ema_series(values, 26)
    macd_values = [fast[index] - slow[index] for index in range(25, len(values))]
    signal_values = ema_series(macd_values, 9)
    if not signal_values or signal_values[-1] is None:
        return {"value": None, "signal": None, "histogram": None,
                "previous_histogram": None, "improving": None, "crossover": None}
    value, signal = macd_values[-1], signal_values[-1]
    histogram = value - signal
    previous = (macd_values[-2] - signal_values[-2]
                if len(macd_values) >= 2 and len(signal_values) >= 2 and signal_values[-2] is not None else None)
    crossover = ("bullish" if previous is not None and previous <= 0 < histogram else
                 "bearish" if previous is not None and previous >= 0 > histogram else None)
    return {"value": round(value, 4), "signal": round(signal, 4), "histogram": round(histogram, 4),
            "previous_histogram": round(previous, 4) if previous is not None else None,
            "improving": histogram > previous if previous is not None else None, "crossover": crossover}


def benchmark_relative_strength(stock_returns, benchmark_returns):
    return {
        horizon: round(stock_returns[horizon] - benchmark_returns[horizon], 2)
        if stock_returns.get(horizon) is not None and benchmark_returns.get(horizon) is not None else None
        for horizon in ("one_month", "three_month", "six_month")
    }


def calculate_market_technicals(ticker, series, benchmark_records=None, market_cap=None):
    rows = sorted(series.get("rows", []), key=lambda row: row.get("date") or "")
    closes = [row["close"] for row in rows]
    volumes = [row.get("volume") for row in rows]
    if not closes:
        return None
    returns = {"daily": period_return(closes, 1), "weekly": period_return(closes, 5),
               "one_month": period_return(closes, 21), "three_month": period_return(closes, 63),
               "six_month": period_return(closes, 126)}
    valid_recent_volumes = [value for value in volumes[-20:] if value is not None]
    volume_average = sum(valid_recent_volumes) / len(valid_recent_volumes) if valid_recent_volumes else None
    current_volume = volumes[-1] if volumes else None
    recent_year = closes[-252:]
    year_low, year_high = (min(recent_year), max(recent_year)) if recent_year else (None, None)
    year_position = round((closes[-1] - year_low) / (year_high - year_low) * 100, 2) if year_high is not None and year_high != year_low else None
    benchmark_records = benchmark_records or {}
    relative_strength = {
        name: benchmark_relative_strength(returns, record.get("returns", {}))
        for name, record in benchmark_records.items()
    }
    moving_averages = {"ma5": moving_average(closes, 5), "ma10": moving_average(closes, 10),
                       "ma20": moving_average(closes, 20), "ma50": moving_average(closes, 50),
                       "ma200": moving_average(closes, 200)}
    macd_record = macd(closes)
    return {
        "ticker": ticker, "current_price": round(closes[-1], 4), "price_date": rows[-1].get("date"),
        "currency": series.get("currency"), "market_cap": market_cap,
        "moving_averages": moving_averages,
        "returns": returns, "rsi_14": rsi(closes), "macd": macd_record,
        "volume_vs_20d_average": round(current_volume / volume_average, 2) if current_volume is not None and volume_average else None,
        "fifty_two_week_position": year_position, "relative_strength": relative_strength,
        "entry_inputs": calculate_entry_inputs(rows, moving_averages, macd_record),
        "source": series.get("source"), "data_status": "current",
        "missing_fields": [name for name, value in (("market_cap", market_cap), ("volume", current_volume),
                           ("ma200", moving_average(closes, 200)), ("fifty_two_week_position", year_position)) if value is None],
    }


def fetch_market_caps(tickers):
    if not tickers:
        return {}
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + urllib.parse.quote(",".join(sorted(tickers)), safe=",")
        payload = json.loads(fetch(url, timeout=12))
        return {
            item["symbol"]: item.get("marketCap")
            for item in payload.get("quoteResponse", {}).get("result", [])
            if isinstance(item.get("marketCap"), (int, float)) and item.get("marketCap") > 0
        }
    except Exception as exc:
        print(f"Market-cap data unavailable: {exc}")
        return {}


NASDAQ_API_ROOT = "https://api.nasdaq.com/api"
NASDAQ_LISTED_COMPANY_URL = f"{NASDAQ_API_ROOT}/screener/stocks?tableonly=true&limit=10000"


def parse_market_number(value):
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value or "").strip().replace("$", "").replace(",", "").replace("%", "")
    if not cleaned or cleaned.upper() in ("N/A", "NA", "NONE", "NULL", "--"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_nasdaq_json(url, timeout=12):
    completed = subprocess.run([
        "curl", "--location", "--fail", "--silent", "--show-error",
        "--connect-timeout", "5", "--max-time", str(timeout),
        "--header", "User-Agent: Mozilla/5.0", "--header", "Accept: application/json", url,
    ], check=True, capture_output=True, timeout=timeout + 3)
    payload = json.loads(completed.stdout)
    return payload.get("data") if payload.get("status", {}).get("rCode") == 200 else None


def fetch_listed_company_universe(run_at, fetcher=fetch_nasdaq_json):
    """Load a general U.S.-listed company universe for evidence entity resolution.

    The universe is not a stock recommendation list and is never shipped to the
    frontend. Only evidence-matched identities are retained in discovery output.
    """
    try:
        data = fetcher(NASDAQ_LISTED_COMPANY_URL, timeout=20) or {}
        rows = data.get("table", {}).get("rows", [])
        companies = []
        seen = set()
        for row in rows:
            ticker = str(row.get("symbol") or "").strip().upper()
            company = html.unescape(str(row.get("name") or "")).strip()
            if not ticker or not company or ticker in seen or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
                continue
            seen.add(ticker)
            companies.append({"company": company, "ticker": ticker, "exchange": "",
                              "listing_status": "Public", "resolution": "Nasdaq listed-company universe"})
        return companies, {
            "status": "available" if companies else "empty",
            "source": NASDAQ_LISTED_COMPANY_URL,
            "retrieved_at": run_at.isoformat(timespec="seconds"),
            "records_loaded": len(companies),
        }
    except Exception as exc:
        print(f"Listed-company discovery universe unavailable: {exc}")
        return [], {"status": "unavailable", "source": NASDAQ_LISTED_COMPANY_URL,
                    "retrieved_at": run_at.isoformat(timespec="seconds"), "error": str(exc)}


def fetch_nasdaq_expectations(ticker, run_at):
    paths = {
        "summary": f"/quote/{ticker}/summary?assetclass=stocks",
        "ratings": f"/analyst/{ticker}/ratings",
        "forecast": f"/analyst/{ticker}/earnings-forecast",
        "short_interest": f"/quote/{ticker}/short-interest?assetclass=stocks",
    }
    result = {"ticker": ticker, "retrieved_at": run_at.isoformat(timespec="seconds"), "payloads": {}, "errors": {}}
    for key, path in paths.items():
        try:
            payload = fetch_nasdaq_json(NASDAQ_API_ROOT + path)
            if payload:
                result["payloads"][key] = payload
            else:
                result["errors"][key] = "No data returned"
        except Exception as exc:
            result["errors"][key] = str(exc)
    return result


def fetch_expectation_inputs(tickers, run_at):
    records = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_nasdaq_expectations, ticker, run_at): ticker for ticker in sorted(tickers)}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                records[ticker] = future.result()
            except Exception as exc:
                print(f"Expectation data unavailable for {ticker}: {exc}")
    return records


def build_expectation_record(ticker, raw, market_record, run_at):
    raw = raw or {}; payloads = raw.get("payloads", {})
    summary = payloads.get("summary", {}).get("summaryData", {})
    summary_value = lambda key: summary.get(key, {}).get("value")
    forecast = payloads.get("forecast", {})
    quarterly_rows = forecast.get("quarterlyForecast", {}).get("rows") or []
    yearly_rows = forecast.get("yearlyForecast", {}).get("rows") or []
    next_quarter = quarterly_rows[0] if quarterly_rows else {}
    next_year = yearly_rows[0] if yearly_rows else {}
    ratings = payloads.get("ratings", {})
    rating_count_match = re.search(r"(\d+)\s+analysts?", ratings.get("ratingsSummary") or "", re.IGNORECASE)
    short_rows = payloads.get("short_interest", {}).get("shortInterestTable", {}).get("rows") or []
    latest_short = short_rows[0] if short_rows else {}; prior_short = short_rows[1] if len(short_rows) > 1 else {}
    current_price = (market_record or {}).get("current_price")
    target = parse_market_number(summary_value("OneYrTarget"))
    market_cap = parse_market_number(summary_value("MarketCap"))
    next_year_eps = parse_market_number(next_year.get("consensusEPSForecast"))
    target_upside = round((target / current_price - 1) * 100, 2) if target and current_price else None
    forward_pe = round(current_price / next_year_eps, 2) if current_price and next_year_eps and next_year_eps > 0 else None
    revisions_up = parse_market_number(next_quarter.get("up")); revisions_down = parse_market_number(next_quarter.get("down"))
    net_revisions = int(revisions_up - revisions_down) if revisions_up is not None and revisions_down is not None else None
    latest_short_shares = parse_market_number(latest_short.get("interest")); prior_short_shares = parse_market_number(prior_short.get("interest"))
    short_change = round((latest_short_shares / prior_short_shares - 1) * 100, 2) if latest_short_shares and prior_short_shares else None
    returns = (market_record or {}).get("returns", {})
    sources = []
    source_specs = {
        "summary": ("Nasdaq company summary", f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}", (market_record or {}).get("price_date")),
        "ratings": ("Nasdaq analyst ratings", f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/analyst-research", None),
        "forecast": ("Nasdaq earnings forecast", f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/earnings", next_quarter.get("fiscalEnd")),
        "short_interest": ("Nasdaq short interest", f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/short-interest", latest_short.get("settlementDate")),
    }
    for key, (name, url, data_date) in source_specs.items():
        if key in payloads:
            sources.append({"name": name, "url": url, "retrieved_at": raw.get("retrieved_at") or run_at.isoformat(timespec="seconds"), "data_date": data_date})
    groups = []
    if any(value is not None for value in (market_cap, target, target_upside, forward_pe)):
        groups.append("valuation")
    if any(returns.get(key) is not None for key in ("one_month", "three_month", "six_month")):
        groups.append("price_run_up")
    if any(value is not None for value in (ratings.get("meanRatingType"), net_revisions, next_year_eps)):
        groups.append("analyst_consensus")
    if any(value is not None for value in (latest_short_shares, parse_market_number(latest_short.get("daysToCover")), short_change)):
        groups.append("positioning")
    record = {
        "ticker": ticker, "data_status": "current" if groups else "missing",
        "as_of": run_at.isoformat(timespec="seconds"), "available_input_groups": groups,
        "valuation": {"market_cap": market_cap, "one_year_target": target, "target_upside_pct": target_upside,
                      "forward_pe": forward_pe, "consensus_eps_next_fy": next_year_eps,
                      "consensus_eps_fiscal_end": next_year.get("fiscalEnd")},
        "price_run_up": {"one_month_pct": returns.get("one_month"), "three_month_pct": returns.get("three_month"),
                         "six_month_pct": returns.get("six_month"), "price_date": (market_record or {}).get("price_date"),
                         "method": "Recent close-to-close return proxy; event-specific anchor is used only when a verified catalyst date is available."},
        "analyst_consensus": {"mean_rating": ratings.get("meanRatingType"),
                              "analyst_count": int(rating_count_match.group(1)) if rating_count_match else None,
                              "next_quarter_fiscal_end": next_quarter.get("fiscalEnd"),
                              "next_quarter_consensus_eps": parse_market_number(next_quarter.get("consensusEPSForecast")),
                              "estimate_count": int(next_quarter["noOfEstimates"]) if isinstance(next_quarter.get("noOfEstimates"), (int, float)) else None,
                              "revisions_up_4w": int(revisions_up) if revisions_up is not None else None,
                              "revisions_down_4w": int(revisions_down) if revisions_down is not None else None,
                              "net_revisions_4w": net_revisions},
        "short_interest": {"settlement_date": latest_short.get("settlementDate"), "shares_short": latest_short_shares,
                           "average_daily_volume": parse_market_number(latest_short.get("avgDailyShareVolume")),
                           "days_to_cover": parse_market_number(latest_short.get("daysToCover")),
                           "change_from_prior_pct": short_change,
                           "prior_settlement_date": prior_short.get("settlementDate")},
        "sources": sources, "source_errors": raw.get("errors", {}),
    }
    record["missing_fields"] = [path for path, value in (
        ("valuation.forward_pe", forward_pe), ("valuation.target_upside_pct", target_upside),
        ("analyst_consensus.net_revisions_4w", net_revisions),
        ("short_interest.days_to_cover", record["short_interest"]["days_to_cover"]),
    ) if value is None]
    return record


def expectation_assessment(snapshot, domain, maximum):
    record = (snapshot or {}).get("expectation_data") if snapshot else None
    if not record or record.get("data_status") != "current":
        return {"state": "Data Insufficient", "score": None, "maximum": maximum, "coverage": 0,
                "signals": [], "rationale": "No current expectation/valuation record is connected."}
    groups = record.get("available_input_groups", [])
    if len(groups) < 2:
        return {"state": "Data Insufficient", "score": None, "maximum": maximum, "coverage": len(groups),
                "signals": [], "rationale": "Fewer than two independent expectation input groups are available."}
    valuation = record.get("valuation", {}); run_up = record.get("price_run_up", {})
    analysts = record.get("analyst_consensus", {}); short = record.get("short_interest", {})
    underpriced = 0; crowded = 0; signals = []
    target_upside = valuation.get("target_upside_pct")
    if target_upside is not None:
        if target_upside >= 20:
            underpriced += 2; signals.append(f"analyst target implies {target_upside:.1f}% upside")
        elif target_upside >= 10:
            underpriced += 1; signals.append(f"analyst target implies {target_upside:.1f}% upside")
        elif target_upside <= 0:
            crowded += 2; signals.append(f"analyst target implies {target_upside:.1f}% upside")
    forward_pe = valuation.get("forward_pe")
    if forward_pe is not None:
        high_threshold = 50 if domain == "ai" else 40
        if forward_pe >= high_threshold:
            crowded += 1; signals.append(f"forward P/E is {forward_pe:.1f}x")
        elif forward_pe <= 25:
            underpriced += 1; signals.append(f"forward P/E is {forward_pe:.1f}x")
    three_month = run_up.get("three_month_pct")
    if three_month is not None:
        if three_month >= 30:
            crowded += 2; signals.append(f"three-month run-up is {three_month:.1f}%")
        elif three_month >= 15:
            crowded += 1; signals.append(f"three-month run-up is {three_month:.1f}%")
        elif three_month <= -20:
            underpriced += 2; signals.append(f"three-month return is {three_month:.1f}%")
        elif three_month <= -10:
            underpriced += 1; signals.append(f"three-month return is {three_month:.1f}%")
    net_revisions = analysts.get("net_revisions_4w")
    if net_revisions is not None:
        if net_revisions >= 2 and (target_upside is None or target_upside >= 0):
            underpriced += 1; signals.append(f"four-week net EPS revisions are +{net_revisions}")
        elif net_revisions <= -2 and three_month is not None and three_month > 0:
            crowded += 1; signals.append(f"four-week net EPS revisions are {net_revisions} despite a positive price return")
    days_to_cover = short.get("days_to_cover"); short_change = short.get("change_from_prior_pct")
    if days_to_cover is not None and days_to_cover >= 5 and short_change is not None and short_change >= 10 and target_upside is not None and target_upside > 0:
        underpriced += 1; signals.append(f"short positioning rose {short_change:.1f}% with {days_to_cover:.1f} days to cover")
    difference = underpriced - crowded
    state = "Underpriced" if difference >= 2 else "Crowded / Priced In" if difference <= -2 else "Fairly Priced"
    score_ratio = 0.85 if state == "Underpriced" else 0.25 if state == "Crowded / Priced In" else 0.55
    score = round(maximum * score_ratio)
    rationale = (f"{state}: " + "; ".join(signals)) if signals else f"{state}: available inputs are balanced and provide no strong directional expectation signal."
    return {"state": state, "score": score, "maximum": maximum, "coverage": len(groups),
            "available_input_groups": groups, "signals": signals, "rationale": rationale,
            "sources": record.get("sources", [])}


AI_CANDIDATE_LIMIT = 30
BIOTECH_CANDIDATE_LIMIT = 20


def biotech_therapeutic_trends(text):
    """Broad modality tags used only for discovery, never as scientific evidence."""
    lowered = str(text or "").lower()
    trends = []
    for label, terms in (
        ("RNA medicines", ("rna", "splicing")),
        ("Gene editing", ("crispr", "editing", "base edit", "prime edit")),
        ("Gene therapy", ("gene therapy", "aav", "redosable")),
        ("Precision medicine", ("human genetics", "precision medicine", "genetically validated")),
    ):
        if any(term in lowered for term in terms):
            trends.append(label)
    return trends


def discover_candidate_pool(ai_radar=None, biotech_radar=None, ai_reasoning_discovery=None):
    """Build a bounded Radar-linked research pool; this is not an eligibility gate."""
    ai_radar = ai_radar or []
    biotech_radar = biotech_radar or []
    candidates = {}
    category_priority = {"Direct": 4, "Bottleneck/Picks-and-Shovels": 3,
                         "Second-Order": 2, "Emerging": 1}

    def add(identity, domain, discovery_source, category=None, radar_link=None,
            therapeutic_trend=None, program=None, indication=None, catalyst=None):
        if not identity or identity.get("listing_status") != "Public":
            return
        ticker = identity.get("ticker")
        if not ticker or ticker in ("Private", "N/A", "Missing") or ":" in ticker:
            return
        key = f"{domain}:{ticker}"
        row = candidates.setdefault(key, {**identity, "domain": domain, "categories": [],
                                           "discovery_sources": [], "radar_links": [],
                                           "programs": [], "therapeutic_trends": []})
        if discovery_source not in row["discovery_sources"]:
            row["discovery_sources"].append(discovery_source)
        if category and category not in row["categories"]:
            row["categories"].append(category)
        if therapeutic_trend and therapeutic_trend not in row["therapeutic_trends"]:
            row["therapeutic_trends"].append(therapeutic_trend)
        program_record = {"program": program, "indication": indication, "catalyst": catalyst}
        if program and program_record not in row["programs"]:
            row["programs"].append(program_record)
        if radar_link and radar_link not in row["radar_links"]:
            row["radar_links"].append(radar_link)

    bottlenecks = {"Compute", "HBM/Memory", "Foundry/Advanced Packaging", "Networking/Optical",
                   "Data Centers", "Power/Electrical", "Cooling", "Grid/Energy/Materials"}
    for trend, config in AI_RADAR_TRACKS.items():
        if trend == "AI Models/Applications":
            for row in AI_PLATFORMS:
                add(company_identity(row["company"], row["ticker"]), "ai",
                    "Existing AI Radar track: AI Models/Applications", "Direct")
        driver = next((item for item in DEMAND_DRIVERS if item["area"] == config.get("demand_area")), None)
        if not driver:
            continue
        public_category = "Bottleneck/Picks-and-Shovels" if trend in bottlenecks else "Direct"
        for identity in normalize_company_list(driver.get("public_companies", "")):
            add(identity, "ai", f"Existing AI Radar demand map: {trend}", public_category)
        for identity in normalize_company_list(driver.get("emerging_companies", "")):
            add(identity, "ai", f"Existing AI Radar emerging map: {trend}", "Emerging")
    for radar in ai_radar:
        for beneficiary in radar.get("beneficiary_records", []):
            component = next((item for item in beneficiary.get("score_components", [])
                              if item.get("label") == "Trend Exposure"), {})
            exposure = round(component["score"] / component["weight"] * 100) if component.get("score") is not None and component.get("weight") else None
            link = {"trend": radar.get("trend"), "category": beneficiary.get("category"),
                    "beneficiary_relevance": beneficiary.get("beneficiary_relevance"),
                    "exposure_score": exposure, "evidence_ids": beneficiary.get("evidence_ids", [])}
            add(company_identity(beneficiary.get("company"), beneficiary.get("ticker")), "ai",
                f"Evidence-linked AI Radar beneficiary: {radar.get('trend')}",
                beneficiary.get("category"), link)
    for discovered in (ai_reasoning_discovery or {}).get("stock_candidates", []):
        roles = discovered.get("beneficiary_roles", [])
        category = "Direct" if "First-Order" in roles else "Second-Order" if "Second-Order" in roles else "Emerging"
        evidence_ids = discovered.get("evidence_ids", [])
        for theme in discovered.get("themes", []) or ["Unclassified reasoning signal"]:
            parent_tracks = discovered.get("parent_tracks", [])
            link = {"trend": next((track for track in parent_tracks if track in AI_RADAR_TRACKS), None),
                    "discovered_theme": theme, "category": category,
                    "beneficiary_relevance": None, "exposure_score": None,
                    "evidence_ids": evidence_ids, "reasoning_discovery": True,
                    "opportunity_stage": discovered.get("opportunity_stage")}
            add(company_identity(discovered.get("company"), discovered.get("ticker")), "ai",
                f"Reasoning-driven stock discovery: {theme}", category, link)
        candidate = candidates.get(f"ai:{str(discovered.get('ticker') or '').upper()}")
        if candidate is not None:
            candidate["opportunity_stage"] = discovered.get("opportunity_stage")
            candidate["thesis_evidence"] = discovered.get("thesis_evidence", [])
            candidate["confirmation_evidence"] = discovered.get("confirmation_evidence", [])
            candidate["confirmation_missing"] = discovered.get("confirmation_missing", True)

    catalog = BIOTECH_LEADERS + BIOTECH_EMERGING
    active_biotech_trends = set()
    for radar in biotech_radar:
        catalog_row = next((row for row in catalog
                            if company_identity(row.get("company"), row.get("ticker")).get("ticker") == radar.get("ticker")), {})
        text = " ".join(str(radar.get(key, "")) for key in
                        ("program", "indication", "catalyst", "clinical_evidence", "commercial_potential"))
        text += " " + " ".join(str(catalog_row.get(key, "")) for key in
                                ("sector", "technology", "proven_therapy", "pipeline", "lead_programs"))
        trends = biotech_therapeutic_trends(text) or ["Program-specific catalyst"]
        active_biotech_trends.update(trends)
        identity = company_identity(radar.get("company"), radar.get("ticker"))
        for trend in trends:
            link = {"therapeutic_trend": trend, "program": radar.get("program"),
                    "indication": radar.get("indication"), "catalyst": radar.get("catalyst"),
                    "evidence_gate_passed": radar.get("evidence_gate", {}).get("passed"),
                    "evidence_count": radar.get("evidence_count", 0)}
            add(identity, "biotech", f"Company → program → catalyst from Biotech Radar: {radar.get('program')}",
                radar_link=link, therapeutic_trend=trend, program=radar.get("program"),
                indication=radar.get("indication"), catalyst=radar.get("catalyst"))
    for row in catalog:
        text = " ".join(str(row.get(key, "")) for key in
                        ("sector", "technology", "proven_therapy", "pipeline", "lead_programs", "catalysts"))
        trends = active_biotech_trends.intersection(biotech_therapeutic_trends(text))
        for trend in trends:
            add(company_identity(row.get("company"), row.get("ticker")), "biotech",
                f"Existing biotech company map matched active Radar modality: {trend}",
                therapeutic_trend=trend, program=row.get("lead_programs") or row.get("pipeline"),
                catalyst=row.get("catalysts"))

    ai = [item for item in candidates.values() if item["domain"] == "ai"]
    biotech = [item for item in candidates.values() if item["domain"] == "biotech"]
    def rank(row):
        linked = sum(bool(link.get("evidence_ids") or link.get("evidence_count")) for link in row["radar_links"])
        category = max((category_priority.get(item, 0) for item in row["categories"]), default=0)
        return (-linked, -category, -len(row["radar_links"]), row["company"])
    ai = sorted(ai, key=rank)[:AI_CANDIDATE_LIMIT]
    biotech = sorted(biotech, key=rank)[:BIOTECH_CANDIDATE_LIMIT]
    result = ai + biotech
    return {"schema_version": "candidate-discovery-v2", "target_size": "30-50", "candidates": result,
            "coverage": {"total": len(result), "ai": len(ai), "biotech": len(biotech),
                         "evidence_linked": sum(bool(row["radar_links"]) for row in result),
                         "by_ai_category": {category: sum(category in row["categories"] for row in ai)
                                            for category in category_priority}},
            "methodology": {"scope": "Focused beneficiaries of evidence-derived AI themes and existing Radar tracks; no broad market screen.",
                            "ai_flow": "Evidence → structured reasoning → theme discovery → beneficiary discovery → stock discovery → Radar.",
                            "no_manual_ticker_insertion": "Reasoning-driven stocks come from evidence identities and a general listed-company universe, not manually added theme tickers.",
                            "candidate_is_not_conviction": "Discovery is research coverage only and cannot pass any High-Conviction gate.",
                            "biotech_path": "Therapeutic trend → program → company → catalyst when a current Radar record exists; related modality matches remain unverified discovery candidates."}}


def shared_market_ticker_domains(previous=None, candidate_pool=None):
    domains = {}

    def add(ticker, domain):
        ticker = str(ticker or "").strip().upper()
        if not ticker or ticker in ("PRIVATE", "N/A", "MISSING") or ":" in ticker:
            return
        domains.setdefault(ticker, set()).add(domain)

    for row in AI_INFRASTRUCTURE + AI_PLATFORMS:
        add(row.get("ticker"), "ai")
    for row in watch_rows(AI_WATCH):
        add(row.get("ticker"), "ai")
    for row in BIOTECH_CATALYSTS + watch_rows(BIOTECH_WATCH):
        add(row.get("ticker"), "biotech")
    for domain, rows in MONTHLY_PICKS.items():
        for row in rows:
            add(company_identity(row.get("company")).get("ticker"), domain)
    for row in (previous or {}).get("radar", {}).get("ai", []):
        for beneficiary in row.get("beneficiary_records", []):
            add(beneficiary.get("ticker"), "ai")
    for row in (candidate_pool or {}).get("candidates", []):
        add(row.get("ticker"), row.get("domain"))
    return {ticker: sorted(values) for ticker, values in domains.items()}


def build_market_data_layer(previous, run_at, series_by_symbol=None, market_caps=None, expectations_by_ticker=None,
                            candidate_pool=None):
    ticker_domains = shared_market_ticker_domains(previous, candidate_pool)
    benchmark_symbols = {"sp500": "^GSPC", "qqq": "QQQ", "xbi": "XBI"}
    dashboard_symbols = set(MARKETS) | set(benchmark_symbols.values())
    requested_symbols = sorted(set(ticker_domains) | dashboard_symbols)
    supplied_series = series_by_symbol is not None
    if series_by_symbol is None:
        series_by_symbol = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(fetch_market_series, symbol, stooq_symbol_for(symbol)): symbol for symbol in requested_symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    series_by_symbol[symbol] = future.result()
                except Exception as exc:
                    print(f"Market data unavailable for {symbol}: {exc}")
                    series_by_symbol[symbol] = {"symbol": symbol, "rows": [], "source": None, "currency": None}
    if market_caps is None:
        market_caps = fetch_market_caps(set(ticker_domains))
    if expectations_by_ticker is None:
        expectations_by_ticker = {} if supplied_series else fetch_expectation_inputs(set(ticker_domains), run_at)
    benchmarks = {
        name: calculate_market_technicals(symbol, series_by_symbol.get(symbol, {"rows": []}))
        for name, symbol in benchmark_symbols.items()
    }
    benchmarks = {name: record for name, record in benchmarks.items() if record}
    if "sp500" in benchmarks:
        for name in ("qqq", "xbi"):
            if name in benchmarks:
                benchmarks[name]["relative_strength"] = {
                    "sp500": benchmark_relative_strength(benchmarks[name].get("returns", {}), benchmarks["sp500"].get("returns", {}))
                }
    previous_layer = (previous or {}).get("market_data", {})
    previous_securities = previous_layer.get("securities", {})
    securities = {}
    for ticker, domains in ticker_domains.items():
        record = calculate_market_technicals(
            ticker, series_by_symbol.get(ticker, {"rows": []}), benchmarks, market_caps.get(ticker))
        if record:
            expectation = build_expectation_record(ticker, expectations_by_ticker.get(ticker), record, run_at)
            if record.get("market_cap") is None and expectation.get("valuation", {}).get("market_cap") is not None:
                record["market_cap"] = expectation["valuation"]["market_cap"]
                record["missing_fields"] = [field for field in record.get("missing_fields", []) if field != "market_cap"]
            record["expectation_data"] = expectation
            securities[ticker] = {**record, "domains": domains}
        elif ticker in previous_securities:
            securities[ticker] = {**previous_securities[ticker], "domains": domains, "data_status": "stale"}
    indexes = {}
    for symbol in MARKETS:
        record = calculate_market_technicals(symbol, series_by_symbol.get(symbol, {"rows": []}))
        if record:
            indexes[symbol] = record
        elif symbol in previous_layer.get("indexes", {}):
            indexes[symbol] = {**previous_layer["indexes"][symbol], "data_status": "stale"}
    return {
        "schema_version": "shared-market-expectation-v1", "updated_at": run_at.isoformat(timespec="seconds"),
        "sources": ["Yahoo Finance chart (primary price/volume history)", "Stooq daily data (fallback)",
                    "Yahoo Finance quote endpoint (market cap when available)",
                    "Nasdaq company summary, analyst ratings, earnings forecast, and short-interest endpoints"],
        "methodology": {
            "returns": "Close-to-close over 21, 63, and 126 sessions.",
            "relative_strength": "Stock return minus benchmark return in percentage points for the same horizon.",
            "rsi": "14-session RSI.", "macd": "12/26-session EMA MACD with 9-session signal.",
            "entry_timing_inputs": "Adds MA5/10, 42/63-session close ranges, MA compression, volume contraction/up-down volume, prior-60-session close resistance, and close-based support. Rules and source dates are retained in each record.",
            "expectation_state": "Requires at least two input groups. Underpriced, Fairly Priced, and Crowded / Priced In use transparent target-upside, forward-P/E, price-run-up, estimate-revision, and positioning signals; missing inputs remain null.",
            "price_run_up": "Uses existing 1M/3M/6M close-to-close returns as a recent pre-event proxy unless a verified event-specific anchor is available.",
            "missing_data": "Unavailable fields remain null; prior successful security records may be retained with data_status=stale.",
        },
        "benchmarks": benchmarks, "indexes": indexes, "securities": securities,
        "coverage": {"requested": len(ticker_domains), "current": sum(record.get("data_status") == "current" for record in securities.values()),
                     "stale": sum(record.get("data_status") == "stale" for record in securities.values()),
                     "missing": len(ticker_domains) - len(securities),
                     "expectation_current": sum(record.get("expectation_data", {}).get("data_status") == "current" for record in securities.values()),
                     "valuation": sum("valuation" in record.get("expectation_data", {}).get("available_input_groups", []) for record in securities.values()),
                     "analyst_consensus": sum("analyst_consensus" in record.get("expectation_data", {}).get("available_input_groups", []) for record in securities.values()),
                     "short_interest": sum("positioning" in record.get("expectation_data", {}).get("available_input_groups", []) for record in securities.values())},
    }


def market_snapshot(market_data, ticker):
    return (market_data or {}).get("securities", {}).get(str(ticker or "").upper())


def compact_market_snapshot(snapshot):
    if not snapshot:
        return snapshot
    return {key: value for key, value in snapshot.items() if key not in ("expectation_data", "entry_inputs")}


def market_timing_signal(snapshot, domain):
    if not snapshot:
        return {"signal": "Insufficient Data", "support_score": None, "rationale": "No current or retained market record is available."}
    if snapshot.get("data_status") != "current":
        return {"signal": "Insufficient Data", "support_score": None, "rationale": "Only a stale retained market record is available."}
    price = snapshot.get("current_price")
    averages = snapshot.get("moving_averages", {})
    macd_histogram = snapshot.get("macd", {}).get("histogram")
    rsi_value = snapshot.get("rsi_14")
    relative = snapshot.get("relative_strength", {}).get("qqq" if domain == "ai" else "xbi", {}).get("three_month")
    checks = [
        price is not None and averages.get("ma50") is not None and price > averages["ma50"],
        price is not None and averages.get("ma200") is not None and price > averages["ma200"],
        macd_histogram is not None and macd_histogram > 0,
        relative is not None and relative > 0,
    ]
    available_checks = [
        None if price is None or averages.get("ma50") is None else checks[0],
        None if price is None or averages.get("ma200") is None else checks[1],
        None if macd_histogram is None else checks[2], None if relative is None else checks[3]]
    available = sum(value is not None for value in available_checks)
    if available == 0:
        return {"signal": "Insufficient Data", "support_score": None, "rationale": "Required trend and relative-strength inputs are missing."}
    positives = sum(checks)
    support_score = round(positives / available * 100)
    below_ma200 = None if price is None or averages.get("ma200") is None else price < averages["ma200"]
    severe_weakness = available >= 3 and below_ma200 is True and macd_histogram is not None and macd_histogram < 0 and relative is not None and relative < 0
    overextended = rsi_value is not None and rsi_value >= 75
    signal = "Sell" if severe_weakness else "Reduce" if overextended or (support_score < 35 and available >= 3) else "Buy" if support_score >= 75 and not overextended else "Hold"
    return {"signal": signal, "support_score": support_score,
            "rationale": f"{positives} of {available} available trend/relative-strength checks are positive; RSI is {rsi_value if rsi_value is not None else 'missing'}."}


def market_component_score(snapshot, benchmark_name, maximum):
    if not snapshot:
        return None, 0, "Missing: no market record is connected."
    if snapshot.get("data_status") != "current":
        return None, 0, "Missing: the connected market record is stale."
    price = snapshot.get("current_price")
    averages = snapshot.get("moving_averages", {})
    macd_histogram = snapshot.get("macd", {}).get("histogram")
    return_3m = snapshot.get("returns", {}).get("three_month")
    relative_3m = snapshot.get("relative_strength", {}).get(benchmark_name, {}).get("three_month")
    raw_checks = [
        None if price is None or averages.get("ma50") is None else price > averages["ma50"],
        None if price is None or averages.get("ma200") is None else price > averages["ma200"],
        None if macd_histogram is None else macd_histogram > 0,
        None if return_3m is None else return_3m > 0,
        None if relative_3m is None else relative_3m > 0,
    ]
    available = [value for value in raw_checks if value is not None]
    if not available:
        return None, 0, "Missing: price-trend and relative-strength inputs are unavailable."
    score = round(sum(available) / len(available) * maximum)
    return score, maximum, f"{sum(available)} of {len(available)} available market-confirmation checks are positive."


def attach_market_context(rows, market_data, domain, rank_opportunities=False):
    enriched = []
    for row in rows:
        normalized = normalize_company_row(row)
        snapshot = market_snapshot(market_data, normalized.get("ticker"))
        timing = market_timing_signal(snapshot, domain)
        expectation = expectation_assessment(snapshot, domain, 15 if domain == "ai" else 20)
        if rank_opportunities:
            timing = {**timing, "expectation_state": expectation["state"], "expectation_score": expectation["score"],
                      "rationale": f"{timing['rationale']} Expectation state: {expectation['state']}."}
        enriched.append({**normalized, "market_data": compact_market_snapshot(snapshot), "timing_support": timing,
                         "expectation": expectation, "source_rank": normalized.get("rank")})
    if rank_opportunities:
        for row in enriched:
            base_score = max(0, 100 - (max(1, int(row.get("source_rank") or 1)) - 1) * 5)
            inputs = [("existing_research_rank", base_score, 70)]
            timing_score = row["timing_support"].get("support_score")
            expectation_score = row["expectation"].get("score")
            if timing_score is not None:
                inputs.append(("market_timing", timing_score, 15))
            if expectation_score is not None:
                inputs.append(("expectation_gap", round(expectation_score / row["expectation"]["maximum"] * 100), 15))
            total_weight = sum(weight for _, _, weight in inputs)
            row["final_ranking_score"] = round(sum(score * weight for _, score, weight in inputs) / total_weight)
            row["ranking_inputs"] = [{"key": key, "score": score, "weight": weight} for key, score, weight in inputs]
        enriched.sort(key=lambda item: (-item["final_ranking_score"], item.get("source_rank") or 999))
        for rank, row in enumerate(enriched, 1):
            row["rank"] = rank
    return enriched


HIGH_CONVICTION_FACTOR_WEIGHTS = {
    "radar_conviction": 35, "beneficiary_company_quality": 25, "expectation_gap": 20,
    "technical_setup": 15, "near_term_catalyst": 5,
}

HIGH_CONVICTION_CLASSIFICATIONS = {
    "high-conviction": "🔥 High Conviction",
    "watch-setup": "👀 Watch / Setup Forming",
    "too-early": "⏳ Too Early",
    "priced-in": "⚠️ Priced In / Extended",
    "speculative-binary": "⚠️ Speculative Binary",
    "avoid": "❌ Avoid / Thesis Broken",
}


def stock_pick_factor(key, score, rationale, evidence=None, available_weight=None):
    if score is not None:
        score = max(0, min(100, round(score)))
    weight = HIGH_CONVICTION_FACTOR_WEIGHTS[key]
    if score is None:
        available_weight = 0
    elif available_weight is None:
        available_weight = weight
    available_weight = max(0, min(weight, round(available_weight, 2)))
    return {"key": key, "label": key.replace("_", " ").title(),
            "weight": weight, "available_weight": available_weight, "score": score,
            "missing": score is None, "rationale": rationale, "evidence": evidence or []}


def weighted_stock_pick_score(factors):
    available = [factor for factor in factors if factor["score"] is not None]
    if not available:
        return None, 0
    available_weight = sum(factor["available_weight"] for factor in available)
    if not available_weight:
        return None, 0
    score = round(sum(factor["score"] * factor["available_weight"] for factor in available) / available_weight)
    return score, round(available_weight, 2)


def stock_pick_gate(key, label, passed, rationale):
    return {"key": key, "label": label, "passed": passed, "rationale": rationale}


def classify_stock_pick(domain, total_score, completeness, gates, expectation_state, technical, radar_record=None):
    gate_map = {gate["key"]: gate for gate in gates}
    if domain == "biotech" and radar_record:
        integrity = radar_record.get("evidence_integrity_gate", {}).get("concern_identified")
        if integrity or radar_record.get("opportunity_status") == "Thesis Broken":
            return "avoid"
        if radar_record.get("binary_risk") in ("High", "Extreme") or radar_record.get("opportunity_status") in ("Speculative Binary", "High Downside Risk"):
            return "speculative-binary"
    if expectation_state == "Crowded / Priced In" or technical.get("signal") == "Reduce":
        return "priced-in"
    if gate_map.get("evidence", {}).get("passed") is not True or gate_map.get("beneficiary_proof", {}).get("passed") is not True:
        return "too-early"
    if expectation_state == "Data Insufficient" or total_score is None or completeness < 60:
        return "too-early"
    required = ("evidence", "beneficiary_proof", "expectation", "technical_entry")
    if domain == "biotech":
        required += ("binary_integrity",)
    if total_score >= 80 and completeness >= 80 and all(gate_map.get(key, {}).get("passed") is True for key in required):
        return "high-conviction"
    return "watch-setup"


def stock_pick_action(classification_key):
    return {
        "high-conviction": "Consider a staged entry; size the position to the documented risks and invalidation level.",
        "watch-setup": "Watch; wait for the failed gate to confirm or for a better technical entry.",
        "too-early": "Wait for sufficient evidence and beneficiary proof before treating this as an actionable setup.",
        "priced-in": "Avoid chasing; wait for valuation or technical conditions to reset.",
        "speculative-binary": "Speculative only; do not treat the total score as sufficient for normal position sizing.",
        "avoid": "Avoid until new source-backed evidence repairs the thesis and clears the integrity gate.",
    }[classification_key]


def ai_company_catalyst(linked_rows, ticker, fallback=None):
    candidates = []
    for radar, beneficiary in linked_rows:
        evidence_ids = set(beneficiary.get("evidence_ids", []))
        for evidence in radar.get("confirming_evidence", []) + radar.get("mixed_evidence", []):
            if evidence.get("event_id") in evidence_ids and evidence.get("age_band") != "stale":
                candidates.append(evidence)
    if candidates:
        selected = max(candidates, key=lambda item: (
            {"fresh": 3, "current": 2, "aging": 1}.get(item.get("age_band"), 0),
            item.get("event_date") or "",
        ))
        recency_score = {"fresh": 90, "current": 75, "aging": 50}.get(selected.get("age_band"))
        material_types = {"Financial Results", "Capacity / Contract", "M&A / Partnership",
                          "Regulatory", "Product Launch", "Commercial Event"}
        catalyst_score = min(100, recency_score + 5) if recency_score is not None and selected.get("event_type") in material_types else recency_score
        return {"description": selected.get("new_information") or fallback or "Missing",
                "score": catalyst_score, "evidence_id": selected.get("event_id"),
                "date": selected.get("event_date"), "source_link": selected.get("source_link"),
                "score_basis": f"Independent catalyst-timing score based on {selected.get('age_band', 'unknown')} event recency"
                               f" and event type {selected.get('event_type') or 'Missing'}; News Importance is not used."}
    return {"description": fallback or "Missing: no current company-specific News catalyst is connected.",
            "score": None, "evidence_id": None, "date": None, "source_link": None,
            "score_basis": "Missing: no current company-specific News catalyst is connected."}


def company_quality_record(quality_layer, domain, ticker):
    return (quality_layer or {}).get("records", {}).get(f"{domain}:{ticker}")


def compact_company_quality(record):
    if not record:
        return None
    keys = ("company_quality_score", "data_completeness", "confidence", "data_status", "qualified",
            "as_of", "latest_period_end", "statement_age_days", "score_cap", "sources",
            "missing_fields", "qualification_rule")
    return {key: record.get(key) for key in keys}


def combined_quality_factor(beneficiary_score, beneficiary_completeness, company_quality):
    """Blend proof of beneficiary relevance and reported company quality inside the existing 25%."""
    company_score = (company_quality or {}).get("company_quality_score")
    company_completeness = (company_quality or {}).get("data_completeness", 0)
    parts = []
    if beneficiary_score is not None:
        parts.append((beneficiary_score, 12.5 * beneficiary_completeness / 100, "beneficiary proof"))
    if company_score is not None:
        parts.append((company_score, 12.5 * company_completeness / 100, "reported company quality"))
    available = sum(weight for _, weight, _ in parts)
    score = round(sum(score * weight for score, weight, _ in parts) / available) if available else None
    return score, available


def build_ai_stock_picks(ai_radar, market_data, curated_rows, candidate_pool=None, quality_layer=None):
    source_rows = ([row for row in candidate_pool.get("candidates", []) if row.get("domain") == "ai"]
                   if candidate_pool else curated_rows)
    curated = {normalize_company_row(row).get("ticker"): normalize_company_row(row) for row in source_rows}
    candidates = {ticker: {**row, "linked_rows": []} for ticker, row in curated.items() if ticker not in (None, "Private", "N/A", "Missing")}
    for radar in ai_radar:
        for beneficiary in radar.get("beneficiary_records", []):
            ticker = beneficiary.get("ticker")
            if ticker in (None, "Private", "N/A", "Missing"):
                continue
            identity = company_identity(beneficiary.get("company"), ticker)
            candidates.setdefault(ticker, {**identity, "linked_rows": []})["linked_rows"].append((radar, beneficiary))
    results = []
    for ticker, candidate in candidates.items():
        links = candidate.get("linked_rows", [])
        best = max(links, key=lambda item: ((item[0].get("trend_strength") or -1), item[1].get("beneficiary_relevance") or -1)) if links else (None, None)
        radar, beneficiary = best
        snapshot = market_snapshot(market_data, ticker)
        expectation = expectation_assessment(snapshot, "ai", 20)
        technical = market_timing_signal(snapshot, "ai")
        catalyst = ai_company_catalyst(links, ticker, candidate.get("catalyst"))
        radar_score = radar.get("trend_strength") if radar else None
        beneficiary_score = beneficiary.get("beneficiary_relevance") if beneficiary else None
        beneficiary_completeness = beneficiary.get("data_completeness", 0) if beneficiary else 0
        company_quality = company_quality_record(quality_layer, "ai", ticker)
        quality_score, quality_available = combined_quality_factor(
            beneficiary_score, beneficiary_completeness, company_quality)
        expectation_score = round(expectation["score"] / expectation["maximum"] * 100) if expectation.get("score") is not None else None
        technical_score = technical.get("support_score")
        catalyst_score = catalyst.get("score")
        factors = [
            stock_pick_factor("radar_conviction", radar_score,
                              f"{radar.get('trend')}: Trend Strength {radar_score}/100 with {radar.get('confidence')} confidence." if radar else "Missing: no AI Radar track is linked to this company.",
                              [radar.get("trend")] if radar else [],
                              35 * radar.get("data_completeness", 0) / 100 if radar else 0),
            stock_pick_factor("beneficiary_company_quality", quality_score,
                              (f"Evidence-linked beneficiary relevance is {beneficiary_score}/100; reported Company Quality is "
                               f"{company_quality.get('company_quality_score') if company_quality else 'Missing'}/100 "
                               f"with {(company_quality or {}).get('data_completeness', 0)}% completeness."),
                              (beneficiary.get("evidence_ids", []) if beneficiary else []) +
                              [source.get("url") for source in (company_quality or {}).get("sources", [])],
                              quality_available),
            stock_pick_factor("expectation_gap", expectation_score, expectation.get("rationale", "Missing."),
                              [source.get("url") for source in expectation.get("sources", [])],
                              20 * min(1, expectation.get("coverage", 0) / 4)),
            stock_pick_factor("technical_setup", technical_score, technical.get("rationale", "Missing."), [ticker] if technical_score is not None else []),
            stock_pick_factor("near_term_catalyst", catalyst_score,
                              f"{catalyst['description']} {catalyst.get('score_basis', '')}" if catalyst_score is not None else "Missing: no dated company-specific near-term catalyst score is available.",
                              [catalyst["evidence_id"]] if catalyst.get("evidence_id") else []),
        ]
        total_score, completeness = weighted_stock_pick_score(factors)
        evidence_pass = bool(radar and beneficiary and beneficiary.get("evidence_ids") and radar.get("confidence") in ("Medium", "High") and (radar_score or 0) >= 65)
        beneficiary_pass = bool(beneficiary and (beneficiary_score or 0) >= 70 and beneficiary.get("evidence_ids") and
                                company_quality and company_quality.get("qualified"))
        expectation_pass = expectation.get("state") == "Underpriced"
        technical_pass = technical_score is not None and technical_score >= 60 and technical.get("signal") in ("Buy", "Hold")
        gates = [
            stock_pick_gate("evidence", "Evidence Gate", evidence_pass,
                            "Requires a linked Medium/High-confidence Radar track, Trend Strength ≥65, and company-specific evidence."),
            stock_pick_gate("beneficiary_proof", "Beneficiary Proof Gate", beneficiary_pass,
                            "Requires evidence-linked beneficiary relevance ≥70 plus qualified reported Company Quality; discovery alone cannot pass."),
            stock_pick_gate("expectation", "Expectation Gate", expectation_pass,
                            f"Requires Underpriced; current state is {expectation.get('state')}."),
            stock_pick_gate("technical_entry", "Technical / Entry Gate", technical_pass,
                            f"Requires Buy/Hold with technical support ≥60; current signal is {technical.get('signal')} at {technical_score if technical_score is not None else 'Missing'}."),
        ]
        classification_key = classify_stock_pick("ai", total_score, completeness, gates, expectation.get("state"), technical, radar)
        invalidation = radar.get("risks") if radar and not str(radar.get("risks", "")).startswith("Missing") else "Missing: no company-specific thesis invalidation is connected in current Radar evidence."
        why_selected = (f"Linked to {radar.get('trend')} with Radar Conviction {radar_score}/100, beneficiary relevance {beneficiary_score}/100, "
                        f"and Company Quality {(company_quality or {}).get('company_quality_score', 'Missing')}/100; "
                        f"expectation is {expectation.get('state')} and technical entry is {technical.get('signal')}." if radar and beneficiary
                        else "Candidate retained from the existing research list, but current Radar or beneficiary proof is missing.")
        results.append({**{key: value for key, value in candidate.items() if key != "linked_rows"},
                        "ticker": ticker, "company": candidate.get("company") or beneficiary.get("company"),
                        "final_score": total_score, "final_ranking_score": total_score, "data_completeness": completeness,
                        "factor_scores": factors, "gates": gates, "classification_key": classification_key,
                        "classification": HIGH_CONVICTION_CLASSIFICATIONS[classification_key],
                        "why_selected": why_selected, "expectation_state": expectation.get("state"), "expectation": expectation,
                        "technical_entry_status": technical, "catalyst": catalyst["description"], "catalyst_evidence": catalyst,
                        "company_quality": compact_company_quality(company_quality),
                        "company_quality_ref": f"ai:{ticker}",
                        "action": stock_pick_action(classification_key), "thesis_invalidation": invalidation,
                        "market_data": compact_market_snapshot(snapshot), "engine_version": "high-conviction-stock-pick-v1"})
    priority = {key: index for index, key in enumerate(("high-conviction", "watch-setup", "too-early", "priced-in", "speculative-binary", "avoid"))}
    results.sort(key=lambda item: (priority[item["classification_key"]], -(item.get("final_score") or -1), item.get("company") or ""))
    for rank, row in enumerate(results, 1):
        row["rank"] = rank
    return results


def biotech_timing_score(radar_row, as_of):
    source = next((item for item in BIOTECH_CATALYSTS if item.get("ticker") == radar_row.get("ticker") and
                   item.get("program") == radar_row.get("program") and item.get("indication") == radar_row.get("indication")), None)
    if not source:
        return None, "Missing: no matching dated catalyst definition is available."
    score, rationale, missing = timing_component(source, as_of)
    return (None, rationale) if missing else (round(score / 15 * 100), rationale)


def build_biotech_stock_picks(biotech_radar, market_data, curated_rows, as_of,
                              candidate_pool=None, quality_layer=None):
    source_rows = ([row for row in candidate_pool.get("candidates", []) if row.get("domain") == "biotech"]
                   if candidate_pool else curated_rows)
    curated = {normalize_company_row(row).get("ticker"): normalize_company_row(row) for row in source_rows}
    radar_by_ticker = {}
    for row in biotech_radar:
        current = radar_by_ticker.get(row.get("ticker"))
        if not current or (row.get("opportunity_score") or -1) > (current.get("opportunity_score") or -1):
            radar_by_ticker[row.get("ticker")] = row
    tickers = {ticker for ticker in set(curated) | set(radar_by_ticker) if ticker not in (None, "Private", "N/A", "Missing")}
    results = []
    for ticker in tickers:
        candidate = curated.get(ticker, company_identity(None, ticker)); radar = radar_by_ticker.get(ticker)
        snapshot = market_snapshot(market_data, ticker)
        expectation = expectation_assessment(snapshot, "biotech", 20)
        technical = market_timing_signal(snapshot, "biotech")
        radar_score = round(radar["scientific_evidence_score"] / 30 * 100) if radar and radar.get("scientific_evidence_score") is not None else None
        quality_component = next((item for item in radar.get("score_components", []) if item.get("key") == "catalyst_impact_company_sensitivity"), {}) if radar else {}
        beneficiary_score = round(quality_component["score"] / quality_component["available_weight"] * 100) if quality_component.get("score") is not None and quality_component.get("available_weight") else None
        beneficiary_completeness = quality_component.get("available_weight", 0) / 25 * 100
        company_quality = company_quality_record(quality_layer, "biotech", ticker)
        quality_score, quality_available = combined_quality_factor(
            beneficiary_score, beneficiary_completeness, company_quality)
        expectation_score = round(expectation["score"] / expectation["maximum"] * 100) if expectation.get("score") is not None else None
        technical_score = technical.get("support_score")
        catalyst_score, catalyst_rationale = biotech_timing_score(radar, as_of) if radar else (None, "Missing: no Biotech Radar catalyst is linked.")
        factors = [
            stock_pick_factor("radar_conviction", radar_score,
                              f"Scientific Evidence is {radar.get('scientific_evidence_score')}/30 with {radar.get('confidence')} confidence." if radar else "Missing: no Biotech Radar record is linked.",
                              [item.get("event_id") for item in radar.get("confirming_evidence", [])] if radar else []),
            stock_pick_factor("beneficiary_company_quality", quality_score,
                              (f"Program/company sensitivity evidence is {beneficiary_score if beneficiary_score is not None else 'Missing'}/100; "
                               f"reported Company Quality is {company_quality.get('company_quality_score') if company_quality else 'Missing'}/100 "
                               f"with {(company_quality or {}).get('data_completeness', 0)}% completeness."),
                              ([ticker] if beneficiary_score is not None else []) +
                              [source.get("url") for source in (company_quality or {}).get("sources", [])],
                              quality_available),
            stock_pick_factor("expectation_gap", expectation_score, expectation.get("rationale", "Missing."),
                              [source.get("url") for source in expectation.get("sources", [])],
                              20 * min(1, expectation.get("coverage", 0) / 4)),
            stock_pick_factor("technical_setup", technical_score, technical.get("rationale", "Missing."), [ticker] if technical_score is not None else []),
            stock_pick_factor("near_term_catalyst", catalyst_score, catalyst_rationale,
                              [radar.get("catalyst")] if radar and catalyst_score is not None else []),
        ]
        total_score, completeness = weighted_stock_pick_score(factors)
        evidence_pass = bool(radar and radar.get("evidence_gate", {}).get("passed") and (radar.get("scientific_evidence_score") or 0) >= 18)
        beneficiary_pass = bool(radar and quality_component.get("available_weight", 0) >= 15 and
                                beneficiary_score is not None and beneficiary_score >= 60 and
                                company_quality and company_quality.get("qualified"))
        expectation_pass = expectation.get("state") == "Underpriced"
        technical_pass = technical_score is not None and technical_score >= 60 and technical.get("signal") in ("Buy", "Hold")
        binary_pass = bool(radar and radar.get("binary_risk") in ("Low", "Moderate") and
                           not radar.get("evidence_integrity_gate", {}).get("concern_identified") and radar.get("opportunity_status") != "Thesis Broken")
        gates = [
            stock_pick_gate("evidence", "Evidence Gate", evidence_pass, "Requires the Biotech Radar Evidence Gate and Scientific Evidence ≥18/30."),
            stock_pick_gate("beneficiary_proof", "Beneficiary Proof Gate", beneficiary_pass, "Requires direct company/program exposure, at least 15 Catalyst Impact / Company Sensitivity points, and qualified reported Company Quality; discovery alone cannot pass."),
            stock_pick_gate("expectation", "Expectation Gate", expectation_pass, f"Requires Underpriced; current state is {expectation.get('state')}."),
            stock_pick_gate("technical_entry", "Technical / Entry Gate", technical_pass, f"Requires Buy/Hold with technical support ≥60; current signal is {technical.get('signal')} at {technical_score if technical_score is not None else 'Missing'}."),
            stock_pick_gate("binary_integrity", "Biotech Binary Risk / Evidence Integrity Gate", binary_pass,
                            f"Requires Low/Moderate binary risk and no integrity concern; current risk is {radar.get('binary_risk') if radar else 'Missing'}."),
        ]
        classification_key = classify_stock_pick("biotech", total_score, completeness, gates, expectation.get("state"), technical, radar)
        invalidation = radar.get("risks") if radar and radar.get("risks") else "Missing: no program-specific thesis invalidation is connected."
        why_selected = (f"{radar.get('program')} in {radar.get('indication')} has Scientific Evidence {radar.get('scientific_evidence_score') if radar.get('scientific_evidence_score') is not None else 'Missing'}/30 "
                        f"and Company Quality {(company_quality or {}).get('company_quality_score', 'Missing')}/100; "
                        f"expectation is {expectation.get('state')}, and technical entry is {technical.get('signal')}." if radar
                        else "Candidate retained from the existing research list, but no current Company → Program → Indication → Catalyst Radar record is linked.")
        results.append({**candidate, "ticker": ticker, "company": candidate.get("company") or (radar or {}).get("company"),
                        "final_score": total_score, "final_ranking_score": total_score, "data_completeness": completeness,
                        "factor_scores": factors, "gates": gates, "classification_key": classification_key,
                        "classification": HIGH_CONVICTION_CLASSIFICATIONS[classification_key], "why_selected": why_selected,
                        "expectation_state": expectation.get("state"), "expectation": expectation,
                        "technical_entry_status": technical, "catalyst": radar.get("catalyst") if radar else candidate.get("catalyst", "Missing"),
                        "catalyst_timing": radar.get("expected_timing") if radar else "Missing",
                        "company_quality": compact_company_quality(company_quality),
                        "company_quality_ref": f"biotech:{ticker}",
                        "action": stock_pick_action(classification_key), "thesis_invalidation": invalidation,
                        "binary_risk": radar.get("binary_risk") if radar else "Missing", "radar_status": radar.get("opportunity_status") if radar else "Missing",
                        "market_data": compact_market_snapshot(snapshot), "engine_version": "high-conviction-stock-pick-v1"})
    priority = {key: index for index, key in enumerate(("high-conviction", "watch-setup", "too-early", "priced-in", "speculative-binary", "avoid"))}
    results.sort(key=lambda item: (priority[item["classification_key"]], -(item.get("final_score") or -1), item.get("company") or ""))
    for rank, row in enumerate(results, 1):
        row["rank"] = rank
    return results


def build_high_conviction_engine(ai_radar, biotech_radar, market_data, as_of,
                                 candidate_pool=None, quality_layer=None, watchlists=None):
    all_ai = build_ai_stock_picks(ai_radar, market_data, MONTHLY_PICKS["ai"], candidate_pool, quality_layer)
    all_biotech = build_biotech_stock_picks(
        biotech_radar, market_data, MONTHLY_PICKS["biotech"], as_of, candidate_pool, quality_layer)
    entry_timing = build_entry_timing_layer(all_ai, all_biotech, market_data, watchlists)
    # Phase 7 annotates the already-ranked rows; it never reorders or rescoring stock selection.
    selected = {"ai": all_ai[:5], "biotech": all_biotech[:5]}
    all_rows = all_ai + all_biotech
    counts = {label: sum(row["classification_key"] == key for row in all_rows)
              for key, label in HIGH_CONVICTION_CLASSIFICATIONS.items()}
    methodology = {
        "engine_version": "high-conviction-stock-pick-v1", "factor_weights": HIGH_CONVICTION_FACTOR_WEIGHTS,
        "phase_6_integration": "The 25% Beneficiary / Company Quality factor blends evidence-linked beneficiary relevance with reported Company Quality. Qualification is also required by the Beneficiary Proof Gate.",
        "missing_data_policy": "Missing factor scores are excluded and weights are renormalized; missing inputs never become zero.",
        "high_conviction_rule": "A total score of at least 80 and at least 80% data completeness are necessary but not sufficient; every applicable gate must pass.",
        "gates": ["Evidence Gate", "Beneficiary Proof Gate", "Expectation Gate", "Technical / Entry Gate", "Biotech Binary Risk / Evidence Integrity Gate"],
        "classifications": list(HIGH_CONVICTION_CLASSIFICATIONS.values()),
    }
    coverage = {"ai_candidates": len(all_ai), "biotech_candidates": len(all_biotech),
                "selected_ai": len(selected["ai"]), "selected_biotech": len(selected["biotech"]),
                "fully_scored": sum(row["data_completeness"] == 100 for row in all_rows),
                "classification_counts": counts}
    return selected, {"methodology": methodology, "coverage": coverage,
                      "entry_timing_ref": "entry_timing_engine",
                      "selected_tickers": {domain: [row["ticker"] for row in rows] for domain, rows in selected.items()}}, entry_timing


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


def parse_publication_time(value):
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="minutes")
    except (TypeError, ValueError, OverflowError):
        return ""


def contains_term(text, term):
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text.lower()) is not None


def source_quality(source_name):
    lowered = source_name.lower()
    if any(contains_term(lowered, term) for term in PRIMARY_SOURCE_TERMS):
        return 20, "Primary/company source"
    if any(term in lowered for term in PRIMARY_RESEARCH_SOURCES):
        return 20, "Primary research/industry source"
    if any(term in lowered for term in RELIABLE_FINANCIAL_SOURCES):
        return 18, "Reliable financial news source"
    if any(term in lowered for term in RELIABLE_INDUSTRY_SOURCES):
        return 15, "Reliable industry news source"
    return 0, "Source is not in the v1 reliability list"


def affected_ai_trends(text):
    padded = f" {text.lower()} "
    return [segment for segment, keywords in AI_INDUSTRY_MAP if any(keyword in padded for keyword in keywords)]


def clean_news_headline(title, source_name):
    if source_name:
        return re.sub(rf"\s+-\s+{re.escape(source_name)}\s*$", "", title, flags=re.IGNORECASE).strip()
    return title.strip()


def news_fingerprint(headline, source_name):
    normalized = re.sub(r"[^a-z0-9]+", " ", f"{headline} {source_name}".lower()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def named_ai_companies(text):
    return [identity["company"] for identity in company_identities_in_text(text, "ai")]


def news_event_family(text):
    lowered = text.lower()
    families = [
        ("financial-results", ("earnings", "financial results", "revenue", "guidance", "outlook")),
        ("deal", ("acquisition", "acquires", "merger", "partnership", "financing")),
        ("capacity-contract", ("capacity", "contract", "orders", "backlog", "construction", "deploy", "additional gpu")),
        ("policy", ("export", "sanction", "regulation", "antitrust", "approval")),
        ("product", ("launch", "unveils", "roadmap", "platform", "model", "computer", "processor", "gpu", "cpu", "robotics")),
        ("power-grid", ("power", "electrical", "grid", "energy", "cooling")),
    ]
    return next((name for name, terms in families if any(term in lowered for term in terms)), "general")


def extract_evidence_facts(text, limit=3):
    cleaned = plain_text(text)
    targeted = re.findall(r"Revenue is expected to be\s+\$?[\d.]+\s+(?:billion|million)[^.]{0,260}\.", cleaned, flags=re.IGNORECASE)
    sentences = targeted + re.split(r"(?<=[.!?])\s+", cleaned)
    ranked = []
    evidence_terms = INVESTMENT_EVENT_TERMS + FORWARD_SIGNAL_TERMS + ("data center", "gpu", "hbm", "power", "ai infrastructure")
    for index, sentence in enumerate(sentences):
        if 25 <= len(sentence) <= 420 and re.search(r"\d", sentence) and any(term in sentence.lower() for term in evidence_terms):
            lowered = sentence.lower()
            relevance = sum(3 for term in ("revenue", "guidance", "outlook", "expected", "capacity", "contract", "gpu", "data center", "investment") if term in lowered)
            relevance += sum(2 for term in ("up ", "down ", "year ago", "year-over-year", "additional", "deploy", "billion", "trillion") if term in lowered)
            relevance += 4 if "revenue is expected" in lowered else 0
            relevance -= sum(5 for term in ("dividend", "share repurchase", "years ago", "birthday", "anniversary") if term in lowered)
            ranked.append((relevance, -index, sentence.strip()))
    return [sentence for _, _, sentence in sorted(ranked, reverse=True)[:limit]]


def enrich_primary_evidence(item):
    evidence = extract_evidence_facts(" ".join((item.get("title", ""), item.get("description", ""), item.get("feed_content", ""))))
    url = item.get("url", "")
    if len(evidence) < 3 and url.startswith("http") and "news.google.com" not in url:
        try:
            page = fetch(url, timeout=12).decode("utf-8", "ignore")
            evidence = extract_evidence_facts(page, limit=3) or evidence
        except Exception as exc:
            print(f"Primary evidence page unavailable for {item.get('source', 'source')}: {exc}")
    item["primary_evidence"] = evidence
    return item


def cluster_ai_news_items(items):
    clusters = {}
    for item in items:
        source_points, source_label = source_quality(item.get("source", ""))
        if not source_points:
            continue
        text = " ".join((item.get("title", ""), item.get("description", "")))
        trends = affected_ai_trends(text)
        if not trends:
            continue
        title_companies = named_ai_companies(item.get("title", ""))
        companies = title_companies or named_ai_companies(text)
        published = parse_publication_time(item.get("date", ""))
        week = datetime.fromisoformat(published).strftime("%G-W%V") if published else "undated"
        family = news_event_family(text)
        identity = "+".join(sorted(set(companies[:2]))) if companies else re.sub(r"[^a-z0-9]+", "-", clean_news_headline(item.get("title", ""), item.get("source", "")).lower())[:55]
        if family in ("product", "general"):
            identity += ":" + news_fingerprint(clean_news_headline(item.get("title", ""), item.get("source", "")), "topic")[:10]
        key = (identity, family, week)
        prepared = dict(item, _source_points=source_points, _source_label=source_label)
        clusters.setdefault(key, []).append(prepared)
    results = []
    for (identity, family, week), members in clusters.items():
        representative = sorted(members, key=lambda item: (not item.get("is_primary", False), -item["_source_points"], item.get("source", "")))[0]
        sources = []
        seen_sources = set()
        for member in members:
            clean_title = clean_news_headline(member.get("title", ""), member.get("source", ""))
            source_key = (member.get("source", ""), clean_title)
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            sources.append({"title": clean_title,
                            "source": member.get("source", ""), "date": parse_publication_time(member.get("date", "")),
                            "url": member.get("url", ""), "source_type": member["_source_label"],
                            "primary": bool(member.get("is_primary") or member["_source_label"].startswith("Primary"))})
        cluster_text = " ".join(" ".join((member.get("title", ""), member.get("description", ""),
                                           " ".join(member.get("primary_evidence", []))))
                                for member in members)
        results.append(dict(representative, _cluster_identity=identity, _event_family=family, _cluster_week=week,
                            _cluster_text=cluster_text, evidence_sources=sources,
                            primary_evidence=[fact for member in members for fact in member.get("primary_evidence", [])]))
    return results


EVENT_TYPE_LABELS = {
    "financial-results": "Financial Results",
    "deal": "Partnership / Transaction",
    "capacity-contract": "Capacity / Contract",
    "policy": "Policy / Regulation",
    "product": "Product / Platform",
    "power-grid": "Power / Grid",
    "general": "Company Update",
}


def news_new_information(facts, headline):
    if facts:
        distinct = []
        normalized = []
        for fact in facts:
            clean = re.sub(r"\s+-\s+[^-]+$", "", fact).strip()
            key = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip()
            if any(key in prior or prior in key for prior in normalized):
                continue
            distinct.append(clean); normalized.append(key)
        return " ".join(f"{fact.rstrip('. ')}." for fact in distinct[:2])
    return f"The source reports: {headline}."


def news_direction(text):
    lowered = text.lower()
    positive = any(term in lowered for term in (
        " up ", "growth", "record", "expand", "additional", "increase", "deploy", "launch",
        "full production", "accelerat", "investment", "capacity", "raises guidance",
    ))
    negative = any(term in lowered for term in (
        " down ", "decline", "fell", "cut guidance", "delay", "halt", "cancel", "shortage",
        "ban", "restriction", "sanction",
    ))
    if positive and negative:
        return "Mixed"
    if positive:
        return "Expanding"
    if negative:
        return "Contracting / Restrictive"
    return "Unclear / not established"


def score_ai_news_item(item, run_at, previous_trends, previous_ids):
    source_name = item.get("source", "").strip()
    source_points, source_label = source_quality(source_name)
    if not source_points:
        return None
    headline = clean_news_headline(item.get("title", ""), source_name)
    combined_text = f" {item.get('_cluster_text') or headline} "
    combined = combined_text.lower()
    headline_context = f" {headline} {item.get('description', '')} ".lower()
    if any(term in headline_context for term in ("birthday", "anniversary", "years ago", "looking back")):
        return None
    trends = affected_ai_trends(combined)
    if not trends:
        return None
    event_hits = sorted({term for term in INVESTMENT_EVENT_TERMS if term in combined})
    named_companies = named_ai_companies(combined)
    identity_fields = company_identity_fields(combined_text, domain="ai")
    quantified_headline = re.search(r"(?:[$€£]\s?\d|\d[\d,.]*\s*(?:million|billion|trillion|gpus?|megawatts?|gigawatts?|%))", headline, flags=re.IGNORECASE)
    headline_facts = [headline] if quantified_headline and any(term in headline.lower() for term in INVESTMENT_EVENT_TERMS) else []
    facts = list(dict.fromkeys(headline_facts + item.get("primary_evidence", []) + extract_evidence_facts(combined_text)))[:3]
    evidence_sources = item.get("evidence_sources", [])
    has_primary = bool(item.get("is_primary") or source_label.startswith("Primary") or any(source.get("primary") for source in evidence_sources))
    published_at = parse_publication_time(item.get("date", ""))
    recent_points = 0
    if published_at:
        age_hours = max(0, (run_at - datetime.fromisoformat(published_at)).total_seconds() / 3600)
        recent_points = 5 if age_hours <= 72 else 2 if age_hours <= 168 else 0
    materiality = min(15, len(event_hits) * 5) + (10 if facts else 0)
    if any(term in combined for term in ("record", "billion", "trillion", "more than doubled", "additional", "shortage", "capacity crunch")):
        materiality += 5
    materiality = min(30, materiality)
    industry_reach = min(15, len(trends) * 5)
    corroboration = 5 if len(evidence_sources) >= 2 else 0
    importance = min(100, 5 + source_points + materiality + industry_reach + (10 if has_primary else 0)
                     + (10 if named_companies else 0) + corroboration + recent_points)
    map_names = [segment for segment, _ in AI_INDUSTRY_MAP]
    last_direct = max(map_names.index(trend) for trend in trends)
    second_order = [segment for segment in map_names[last_direct + 1:last_direct + 3] if segment not in trends]
    if importance < 70:
        return None
    story_id = news_fingerprint(f"{item.get('_cluster_identity', headline)} {item.get('_event_family', '')} {item.get('_cluster_week', '')}", "cluster")
    if importance >= 85 and any(term in combined for term in TREND_CHANGE_TERMS):
        status = "TREND-CHANGING"
    elif story_id in previous_ids:
        status = "CONFIRMING"
    else:
        status = "NEW"
    impact_chain = f"Direct: {', '.join(trends)}. Second-order: {', '.join(second_order) if second_order else 'Missing / not established'}."
    missing = []
    if not facts:
        missing.append("Quantified primary-source facts")
    if not has_primary:
        missing.append("Primary source")
    if not published_at:
        missing.append("Publication date/time")
    if not item.get("url"):
        missing.append("Source link")
    return {
        "id": story_id, "headline": headline, "published_at": published_at, "source": source_name,
        **identity_fields,
        "source_type": source_label, "news_importance_score": importance,
        "event_type": EVENT_TYPE_LABELS.get(item.get("_event_family", "general"), "Company Update"),
        "new_information": news_new_information(facts, headline),
        "direction": news_direction(combined_text), "status": status,
        "affected_trends": trends, "direct_effects": trends, "second_order_effects": second_order,
        "impact_chain": impact_chain,
        "source_link": item.get("url", ""), "publisher_url": item.get("publisher_url", ""),
        "evidence_sources": evidence_sources,
        "score_evidence": {
            "source_quality": {"points": source_points, "basis": source_label},
            "materiality": {"points": materiality, "facts": facts},
            "industry_reach": {"points": industry_reach, "direct_segments": trends, "second_order_segments": second_order},
            "primary_confirmation": {"points": 10 if has_primary else 0, "available": has_primary},
            "corroboration": {"points": corroboration, "source_count": len(evidence_sources)},
            "investment_event_terms": event_hits,
            "named_companies": named_companies,
        },
        "missing_data": missing, "first_seen": run_at.isoformat(timespec="minutes"), "quality_schema_version": 4,
    }


def collect_ai_investment_news(run_at=None):
    current_time = run_at or datetime.now(timezone.utc)
    combined = []
    seen = set()
    official = []
    for source_name, url, publisher_url in OFFICIAL_AI_FEEDS:
        official.extend(official_feed_items(source_name, url, publisher_url, 20))
    recent_official = []
    for item in official:
        text = " ".join((item.get("title", ""), item.get("description", "")))
        published = parse_publication_time(item.get("date", ""))
        recent = published and (current_time - datetime.fromisoformat(published)).days <= 7
        if recent:
            if affected_ai_trends(text) and any(term in text.lower() for term in INVESTMENT_EVENT_TERMS):
                enrich_primary_evidence(item)
            recent_official.append(item)
    for item in recent_official:
        key = (item.get("title", ""), item.get("source", ""))
        if key not in seen:
            seen.add(key); combined.append(item)
    for query in AI_NEWS_QUERIES:
        for item in rss_items(query, 25):
            key = (item.get("title", ""), item.get("source", ""))
            if key not in seen:
                seen.add(key); combined.append(item)
    return combined


def sanitize_news_story(story):
    clean = dict(story)
    prior_explanation = clean.pop("why_it_matters", "")
    clean.pop("future_signal_score", None)
    clean.pop("potential_beneficiaries", None)
    clean["quality_schema_version"] = 4
    if not clean.get("new_information"):
        match = re.search(r"New information:\s*(.*?)(?:\s+Direct effect:|$)", prior_explanation)
        clean["new_information"] = match.group(1).strip() if match else f"The source reports: {clean.get('headline', 'Headline missing')}."
    event_text = " ".join((clean.get("headline", ""), clean.get("new_information", "")))
    inferred_event_type = EVENT_TYPE_LABELS.get(news_event_family(event_text), "Company Update")
    inferred_direction = news_direction(event_text)
    clean["event_type"] = inferred_event_type
    if not clean.get("direction") or (clean["direction"] == "Unclear / not established" and inferred_direction != "Unclear / not established"):
        clean["direction"] = inferred_direction
    clean["missing_data"] = [item for item in clean.get("missing_data", [])
                             if not str(item).lower().startswith("potential beneficiaries")]
    clean.update(company_identity_fields(event_text, clean.get("company"), clean.get("ticker"), "ai"))
    return clean


def build_news_radar_interface(current_stories, archived_stories):
    events = []
    for archived, stories in ((False, current_stories), (True, archived_stories)):
        for story in stories:
            events.append({
                "event_id": story.get("id"),
                "event_date": story.get("published_at"),
                "headline": story.get("headline"),
                "company": story.get("company"),
                "ticker": story.get("ticker"),
                "exchange": story.get("exchange"),
                "listing_status": story.get("listing_status"),
                "related_companies": story.get("related_companies", []),
                "related_tickers": story.get("related_tickers", []),
                "company_identities": story.get("company_identities", []),
                "event_type": story.get("event_type"),
                "direction": story.get("direction"),
                "confirmation_status": story.get("status"),
                "news_importance_score": story.get("news_importance_score"),
                "new_information": story.get("new_information"),
                "affected_trends": story.get("affected_trends", []),
                "direct_effects": story.get("direct_effects", []),
                "second_order_effects": story.get("second_order_effects", []),
                "evidence_sources": story.get("evidence_sources", []),
                "source_link": story.get("source_link", ""),
                "archived": archived,
            })
    return {
        "schema_version": "news-to-radar-evidence-v1",
        "description": "Source-backed news-event evidence only; contains no Radar scores or opportunity rankings.",
        "events": events,
    }


def deduplicate_news_records(records):
    by_headline = {}
    for item in records:
        key = re.sub(r"[^a-z0-9]+", " ", item.get("headline", "").lower()).strip() or item.get("id")
        existing = by_headline.get(key)
        if not existing or (item.get("news_importance_score", 0), item.get("published_at") or item.get("first_seen", "")) > (
                existing.get("news_importance_score", 0), existing.get("published_at") or existing.get("first_seen", "")):
            by_headline[key] = item
    return list(by_headline.values())


def build_ai_news_section(items, previous_section, run_at):
    previous_current = [sanitize_news_story(item) for item in previous_section.get("stories", [])
                        if source_quality(item.get("source", ""))[0] and item.get("quality_schema_version") in (3, 4)]
    previous_archive = deduplicate_news_records(
        sanitize_news_story(item) for item in previous_section.get("important_news_archive", [])
        if source_quality(item.get("source", ""))[0] and item.get("quality_schema_version") in (3, 4))
    previous_records = previous_current + previous_archive
    previous_ids = {item.get("id") for item in previous_records if item.get("id")}
    previous_trends = {trend for item in previous_records for trend in item.get("affected_trends", [])}
    scored = [score_ai_news_item(item, run_at, previous_trends, previous_ids) for item in cluster_ai_news_items(items)]
    selected = sorted((item for item in scored if item),
                      key=lambda item: (-item["news_importance_score"], item["headline"]))[:5]
    if not selected:
        return {"stories": previous_current, "important_news_archive": previous_archive,
                "radar_evidence_interface": build_news_radar_interface(previous_current, previous_archive),
                "selection_status": "No qualifying new stories were available; the prior selection was preserved.",
                "methodology": ai_news_methodology()}
    selected_ids = {item["id"] for item in selected}
    selected_evidence_urls = {source.get("url") for item in selected for source in item.get("evidence_sources", []) if source.get("url")}
    archive_by_id = {item["id"]: item for item in previous_archive if item.get("id") and item["id"] not in selected_ids}
    for item in previous_current:
        if item.get("id") and item["id"] not in selected_ids and item.get("source_link") not in selected_evidence_urls:
            archive_by_id.setdefault(item["id"], item)
    archive = sorted(deduplicate_news_records(archive_by_id.values()),
                     key=lambda item: item.get("published_at") or item.get("first_seen", ""), reverse=True)
    return {"stories": selected, "important_news_archive": archive,
            "radar_evidence_interface": build_news_radar_interface(selected, archive),
            "selection_status": f"Selected {len(selected)} source-qualified, investment-relevant stories.",
            "methodology": ai_news_methodology()}


def ai_news_methodology():
    return {
        "engine_version": "ai-technology-news-v1.1",
        "industry_map": [segment for segment, _ in AI_INDUSTRY_MAP],
        "minimum_importance_score": 70,
        "source_policy": "Official company feeds are ingested directly and clustered with configured reliable financial and industry coverage. Unsupported publishers do not qualify.",
        "archive_policy": "Prior selected stories move to the archive when they leave the current top-news set; records are deduplicated by normalized headline and source.",
        "scoring_note": "Importance uses source quality, quantified materiality, direct industry reach, primary confirmation, company specificity, corroboration and recency. News does not calculate Radar scores or rank investment opportunities.",
        "selection_policy": "At most five stories are shown. No quota is filled; only stories scoring at least 70 qualify.",
    }


def biotech_source_quality(source_name):
    lowered = source_name.lower()
    if any(contains_term(lowered, term) for term in BIOTECH_PRIMARY_SOURCE_TERMS):
        return 15, "Primary/company or regulator source"
    if any(term in lowered for term in BIOTECH_SCIENTIFIC_SOURCES):
        return 15, "Primary peer-reviewed scientific source"
    if any(term in lowered for term in RELIABLE_FINANCIAL_SOURCES):
        return 12, "Reliable financial news source"
    if any(term in lowered for term in BIOTECH_INDUSTRY_SOURCES):
        return 10, "Reliable biotech industry source"
    if re.search(r"(?:therapeutics|pharmaceuticals|biosciences|biopharma|biotech)(?: investor relations)?$", lowered):
        return 15, "Primary/company source"
    return 0, "Source is not in the Biotech News V1 reliability list"


def named_biotech_company(text):
    identity = company_identity_fields(text, domain="biotech")
    if identity["ticker"] != "Missing":
        return identity["company"], identity["ticker"]
    generic = re.search(r"\b([A-Z][A-Za-z0-9&.' -]{2,55}?(?:Therapeutics|Pharmaceuticals|Biosciences|Biopharma|Biotech))\b", text)
    if generic:
        return generic.group(1).strip(), "Missing"
    headline_company = re.search(r"^([A-Z][A-Za-z0-9&.']{1,30})\s+(?:(?:finally|now)\s+)?(?:reports|announces|details|says|nabs|pens|launches|wins|secures|acquires|halts|delays)\b", text)
    return (headline_company.group(1).strip(), "Missing") if headline_company else ("Missing / not established", "Missing")


def named_biotech_program(text):
    for program in BIOTECH_PROGRAMS:
        if contains_term(text, program):
            return program
    match = re.search(r"\b(?:[A-Z]{2,8}|mRNA)-?\d{2,5}\b", text)
    return match.group(0) if match else "Missing / not established"


def biotech_indication(text):
    patterns = (
        r"(?:for (?:the treatment of )?|in patients with )([A-Za-z][A-Za-z0-9 -]{3,70}?)(?:[.;,]| in a | who | with )",
        r"(?:treating|treatment for) ([A-Za-z][A-Za-z0-9 -]{3,70}?)(?:[.;,]| in a | who | with )",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "Missing / not established"


def biotech_event_type(text):
    lowered = text.lower()
    event_types = (
        ("Regulatory / FDA", ("fda approval", "approved", "complete response letter", " crl", "clinical hold", "bla", "nda", "pdufa", "fast track", "breakthrough therapy")),
        ("Catalyst Timing Change", ("delayed", "delay", "accelerated", "timeline", "now expects", "rescheduled")),
        ("Competitor Event", ("competitor", "rival", "head-to-head")),
        ("Clinical Results", ("clinical results", "trial results", "trial win", "topline", "readout", "primary endpoint", "phase 1", "phase 2", "phase 3", "pivotal")),
        ("M&A / Licensing / Partnership", ("acquisition", "acquires", "merger", "license", "licensing", "partnership", "deal")),
        ("Capital Markets / Financing", ("ipo", "financing", "offering", "spac")),
        ("Commercial Event", ("launch", "commercial", "sales", "reimbursement", "manufacturing")),
        ("Scientific / Platform", ("platform", "proof-of-concept", "publication", "mechanism", "preclinical")),
    )
    return next((label for label, terms in event_types if any(term in lowered for term in terms)), "Biotech Sector Event")


def biotech_stage(text, event_type):
    lowered = text.lower()
    if "phase 3" in lowered or "pivotal" in lowered:
        return "Phase 3 / Pivotal"
    if "phase 2" in lowered:
        return "Phase 2"
    if "phase 1" in lowered:
        return "Phase 1"
    if "preclinical" in lowered:
        return "Preclinical"
    if any(term in lowered for term in ("approved", "fda approval", "launch", "commercial")):
        return "Regulatory decision / Commercial"
    if any(term in lowered for term in ("bla", "nda", "pdufa", "clinical hold", "fast track")):
        return "Regulatory review"
    if event_type == "M&A / Licensing / Partnership":
        return "Corporate transaction"
    if event_type == "Scientific / Platform":
        return "Scientific / Platform evidence"
    return "Missing / not established"


def biotech_radar_factors(text):
    lowered = text.lower()
    factors = []
    mappings = (
        ("Clinical Evidence", ("clinical", "trial", "endpoint", "readout", "phase 1", "phase 2", "phase 3", "pivotal")),
        ("Regulatory Status", ("fda", "approval", "crl", "clinical hold", "bla", "nda", "pdufa", "fast track")),
        ("Catalyst Timing", ("delay", "timeline", "expects", "scheduled", "accelerated", "pdufa")),
        ("Competitive Landscape", ("competitor", "rival", "head-to-head")),
        ("Corporate Strategy", ("acquisition", "merger", "license", "partnership", "deal")),
        ("Capital / Financing", ("ipo", "financing", "offering", "spac")),
        ("Commercialization", ("launch", "sales", "commercial", "reimbursement", "manufacturing")),
        ("Platform Validation", ("platform", "proof-of-concept", "gene editing", "gene therapy", "rna", "cell therapy", "publication")),
    )
    for label, terms in mappings:
        if any(term in lowered for term in terms):
            factors.append(label)
    return factors or ["Biotech Sector Context"]


def biotech_subsectors(text):
    lowered = text.lower()
    mappings = (
        ("Rare Disease", ("rare disease", "orphan", "dravet", "hae", "alpha-1 antitrypsin")),
        ("Oncology", ("cancer", "oncology", "tumor", "leukemia", "lymphoma")),
        ("Vaccines / Infectious Disease", ("vaccine", "covid", "influenza", "rsv", "infectious")),
        ("Neurology", ("neurology", "neuro", "alzheimer", "parkinson", "epilepsy")),
        ("Cardiometabolic", ("obesity", "diabetes", "cardio", "metabolic", "kidney")),
        ("Immunology", ("immunology", "autoimmune", "inflammation")),
        ("Genetic Medicines", ("gene therapy", "gene editing", "crispr", "rna", "cell therapy", "mrna")),
    )
    result = [label for label, terms in mappings if any(term in lowered for term in terms)]
    return result or ["Biotech Sector"]


def biotech_direction(text):
    lowered = text.lower()
    positive = any(term in lowered for term in (
        "positive", "met endpoint", "trial win", "approved", "fda approval", "lifted hold", "accelerated", "earlier", "increase", "growth", "launch", "acquisition", "partnership",
    ))
    negative = any(term in lowered for term in (
        "failed", "missed endpoint", "complete response letter", "clinical hold", "delayed", "discontinued", "terminated", "safety signal", "decline",
    ))
    if positive and negative:
        return "Mixed"
    if positive:
        return "Positive / Advancing"
    if negative:
        return "Negative / Delaying"
    return "Neutral / not established"


def extract_biotech_facts(text, limit=3):
    cleaned = plain_text(text)
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    ranked = []
    for index, sentence in enumerate(sentences):
        lowered = sentence.lower()
        if not 20 <= len(sentence) <= 450 or not any(term in lowered for term in BIOTECH_EVENT_TERMS):
            continue
        authority = sum(3 for term in ("primary endpoint", "phase 3", "pivotal", "approved", "complete response letter", "clinical hold", "acquisition") if term in lowered)
        specificity = 5 if re.search(r"(?:\d|\$|%)", sentence) else 0
        ranked.append((authority + specificity, -index, sentence.strip()))
    return [sentence for _, _, sentence in sorted(ranked, reverse=True)[:limit]]


def enrich_biotech_primary_evidence(item):
    evidence = extract_biotech_facts(" ".join((item.get("title", ""), item.get("description", ""), item.get("feed_content", ""))))
    url = item.get("url", "")
    if len(evidence) < 3 and url.startswith("http") and "news.google.com" not in url:
        try:
            evidence = extract_biotech_facts(fetch(url, timeout=12).decode("utf-8", "ignore"), limit=3) or evidence
        except Exception as exc:
            print(f"Biotech primary evidence page unavailable for {item.get('source', 'source')}: {exc}")
    item["primary_evidence"] = evidence
    return item


def cluster_biotech_news_items(items):
    clusters = {}
    for item in items:
        authority, source_label = biotech_source_quality(item.get("source", ""))
        if not authority:
            continue
        clean_title = clean_news_headline(item.get("title", ""), item.get("source", ""))
        text = " ".join((clean_title, item.get("description", ""), " ".join(item.get("primary_evidence", []))))
        if not any(term in text.lower() for term in BIOTECH_EVENT_TERMS):
            continue
        company, ticker = named_biotech_company(text)
        program = named_biotech_program(text)
        event_type = biotech_event_type(text)
        published = parse_publication_time(item.get("date", ""))
        week = datetime.fromisoformat(published).strftime("%G-W%V") if published else "undated"
        identity = f"{ticker}:{program}:{event_type}" if ticker != "Missing" else news_fingerprint(clean_news_headline(item.get("title", ""), item.get("source", "")), "biotech-topic")
        key = (identity, week)
        clusters.setdefault(key, []).append(dict(item, _source_authority=authority, _source_label=source_label,
                                                  _company=company, _ticker=ticker, _program=program,
                                                  _event_type=event_type, _cluster_identity=identity,
                                                  _cluster_week=week))
    results = []
    for _cluster_key, members in clusters.items():
        representative = sorted(members, key=lambda item: (not item.get("is_primary", False), -item["_source_authority"]))[0]
        sources = []
        seen = set()
        for member in members:
            key = (member.get("source", ""), member.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            sources.append({"title": clean_news_headline(member.get("title", ""), member.get("source", "")),
                            "source": member.get("source", ""), "date": parse_publication_time(member.get("date", "")),
                            "url": member.get("url", ""), "source_type": member["_source_label"],
                            "primary": bool(member.get("is_primary") or member["_source_authority"] == 15)})
        cluster_text = " ".join(" ".join((member.get("title", ""), member.get("description", ""),
                                           " ".join(member.get("primary_evidence", [])))) for member in members)
        results.append(dict(representative, _cluster_text=cluster_text, evidence_sources=sources,
                            primary_evidence=[fact for member in members for fact in member.get("primary_evidence", [])]))
    return results


def biotech_state_change(text, new_information):
    match = re.search(r"\bfrom ([^.]{3,80}?) to ([^.]{3,80}?)(?:[.;]|$)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "Missing / not established", new_information


def score_biotech_news_item(item, run_at, previous_ids):
    source_name = item.get("source", "").strip()
    authority, source_label = biotech_source_quality(source_name)
    if not authority:
        return None
    headline = clean_news_headline(item.get("title", ""), source_name)
    combined_text = item.get("_cluster_text") or " ".join((headline, item.get("description", "")))
    lowered = combined_text.lower()
    if not any(term in lowered for term in BIOTECH_EVENT_TERMS):
        return None
    event_type = item.get("_event_type") or biotech_event_type(combined_text)
    company, ticker = (item.get("_company"), item.get("_ticker")) if item.get("_company") else named_biotech_company(combined_text)
    identity_fields = company_identity_fields(combined_text, company, ticker, "biotech")
    company, ticker = identity_fields["company"], identity_fields["ticker"]
    program = item.get("_program") or named_biotech_program(combined_text)
    indication = biotech_indication(combined_text)
    facts = list(dict.fromkeys(item.get("primary_evidence", []) + extract_biotech_facts(combined_text)))[:3]
    new_information = news_new_information(facts, headline)
    previous_state, new_state = biotech_state_change(combined_text, new_information)
    factors = biotech_radar_factors(combined_text)
    subsectors = biotech_subsectors(combined_text)
    evidence_sources = item.get("evidence_sources", [])
    published_at = parse_publication_time(item.get("date", ""))
    story_id = news_fingerprint(f"{item.get('_cluster_identity', headline)} {item.get('_cluster_week', '')}", "biotech-cluster")

    major = ("fda approval", "approved", "complete response letter", "clinical hold", "phase 3", "pivotal", "primary endpoint", "trial win", "acquisition", "merger")
    medium = ("phase 2", "bla", "nda", "pdufa", "licensing", "license", "deal", "topline", "readout", "launch", "ipo", "financing")
    event_significance = 30 if any(term in lowered for term in major) else 24 if any(term in lowered for term in medium) else 18 if event_type != "Biotech Sector Event" else 12
    company_impact = (8 if not company.startswith("Missing") else 0) + (5 if program != "Missing / not established" else 0)
    company_impact += 5 if re.search(r"(?:\d|\$|%)", combined_text) else 0
    company_impact += min(7, len(factors) * 2 + len(subsectors))
    company_impact = min(25, company_impact)
    age_hours = None
    if published_at:
        age_hours = max(0, (run_at - datetime.fromisoformat(published_at)).total_seconds() / 3600)
    novelty = 20 if story_id not in previous_ids or (age_hours is not None and age_hours <= 168) else 12
    immediacy = 10 if age_hours is not None and age_hours <= 72 else 7 if age_hours is not None and age_hours <= 168 else 3 if age_hours is not None and age_hours <= 336 else 0
    importance = event_significance + company_impact + novelty + authority + immediacy
    if importance < 65:
        return None
    status = "CONFIRMING" if story_id in previous_ids else "NEW"
    missing = []
    for label, value in (("Company/ticker", ticker), ("Drug/program", program), ("Indication", indication),
                         ("Development stage", biotech_stage(combined_text, event_type))):
        if str(value).startswith("Missing"):
            missing.append(label)
    if not facts:
        missing.append("Detailed source facts")
    if not published_at:
        missing.append("Publication date/time")
    return {
        "id": story_id, "headline": headline, "company": company, "ticker": ticker,
        **identity_fields,
        "drug_program": program, "indication": indication, "event_type": event_type,
        "development_stage": biotech_stage(combined_text, event_type), "new_information": new_information,
        "previous_state": previous_state, "new_state": new_state, "direction": biotech_direction(combined_text),
        "news_importance_score": importance, "affected_radar_factors": factors, "subsectors": subsectors,
        "status": status, "published_at": published_at, "source": source_name, "source_type": source_label,
        "source_link": item.get("url", ""), "publisher_url": item.get("publisher_url", ""),
        "evidence_sources": evidence_sources,
        "score_evidence": {
            "event_significance": {"score": event_significance, "weight": 30},
            "company_sector_impact": {"score": company_impact, "weight": 25},
            "novelty": {"score": novelty, "weight": 20},
            "evidence_authority": {"score": authority, "weight": 15, "basis": source_label},
            "immediacy": {"score": immediacy, "weight": 10},
        },
        "missing_data": missing, "first_seen": run_at.isoformat(timespec="minutes"), "quality_schema_version": 1,
    }


def collect_biotech_investment_news(run_at=None):
    current_time = run_at or datetime.now(timezone.utc)
    combined = []
    seen = set()
    official = []
    for source_name, url, publisher_url in OFFICIAL_BIOTECH_FEEDS:
        official.extend(official_feed_items(source_name, url, publisher_url, 20))
    for item in official:
        text = " ".join((item.get("title", ""), item.get("description", "")))
        published = parse_publication_time(item.get("date", ""))
        if published and (current_time - datetime.fromisoformat(published)).days <= 7 and any(term in text.lower() for term in BIOTECH_EVENT_TERMS):
            enrich_biotech_primary_evidence(item)
            key = (item.get("title", ""), item.get("source", ""))
            if key not in seen:
                seen.add(key); combined.append(item)
    for query in BIOTECH_NEWS_QUERIES:
        for item in rss_items(query, 25):
            key = (item.get("title", ""), item.get("source", ""))
            if key not in seen:
                seen.add(key); combined.append(item)
    return combined


def biotech_news_radar_interface(current_stories, archived_stories):
    events = []
    for archived, stories in ((False, current_stories), (True, archived_stories)):
        for story in stories:
            events.append({key: story.get(key) for key in (
                "id", "published_at", "company", "ticker", "exchange", "listing_status", "related_companies",
                "related_tickers", "company_identities", "drug_program", "indication", "event_type",
                "development_stage", "new_information", "previous_state", "new_state", "direction",
                "news_importance_score", "affected_radar_factors", "subsectors", "status", "source_link", "evidence_sources",
            )} | {"archived": archived})
    return {
        "schema_version": "biotech-news-to-radar-evidence-v1",
        "description": "Source-backed biotech news events for future Radar evidence ingestion; contains no Radar-factor or opportunity scores.",
        "events": events,
    }


def build_biotech_news_section(items, previous_section, run_at):
    previous_current = [normalize_news_company_story(item, "biotech") for item in previous_section.get("stories", [])
                        if item.get("quality_schema_version") == 1]
    previous_archive = deduplicate_news_records(
        normalize_news_company_story(item, "biotech") for item in previous_section.get("important_news_archive", [])
        if item.get("quality_schema_version") == 1)
    previous_ids = {item.get("id") for item in previous_current + previous_archive if item.get("id")}
    scored = [score_biotech_news_item(item, run_at, previous_ids) for item in cluster_biotech_news_items(items)]
    scored = [item for item in scored if item]
    if not items:
        return {"stories": previous_current, "important_news_archive": previous_archive,
                "radar_evidence_interface": biotech_news_radar_interface(previous_current, previous_archive),
                "selection_status": "Biotech feeds were unavailable; the prior selection was preserved.",
                "methodology": biotech_news_methodology()}
    current = sorted((item for item in scored if item["news_importance_score"] >= 80),
                     key=lambda item: (-item["news_importance_score"], item["headline"]))
    archive_candidates = [item for item in scored if 65 <= item["news_importance_score"] < 80]
    current_ids = {item["id"] for item in current}
    current_headlines = {re.sub(r"[^a-z0-9]+", " ", item.get("headline", "").lower()).strip() for item in current}
    current_links = {item.get("source_link") for item in current if item.get("source_link")}
    archive_by_id = {
        item["id"]: item for item in previous_archive
        if item.get("id") not in current_ids
        and re.sub(r"[^a-z0-9]+", " ", item.get("headline", "").lower()).strip() not in current_headlines
        and item.get("source_link") not in current_links
    }
    for item in previous_current + archive_candidates:
        normalized_headline = re.sub(r"[^a-z0-9]+", " ", item.get("headline", "").lower()).strip()
        if item.get("id") not in current_ids and normalized_headline not in current_headlines and item.get("source_link") not in current_links:
            archive_by_id[item["id"]] = item
    archive = sorted(deduplicate_news_records(archive_by_id.values()),
                     key=lambda item: item.get("published_at") or item.get("first_seen", ""), reverse=True)
    return {"stories": current, "important_news_archive": archive,
            "radar_evidence_interface": biotech_news_radar_interface(current, archive),
            "selection_status": f"Selected {len(current)} prominent event{'s' if len(current) != 1 else ''}; {len(archive_candidates)} new event{'s' if len(archive_candidates) != 1 else ''} added to Evidence History.",
            "methodology": biotech_news_methodology()}


def biotech_news_methodology():
    return {
        "engine_version": "biotech-news-v1",
        "prominent_threshold": 80, "archive_threshold": 65,
        "importance_weights": {"event_significance": 30, "company_sector_impact": 25, "novelty": 20,
                               "evidence_authority": 15, "immediacy": 10},
        "source_policy": "Official company and regulator feeds are preferred; configured reliable financial, scientific and biotech-industry sources may corroborate or supply events.",
        "archive_policy": "Events scoring 65-79 and previously prominent events remain in Important News Archive / Evidence History.",
        "scoring_boundary": "News scores event importance only. Scientific Evidence, Catalyst Impact, Expectation Gap, Sector Trend and Opportunity Score are not calculated here.",
        "selection_policy": "No quota is filled; only events meeting the configured thresholds are retained.",
    }


AI_RADAR_FACTOR_WEIGHTS = {
    "structural_trend": 20, "demand_adoption": 20, "bottleneck_moat": 20,
    "fundamental_earnings_impact": 15, "expectation_gap_valuation": 15, "market_confirmation": 10,
}

AI_ADOPTION_STAGES = {
    "A0": "Research", "A1": "Prototype / enabling platform", "A2": "Pilot / limited deployment",
    "A3": "Early commercial adoption", "A4": "Scaled adoption", "A5": "Mass adoption / standard infrastructure",
}

AI_RADAR_TRACKS = {
    "AI Models/Applications": {
        "demand_area": None, "current_bottleneck": "Inference economics, reliable deployment, and differentiated application value",
        "next_bottleneck": "Proprietary data, distribution, and power-efficient inference",
        "medium": "Watch whether recurring production usage broadens beyond infrastructure providers and early enterprise adopters.",
        "long": "The 3–10 year outcome depends on durable application economics and widespread workflow integration; current evidence does not establish the end state.",
    },
    "Physical AI / Robotics": {
        "demand_area": "Robotics", "current_bottleneck": "Real-world reliability, unit economics, safety, and repeatable paid deployment",
        "next_bottleneck": "Scaled manufacturing, service operations, and application-specific distribution",
        "medium": "Require evidence of repeated paid deployments and production-scale operation, not demos or isolated pilots.",
        "long": "Mass adoption requires proven economics and operational reliability across many sites; current demos and pilots alone do not establish A4 or A5 adoption.",
    },
    "Compute": {
        "demand_area": "AI Compute", "current_bottleneck": "Accelerator availability, HBM supply, and efficient inference capacity",
        "next_bottleneck": "Networking, data-center commissioning, and power delivery",
        "medium": "Watch whether capacity additions convert into sustained utilization and earnings rather than inventory or overbuild.",
        "long": "Architectural efficiency and workload economics will determine how much compute demand remains structurally durable.",
    },
    "HBM/Memory": {
        "demand_area": "Advanced Semiconductors", "current_bottleneck": "Qualified high-bandwidth-memory supply and yield",
        "next_bottleneck": "Advanced packaging, interconnect bandwidth, and system-level power",
        "medium": "Watch qualification, capacity expansion, pricing, and whether supply growth catches demand.",
        "long": "Memory bandwidth remains strategically important, but supplier economics depend on capacity discipline and architecture changes.",
    },
    "Foundry/Advanced Packaging": {
        "demand_area": "Advanced Semiconductors", "current_bottleneck": "Leading-edge wafer capacity, packaging capacity, and yield",
        "next_bottleneck": "HBM integration, networking, and facility power",
        "medium": "Watch capacity commitments, yield, customer concentration, and packaging lead times.",
        "long": "Durability depends on sustained leading-edge demand and the capital intensity required to maintain process leadership.",
    },
    "Networking/Optical": {
        "demand_area": "AI Networking", "current_bottleneck": "Scale-out bandwidth, latency, and power-efficient interconnect",
        "next_bottleneck": "Optical integration, switching efficiency, and data-center power",
        "medium": "Watch deployment evidence as clusters scale and architectures shift between Ethernet, proprietary fabrics, and optical links.",
        "long": "Network content can rise with distributed compute, but standards shifts and integration may change where value accrues.",
    },
    "Data Centers": {
        "demand_area": "Data Centers", "current_bottleneck": "Commissioned capacity, construction lead times, and usable powered shells",
        "next_bottleneck": "Grid interconnection, electrical equipment, and cooling density",
        "medium": "Watch contracted capacity, utilization, delivery timing, and cancellations rather than announced capacity alone.",
        "long": "Long-run returns depend on utilization, financing costs, location, and whether infrastructure avoids overbuild.",
    },
    "Power/Electrical": {
        "demand_area": "Energy & Power Infrastructure", "current_bottleneck": "Transformers, switchgear, power delivery, and interconnection queues",
        "next_bottleneck": "Generation availability, transmission, and permitting",
        "medium": "Watch order conversion, lead times, and completed energization of AI facilities.",
        "long": "Durable demand depends on grid investment and the realized electricity intensity of AI workloads.",
    },
    "Cooling": {
        "demand_area": "Data Centers", "current_bottleneck": "Thermal density and deployment of liquid-cooling systems",
        "next_bottleneck": "Water, energy efficiency, maintenance, and facility integration",
        "medium": "Watch production deployments and service requirements as rack density rises.",
        "long": "Cooling value depends on sustained high-density compute and whether architectures reduce thermal intensity.",
    },
    "Grid/Energy/Materials": {
        "demand_area": "Energy & Power Infrastructure", "current_bottleneck": "Generation, transmission, permitting, and grid connection",
        "next_bottleneck": "Fuel, critical materials, project finance, and community acceptance",
        "medium": "Watch signed supply agreements, permitted projects, construction, and delivered megawatts.",
        "long": "The 3–10 year opportunity depends on actual load growth, project completion, and competitive generation economics.",
    },
}


def ai_evidence_age(event_date, run_at):
    if not event_date:
        return {"age_days": None, "age_band": "Undated", "freshness_multiplier": 0.5}
    try:
        event_time = datetime.fromisoformat(event_date)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        age_days = max(0, (run_at - event_time).total_seconds() / 86400)
    except (TypeError, ValueError):
        return {"age_days": None, "age_band": "Undated", "freshness_multiplier": 0.5}
    if age_days <= 7:
        return {"age_days": round(age_days, 1), "age_band": "Fresh", "freshness_multiplier": 1.0}
    if age_days <= 30:
        return {"age_days": round(age_days, 1), "age_band": "Current", "freshness_multiplier": 0.85}
    if age_days <= 90:
        return {"age_days": round(age_days, 1), "age_band": "Aging", "freshness_multiplier": 0.6}
    return {"age_days": round(age_days, 1), "age_band": "Stale", "freshness_multiplier": 0.35}


def deduplicate_ai_radar_evidence(events):
    deduplicated = {}
    for event in events:
        key = event.get("event_id") or news_fingerprint(
            f"{event.get('company', '')} {event.get('event_date', '')} {event.get('new_information', '')}", "ai-radar")
        existing = deduplicated.get(key)
        if not existing or event.get("news_importance_score", 0) > existing.get("news_importance_score", 0):
            deduplicated[key] = dict(event, underlying_event_key=key)
    return list(deduplicated.values())


def ai_adoption_stage(trend, evidence):
    if not evidence:
        return None, "Insufficient dated adoption evidence"
    text = " ".join(item.get("new_information", "") for item in evidence).lower()
    quantified = bool(re.search(r"(?:\d|%|million|billion)", text))
    if trend == "Physical AI / Robotics":
        real_paid = any(term in text for term in ("paid deployment", "commercial fleet", "deployed robots", "production units", "robotics revenue"))
        scaled = real_paid and quantified and any(term in text for term in ("multiple sites", "thousand", "million", "scaled"))
        if scaled:
            return "A4", AI_ADOPTION_STAGES["A4"]
        if real_paid:
            return "A3", AI_ADOPTION_STAGES["A3"]
        if any(term in text for term in ("pilot", "trial deployment", "limited deployment")):
            return "A2", AI_ADOPTION_STAGES["A2"]
        if any(term in text for term in ("demo", "prototype", "platform", "physical ai", "robotics")):
            return "A1", AI_ADOPTION_STAGES["A1"]
        return "A0", AI_ADOPTION_STAGES["A0"]
    if quantified and any(term in text for term in ("widely deployed", "industry standard", "mass adoption")):
        return "A5", AI_ADOPTION_STAGES["A5"]
    if quantified and any(term in text for term in ("deploy", "full production", "revenue", "million additional", "customer adoption")):
        return "A4", AI_ADOPTION_STAGES["A4"]
    if any(term in text for term in ("launch", "production", "commercial", "contract", "revenue")):
        return "A3", AI_ADOPTION_STAGES["A3"]
    if any(term in text for term in ("pilot", "limited deployment", "evaluation")):
        return "A2", AI_ADOPTION_STAGES["A2"]
    return "A1", AI_ADOPTION_STAGES["A1"]


def ai_factor(label, key, score, evidence_ids, rationale):
    return {"key": key, "label": label, "weight": AI_RADAR_FACTOR_WEIGHTS[key], "score": score,
            "missing": score is None, "evidence_ids": evidence_ids, "rationale": rationale}


def normalized_available_score(components, keys):
    available = [component for component in components if component["key"] in keys and component["score"] is not None]
    if not available:
        return None
    return round(sum(component["score"] for component in available) / sum(component["weight"] for component in available) * 100)


def ai_beneficiaries(trend, relevant_events, market_data=None, ai_reasoning_discovery=None):
    config = AI_RADAR_TRACKS[trend]
    driver = next((item for item in DEMAND_DRIVERS if item["area"] == config.get("demand_area")), None)
    candidates = {}
    bottleneck_tracks = {"Compute", "HBM/Memory", "Foundry/Advanced Packaging", "Networking/Optical", "Data Centers", "Power/Electrical", "Cooling", "Grid/Energy/Materials"}

    def add(identity, category, evidence_id=None, importance=None):
        if not identity or identity.get("ticker") in (None, "Missing", "N/A"):
            return
        item = candidates.setdefault(identity["company"], {**identity, "category": category, "evidence_ids": [], "importance": []})
        category_priority = {"Direct": 4, "Bottleneck/Picks-and-Shovels": 3, "Second-Order": 2, "Emerging": 1}
        if category_priority[category] > category_priority[item["category"]]:
            item["category"] = category
        if evidence_id and evidence_id not in item["evidence_ids"]:
            item["evidence_ids"].append(evidence_id)
        if importance is not None:
            item["importance"].append(importance)

    if trend == "AI Models/Applications":
        for row in AI_PLATFORMS:
            add(company_identity(row["company"], row.get("ticker")), "Direct")
    if driver:
        public_category = "Bottleneck/Picks-and-Shovels" if trend in bottleneck_tracks else "Direct"
        for identity in normalize_company_list(driver.get("public_companies", "")):
            add(identity, public_category)
        for identity in normalize_company_list(driver.get("emerging_companies", "")):
            add(identity, "Emerging")
    for evidence in relevant_events:
        relation = evidence.get("relation")
        category = "Bottleneck/Picks-and-Shovels" if relation == "direct" and trend in bottleneck_tracks else "Direct" if relation == "direct" else "Second-Order"
        for identity in evidence.get("company_identities", []):
            add(identity, category, evidence.get("event_id"), evidence.get("news_importance_score"))
    relevant_ids = {event.get("event_id") for event in relevant_events}
    importance_by_id = {event.get("event_id"): event.get("news_importance_score") for event in relevant_events}
    for discovered in (ai_reasoning_discovery or {}).get("stock_candidates", []):
        if trend not in discovered.get("parent_tracks", []):
            continue
        evidence_ids = [event_id for event_id in discovered.get("evidence_ids", []) if event_id in relevant_ids]
        if not evidence_ids:
            continue
        roles = discovered.get("beneficiary_roles", [])
        category = "Direct" if "First-Order" in roles else "Second-Order" if "Second-Order" in roles else "Emerging"
        identity = company_identity(discovered.get("company"), discovered.get("ticker"))
        for event_id in evidence_ids:
            add(identity, category, event_id, importance_by_id.get(event_id))
        candidate = candidates.get(identity["company"])
        if candidate is not None:
            candidate["opportunity_stage"] = discovered.get("opportunity_stage")
            candidate["thesis_evidence"] = discovered.get("thesis_evidence", [])
            candidate["confirmation_evidence"] = discovered.get("confirmation_evidence", [])
            candidate["confirmation_missing"] = discovered.get("confirmation_missing", True)
            candidate["classification_reason"] = discovered.get("classification_reason")

    leader_names = {item["company"] for item in AI_INFRASTRUCTURE + AI_PLATFORMS}
    results = []
    for item in candidates.values():
        if not item["evidence_ids"]:
            continue
        category = item["category"]
        components = [
            {"label": "Trend Exposure", "weight": 30, "score": {"Direct": 30, "Bottleneck/Picks-and-Shovels": 26, "Second-Order": 16, "Emerging": 18}[category]},
            {"label": "Bottleneck Position", "weight": 25, "score": 25 if category == "Bottleneck/Picks-and-Shovels" else None},
            {"label": "Revenue Sensitivity", "weight": 20, "score": 20 if item["importance"] and any(
                event.get("event_type") == "Financial Results" and event.get("event_id") in item["evidence_ids"] for event in relevant_events) else None},
            {"label": "Competitive Moat", "weight": 15, "score": 12 if item["company"] in leader_names else None},
            {"label": "Evidence Quality", "weight": 10, "score": round(max(item["importance"]) / 10) if item["importance"] else 5},
        ]
        available = [component for component in components if component["score"] is not None]
        relevance = round(sum(component["score"] for component in available) / sum(component["weight"] for component in available) * 100)
        security_market = market_snapshot(market_data, item["ticker"])
        results.append({key: item[key] for key in ("company", "ticker", "exchange", "listing_status")} | {
            "category": category, "beneficiary_relevance": relevance, "score_components": components,
            "data_completeness": sum(component["weight"] for component in available), "evidence_ids": item["evidence_ids"],
            "opportunity_stage": item.get("opportunity_stage", "Commercial Confirmation" if item["importance"] else "Emerging Trend"),
            "thesis_evidence": item.get("thesis_evidence", []),
            "confirmation_evidence": item.get("confirmation_evidence", []),
            "confirmation_missing": item.get("confirmation_missing", not bool(item.get("confirmation_evidence"))),
            "classification_reason": item.get("classification_reason", "Legacy evidence-linked beneficiary; forward-looking evidence separation is unavailable."),
            "market_data": compact_market_snapshot(security_market),
            "expectation": expectation_assessment(security_market, "ai", 15),
        })
    return sorted(results, key=lambda item: (-item["beneficiary_relevance"], item["company"]))[:8]


def ai_radar_why_changed(previous, current):
    if not previous:
        return "Initial AI Radar V1 evidence baseline."
    changes = []
    for label, key in (("Trend Strength", "trend_strength"), ("Opportunity Score", "opportunity_score"),
                       ("Data Completeness", "data_completeness")):
        old, new = previous.get(key), current.get(key)
        if old != new:
            changes.append(f"{label} changed from {old if old is not None else 'Missing'} to {new if new is not None else 'Missing'}")
    if previous.get("adoption_stage") != current.get("adoption_stage"):
        changes.append(f"Adoption Stage changed from {previous.get('adoption_stage') or 'Missing'} to {current.get('adoption_stage') or 'Missing'}")
    return "; ".join(changes) + "." if changes else "No material score change; evidence was refreshed and deduplicated."


def aggregate_ai_expectation(beneficiaries):
    assessments = []
    for beneficiary in beneficiaries:
        assessment = beneficiary.get("expectation") or {"state": "Data Insufficient", "score": None}
        if assessment["score"] is not None:
            assessments.append((beneficiary["ticker"], assessment))
    if not assessments:
        return {"state": "Data Insufficient", "score": None, "maximum": 15, "tickers": [],
                "coverage": 0, "rationale": "No evidence-supported beneficiary has sufficient current expectation inputs.", "assessments": []}
    score = round(sum(item[1]["score"] for item in assessments) / len(assessments))
    state = "Underpriced" if score >= 11 else "Crowded / Priced In" if score <= 5 else "Fairly Priced"
    return {"state": state, "score": score, "maximum": 15,
            "tickers": [item[0] for item in assessments], "coverage": len(assessments),
            "rationale": f"{state}: aggregated valuation, run-up, analyst-revision, and positioning evidence across {len(assessments)} evidence-supported public beneficiaries.",
            "assessments": [{"ticker": ticker, **assessment} for ticker, assessment in assessments]}


def build_ai_radar(ai_news_section, previous_rows, run_at, market_data=None, ai_reasoning_discovery=None):
    raw_events = ai_news_section.get("radar_evidence_interface", {}).get("events", [])
    events = deduplicate_ai_radar_evidence(raw_events)
    previous_by_trend = {item.get("trend"): item for item in previous_rows or []}
    rows = []
    for trend, config in AI_RADAR_TRACKS.items():
        relevant = []
        for event in events:
            direct = trend in event.get("direct_effects", []) or trend in event.get("affected_trends", [])
            second_order = trend in event.get("second_order_effects", []) and not direct
            if not direct and not second_order:
                continue
            aged = ai_evidence_age(event.get("event_date"), run_at)
            direction = (event.get("direction") or "").lower()
            signal = "mixed" if "mixed" in direction else "confirming" if any(term in direction for term in ("expand", "positive", "advancing")) else "contradicting" if any(
                term in direction for term in ("contract", "restrict", "negative", "delay")) else "neutral"
            relevant.append({**event, **aged, "relation": "direct" if direct else "second-order", "signal": signal})
        confirming = [item for item in relevant if item["signal"] == "confirming"]
        contradicting = [item for item in relevant if item["signal"] == "contradicting"]
        mixed_evidence = [item for item in relevant if item["signal"] == "mixed"]
        event_ids = [item["event_id"] for item in relevant if item.get("event_id")]
        structural_score = min(20, 12 + min(8, len(confirming) * 2))
        demand_score = None
        if relevant:
            weighted_importance = sum(item.get("news_importance_score", 0) * item["freshness_multiplier"] *
                                      (1 if item["relation"] == "direct" else 0.55) for item in relevant) / len(relevant)
            demand_score = min(20, round(6 + weighted_importance * 0.13 + min(3, len(confirming))))
        bottleneck_tracks = {"Compute", "HBM/Memory", "Foundry/Advanced Packaging", "Networking/Optical", "Data Centers", "Power/Electrical", "Cooling", "Grid/Energy/Materials"}
        bottleneck_score = None
        if trend in bottleneck_tracks:
            bottleneck_score = min(20, 10 + min(6, len(relevant) * 2))
        elif relevant and any(term in " ".join(item.get("new_information", "") for item in relevant).lower()
                              for term in ("bottleneck", "capacity", "shortage", "latency", "power", "bandwidth")):
            bottleneck_score = min(20, 8 + min(8, len(relevant) * 2))
        earnings_events = [item for item in relevant if item.get("event_type") == "Financial Results" and item["relation"] == "direct"]
        earnings_score = min(15, 10 + len(earnings_events)) if earnings_events else None
        beneficiaries = ai_beneficiaries(trend, relevant, market_data, ai_reasoning_discovery)
        expectation_context = aggregate_ai_expectation(beneficiaries)
        expectation_score = expectation_context["score"]
        beneficiary_market_scores = []
        for beneficiary in beneficiaries:
            score, available, _ = market_component_score(beneficiary.get("market_data"), "qqq", 10)
            if available:
                beneficiary_market_scores.append(score)
        market_score = round(sum(beneficiary_market_scores) / len(beneficiary_market_scores)) if beneficiary_market_scores else None
        market_evidence_tickers = [beneficiary["ticker"] for beneficiary in beneficiaries if beneficiary.get("market_data")]
        market_rationale = (f"Aggregated price trend and relative strength versus QQQ across {len(beneficiary_market_scores)} evidence-supported beneficiaries."
                            if market_score is not None else "Missing: no beneficiary price/volume record is connected.")
        components = [
            ai_factor("Structural Trend", "structural_trend", structural_score, ["existing-ai-industry-map", *event_ids], "Existing industry-chain structure plus deduplicated supporting events."),
            ai_factor("Demand & Adoption", "demand_adoption", demand_score, event_ids, "Dated adoption and demand evidence; missing when no connected event supports the track."),
            ai_factor("Bottleneck / Moat", "bottleneck_moat", bottleneck_score, event_ids if bottleneck_score is not None else [], "Current chain bottleneck and connected event evidence."),
            ai_factor("Fundamental Earnings Impact", "fundamental_earnings_impact", earnings_score, [item["event_id"] for item in earnings_events], "Company financial-results evidence directly associated with the track."),
            ai_factor("Expectation Gap / Valuation", "expectation_gap_valuation", expectation_score,
                      expectation_context["tickers"], expectation_context["rationale"]),
            ai_factor("Market Confirmation", "market_confirmation", market_score, market_evidence_tickers, market_rationale),
        ]
        trend_strength = normalized_available_score(components, {
            "structural_trend", "demand_adoption", "bottleneck_moat", "fundamental_earnings_impact"})
        opportunity_score = normalized_available_score(components, set(AI_RADAR_FACTOR_WEIGHTS)) if expectation_score is not None and market_score is not None else None
        completeness = sum(component["weight"] for component in components if component["score"] is not None)
        confidence = "High" if completeness >= 70 and len(relevant) >= 3 else "Medium" if completeness >= 45 and relevant else "Low"
        direct_evidence = [item for item in relevant if item["relation"] == "direct"]
        adoption_stage, adoption_label = ai_adoption_stage(trend, direct_evidence)
        evidence_summary = confirming[0]["new_information"] if confirming else relevant[0]["new_information"] if relevant else "No dated News evidence is connected; only the existing structural industry map is available."
        direction = "Expanding" if confirming and not contradicting and not mixed_evidence else "Mixed" if mixed_evidence or (confirming and contradicting) else "Contradicting" if contradicting else "Unconfirmed"
        row = {
            "trend": trend, "heat_score": trend_strength, "trend_strength": trend_strength,
            "opportunity_score": opportunity_score, "direction": direction,
            "stage": f"{adoption_stage} · {adoption_label}" if adoption_stage else "Missing / insufficient evidence",
            "adoption_stage": adoption_stage, "adoption_stage_label": adoption_label,
            "why_now": f"{evidence_summary} Data completeness is {completeness}% with {confidence.lower()} confidence.",
            "what_it_means": f"{len(confirming)} confirming, {len(mixed_evidence)} mixed, and {len(contradicting)} contradicting deduplicated events currently inform this track.",
            "key_intelligence": evidence_summary, "demand_drivers": config["medium"],
            "current_bottleneck": config["current_bottleneck"], "next_likely_bottleneck": config["next_bottleneck"],
            "bottleneck": f"Current: {config['current_bottleneck']}. Next likely: {config['next_bottleneck']}.",
            "beneficiary_records": beneficiaries,
            "discovered_themes": [item for item in (ai_reasoning_discovery or {}).get("theme_signals", [])
                                  if trend in item.get("parent_tracks", []) and
                                  set(item.get("evidence_ids", [])).intersection(event_ids)],
            "potential_beneficiaries": "; ".join(f"{item['company']} ({item['ticker']}) · {item['category']} · {item['beneficiary_relevance']}" for item in beneficiaries[:3]) or "Missing / insufficient evidence",
            "beneficiaries": "; ".join(f"{item['company']} ({item['ticker']}) — {item['category']} — relevance {item['beneficiary_relevance']}/100" for item in beneficiaries) or "Missing / insufficient evidence",
            "market_expectation": expectation_context["rationale"],
            "expectation_state": expectation_context["state"], "expectation": expectation_context,
            "market_confirmation": {"score": market_score, "tickers": market_evidence_tickers, "rationale": market_rationale},
            "risks": "; ".join(item["new_information"] for item in contradicting[:2]) or "Missing: no explicit contradicting or invalidation evidence is connected.",
            "watch_next": f"Watch whether {config['current_bottleneck'].lower()} shifts toward {config['next_bottleneck'].lower()}.",
            "horizons": {"near_term": evidence_summary, "six_to_36_months": config["medium"], "three_to_10_years": config["long"]},
            "score_components": components, "data_completeness": completeness, "confidence": confidence,
            "confirming_evidence": confirming, "contradicting_evidence": contradicting, "mixed_evidence": mixed_evidence,
            "evidence_count": len(relevant), "deduplicated_event_count": len(events), "evidence_as_of": run_at.isoformat(timespec="minutes"),
            "engine_version": "ai-technology-radar-v1",
        }
        previous = previous_by_trend.get(trend)
        row["why_changed"] = ai_radar_why_changed(previous, row)
        prior_history = list(previous.get("score_history", [])) if previous else []
        snapshot = {"as_of": row["evidence_as_of"], "trend_strength": trend_strength, "opportunity_score": opportunity_score,
                    "data_completeness": completeness, "confidence": confidence, "adoption_stage": adoption_stage,
                    "evidence_count": len(relevant), "why_changed": row["why_changed"]}
        snapshot_day = snapshot["as_of"][:10]
        prior_history = [item for item in prior_history if str(item.get("as_of", ""))[:10] != snapshot_day]
        row["score_history"] = (prior_history + [snapshot])[-60:]
        rows.append(row)
    return sorted(rows, key=lambda item: (-(item["trend_strength"] or -1), item["trend"]))


def ai_radar_methodology():
    return {
        "engine_version": "ai-technology-radar-v1", "factor_weights": AI_RADAR_FACTOR_WEIGHTS,
        "trend_strength_policy": "Trend Strength uses available Structural, Demand, Bottleneck and Earnings factors. Missing factors are excluded, not scored as zero.",
        "opportunity_score_policy": "Opportunity Score requires current Expectation Gap/Valuation and trend-specific Market Confirmation evidence. Missing inputs remain missing rather than becoming zero.",
        "expectation_gap_policy": "Expectation Gap / Valuation aggregates evidence-supported public beneficiaries using Nasdaq valuation, analyst-consensus, estimate-revision and short-interest inputs plus the shared market layer's recent price run-up. At least two input groups are required.",
        "market_confirmation_policy": "Market Confirmation aggregates price trend and relative strength versus QQQ across evidence-supported public beneficiaries; missing security data remains missing.",
        "adoption_stages": AI_ADOPTION_STAGES,
        "physical_ai_policy": "Demos and pilots cannot establish scaled or mass adoption. A3+ requires real commercial deployment evidence; A4+ requires quantified scale.",
        "evidence_aging": {"fresh": "0-7 days", "current": "8-30 days", "aging": "31-90 days", "stale": ">90 days"},
        "beneficiary_weights": {"trend_exposure": 30, "bottleneck_position": 25, "revenue_sensitivity": 20,
                                "competitive_moat": 15, "evidence_quality": 10},
    }


def normalize_company_row(row):
    normalized = dict(row)
    normalized.update(company_identity(normalized.get("company"), normalized.get("ticker")))
    normalized.setdefault("related_companies", [])
    normalized.setdefault("related_tickers", [])
    return normalized


def normalize_company_list(value):
    identities = []
    for name in (part.strip() for part in (value or "").split(",")):
        if not name:
            continue
        identity = company_identity(name)
        identities.append(identity)
    return identities


def formatted_company_list(identities):
    return ", ".join(f"{item['company']} ({item['ticker']})" for item in identities)


def normalize_investment_data(data):
    for section_name, domain in (("ai_technology", "ai"), ("biotech_healthcare", "biotech")):
        section = data.get("top_investment_news", {}).get(section_name, {})
        section["stories"] = [normalize_news_company_story(item, domain) for item in section.get("stories", [])]
        section["important_news_archive"] = [normalize_news_company_story(item, domain)
                                               for item in section.get("important_news_archive", [])]
        if section_name == "ai_technology":
            section["radar_evidence_interface"] = build_news_radar_interface(
                section["stories"], section["important_news_archive"])
        else:
            section["radar_evidence_interface"] = biotech_news_radar_interface(
                section["stories"], section["important_news_archive"])

    for key in ("infrastructure_leaders", "platform_leaders", "emerging"):
        data.get("ai", {})[key] = [normalize_company_row(item) for item in data.get("ai", {}).get(key, [])]
    for item in data.get("ai", {}).get("demand_drivers", []):
        public_identities = normalize_company_list(item.get("public_companies", ""))
        emerging_identities = normalize_company_list(item.get("emerging_companies", ""))
        item["public_company_identities"] = public_identities
        item["emerging_company_identities"] = emerging_identities
        item["public_companies"] = formatted_company_list(public_identities)
        item["emerging_companies"] = formatted_company_list(emerging_identities)

    for key in ("leaders", "emerging"):
        data.get("biotech", {})[key] = [normalize_company_row(item) for item in data.get("biotech", {}).get(key, [])]
    data.get("radar", {})["biotech"] = [normalize_company_row(item) for item in data.get("radar", {}).get("biotech", [])]
    validation = data.get("radar_validation", {}).get("mrna", {}).get("result")
    if validation:
        data["radar_validation"]["mrna"]["result"] = normalize_company_row(validation)
    for category in ("ai", "biotech"):
        data.get("monthly_picks", {})[category] = [normalize_company_row(item)
                                                    for item in data.get("monthly_picks", {}).get(category, [])]
        data.get("watchlists", {})[category] = [normalize_company_row(item)
                                                 for item in data.get("watchlists", {}).get(category, [])]
    for item in data.get("fda", []):
        item.setdefault("ticker", "N/A")
        item.setdefault("listing_status", "Non-public")
        item.setdefault("exchange", "")
    data["company_normalization"] = {
        "schema_version": "global-company-identity-v1",
        "ticker_policy": "U.S. canonical ticker; foreign primary ticker with exchange; Private for private companies; N/A for non-public organizations.",
    }
    return data


def build():
    previous = prior_data()
    run_at = datetime.now(timezone.utc)
    score_date = run_at.date()
    ai_news_candidates = collect_ai_investment_news(run_at)
    ai_news = ai_news_candidates[:6]
    biotech_news_candidates = collect_biotech_investment_news(run_at)
    biotech_news = biotech_news_candidates[:6]
    previous_ai_news = previous.get("top_investment_news", {}).get("ai_technology", {})
    ai_news_section = build_ai_news_section(ai_news_candidates, previous_ai_news, run_at)
    previous_biotech_news = previous.get("top_investment_news", {}).get("biotech_healthcare", {})
    biotech_news_section = build_biotech_news_section(biotech_news_candidates, previous_biotech_news, run_at)
    listed_companies, listed_company_status = fetch_listed_company_universe(run_at)
    ai_reasoning_discovery = build_ai_reasoning_discovery(
        ai_news_section, listed_companies, listed_company_status)
    fda_news = rss_items("FDA approval orphan drug fast track rare disease when:7d", 8)
    market_news = rss_items("US stock market Nasdaq S&P 500 today when:1d", 4)
    preliminary_candidates = discover_candidate_pool(
        previous.get("radar", {}).get("ai", []), previous.get("radar", {}).get("biotech", []),
        ai_reasoning_discovery)
    market_data = build_market_data_layer(previous, run_at, candidate_pool=preliminary_candidates)

    old_markets = {item["name"]: item for item in previous.get("markets", [])}
    markets = []
    for yahoo_symbol, (_, name) in MARKETS.items():
        record = market_data.get("indexes", {}).get(yahoo_symbol)
        if record:
            returns = record.get("returns", {})
            markets.append({"name": name, "value": f"{record['current_price']:,.2f}",
                            "daily": returns.get("daily") if returns.get("daily") is not None else 0,
                            "weekly": returns.get("weekly") if returns.get("weekly") is not None else 0,
                            "monthly": returns.get("one_month") if returns.get("one_month") is not None else 0})
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
    ai_radar = build_ai_radar(ai_news_section, previous.get("radar", {}).get("ai", []), run_at,
                              market_data, ai_reasoning_discovery)
    biotech_radar = build_biotech_radar(
        score_date, biotech_news_section, previous.get("radar", {}).get("biotech", []), market_data)
    candidate_discovery = discover_candidate_pool(ai_radar, biotech_radar, ai_reasoning_discovery)
    company_quality = build_company_quality_layer(
        candidate_discovery["candidates"], run_at, fetch_nasdaq_json,
        previous.get("company_quality"))
    watchlists = {"ai": attach_market_context(watch_rows(AI_WATCH), market_data, "ai"),
                  "biotech": attach_market_context(watch_rows(BIOTECH_WATCH), market_data, "biotech")}
    monthly_picks, high_conviction_engine, entry_timing_engine = build_high_conviction_engine(
        ai_radar, biotech_radar, market_data, score_date, candidate_discovery, company_quality, watchlists)
    high_conviction_commentary = annotate_high_conviction(monthly_picks)
    watchlists = annotate_watchlists(watchlists, biotech_radar)
    dashboard_commentary = {
        "news": build_news_commentary(ai_news_section, biotech_news_section),
        "radar": build_radar_commentary(ai_radar, biotech_radar),
        "high_conviction": high_conviction_commentary,
    }

    data = {
        "updated_at": run_at.isoformat(timespec="seconds"),
        "top_investment_news": {"ai_technology": ai_news_section, "biotech_healthcare": biotech_news_section},
        "summaries": {"ai": summarize(ai_news, "AI"), "biotech": summarize(biotech_news, "biotech"),
                      "market": summarize(market_news, "market"), "market_movers": market_movers},
        "takeaways": takeaways[:8],
        "ai": {"infrastructure_leaders": AI_INFRASTRUCTURE, "platform_leaders": AI_PLATFORMS,
               "emerging": AI_EMERGING, "demand_drivers": DEMAND_DRIVERS},
        "biotech": {"leaders": BIOTECH_LEADERS, "emerging": BIOTECH_EMERGING},
        "radar": {"ai": ai_radar, "biotech": biotech_radar,
                  "methodology": radar_methodology(), "ai_methodology": ai_radar_methodology()},
        "radar_validation": {
            "mrna": {
                "cutoff_date": "2026-07-31",
                "future_information_used": False,
                "result": score_biotech_catalyst(MRNA_VALIDATION_CASE, datetime(2026, 7, 31).date()),
                "note": "Retrospective validation input is frozen at July 31, 2026; the August 5 FDA outcome is deliberately excluded.",
            }
        },
        "market_data": market_data, "ai_reasoning_discovery": ai_reasoning_discovery,
        "candidate_discovery": candidate_discovery,
        "company_quality": company_quality, "watchlists": watchlists,
        "commentary": dashboard_commentary,
        "high_conviction_engine": high_conviction_engine,
        "entry_timing_engine": entry_timing_engine,
        "monthly_picks": monthly_picks, "fda": fda, "markets": markets,
    }
    data = normalize_investment_data(data)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")
    print(f"Updated {OUTPUT}")


if __name__ == "__main__":
    build()
