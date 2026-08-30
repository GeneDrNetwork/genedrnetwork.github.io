"""Reasoning-driven AI theme and public-company discovery.

This module turns source-backed News→Radar events into structured discovery
signals.  It does not score Radar trends or investment opportunities.
"""

from __future__ import annotations

import re
from collections import defaultdict


THEME_PATTERNS = (
    {
        "theme": "Agentic AI deployment",
        "terms": ("agentic ai", "ai agents", "agent platform"),
        "parent_tracks": ("AI Models/Applications", "Compute"),
        "related_industries": ("Enterprise software", "Cloud infrastructure", "Inference services"),
        "technologies": ("AI agents", "Inference", "Model orchestration"),
    },
    {
        "theme": "Inference economics and low-latency serving",
        "terms": ("inference", "low-latency", "latency-sensitive", "tokens per second"),
        "parent_tracks": ("AI Models/Applications", "Compute", "Networking/Optical"),
        "related_industries": ("Inference cloud", "Data-center networking", "Enterprise AI"),
        "technologies": ("Inference accelerators", "Rack-scale systems", "High-speed interconnect"),
    },
    {
        "theme": "AI factories and accelerated data centers",
        "terms": ("ai factory", "ai factories", "accelerated computing", "gpu cloud", "additional gpus"),
        "parent_tracks": ("Compute", "Data Centers", "Networking/Optical"),
        "related_industries": ("Semiconductors", "Data centers", "Network infrastructure"),
        "technologies": ("Accelerated computing", "Rack-scale systems", "AI networking"),
    },
    {
        "theme": "Physical AI and production robotics",
        "terms": ("physical ai", "robotics", "robot computer", "deployed robots", "production units"),
        "parent_tracks": ("Physical AI / Robotics", "Edge AI"),
        "related_industries": ("Industrial automation", "Robotics", "Autonomous systems"),
        "technologies": ("Robot foundation models", "Edge AI", "Simulation"),
    },
    {
        "theme": "Memory bandwidth and advanced packaging",
        "terms": ("high-bandwidth memory", "hbm", "memory bandwidth", "advanced packaging", "cowos"),
        "parent_tracks": ("HBM/Memory", "Foundry/Advanced Packaging"),
        "related_industries": ("Memory semiconductors", "Foundry", "Semiconductor equipment"),
        "technologies": ("HBM", "Advanced packaging", "Chiplets"),
    },
    {
        "theme": "Optical and scale-out AI networking",
        "terms": ("optical", "interconnect", "scale-out", "ethernet", "networking"),
        "parent_tracks": ("Networking/Optical", "Data Centers"),
        "related_industries": ("Optical components", "Network switching", "Data centers"),
        "technologies": ("Optical interconnect", "Ethernet fabrics", "Network switching"),
    },
    {
        "theme": "AI power and grid constraints",
        "terms": ("power demand", "power capacity", "grid", "megawatt", "gigawatt", "electricity"),
        "parent_tracks": ("Power/Electrical", "Grid/Energy/Materials", "Data Centers"),
        "related_industries": ("Electrical equipment", "Power generation", "Grid infrastructure"),
        "technologies": ("Power delivery", "Grid interconnection", "On-site generation"),
    },
    {
        "theme": "High-density liquid cooling",
        "terms": ("liquid cooling", "liquid-cooled", "thermal density", "cooling capacity"),
        "parent_tracks": ("Cooling", "Data Centers"),
        "related_industries": ("Thermal management", "Data-center equipment", "Water infrastructure"),
        "technologies": ("Direct-to-chip cooling", "Immersion cooling", "Heat rejection"),
    },
    {
        "theme": "Edge AI deployment",
        "terms": ("edge ai", "on-device inference", "robotics computer", "jetson"),
        "parent_tracks": ("AI Models/Applications", "Physical AI / Robotics"),
        "related_industries": ("Industrial automation", "Automotive", "Edge computing"),
        "technologies": ("Edge accelerators", "On-device inference", "Embedded systems"),
    },
)


THESIS_SIGNAL_TERMS = (
    ("Industry Position", ("leader", "leading", "dominant", "ecosystem", "platform")),
    ("Product / Technology", ("product", "technology", "system", "chip", "accelerator", "interconnect", "model", "computer")),
    ("Capability", ("capability", "capabilities", "enable", "enables", "delivering", "supports", "performance")),
    ("Capacity", ("capacity", "manufacturing", "fab", "production", "availability")),
    ("Customer Exposure", ("hyperscaler", "cloud provider", "enterprise", "data center", "customer")),
    ("Supply-Chain Position", ("supplier", "supply", "foundry", "memory", "networking", "optical", "cooling", "power")),
    ("Competitive Position", ("faster", "lower latency", "low-latency", "world-class", "next-generation", "differentiated")),
)


CONFIRMATION_SIGNAL_TERMS = (
    ("Orders / Backlog", ("order", "orders", "backlog", "bookings")),
    ("Named Customers / Contracts", ("customer", "customers", "contract", "agreement", "selected by", "adopts", "adopted")),
    ("Guidance", ("guidance", "forecast", "expects revenue", "revenue is expected")),
    ("Revenue / Sales", ("revenue", "sales grew", "sales increased")),
    ("Commercial Deployment", ("paid deployment", "commercial deployment", "full production", "shipping", "production units")),
)


LEGAL_SUFFIXES = re.compile(
    r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|holdings|holding|group|"
    r"common stock|ordinary shares?|common shares?|american depositary shares?|ads|class [a-z])\b\.?,?",
    re.IGNORECASE,
)


def _contains_term(text, term):
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text.lower()) is not None


def company_name_variants(name):
    """Return conservative matching variants for a listed company name."""
    original = re.sub(r"\s+", " ", str(name or "")).strip(" ,.-")
    simplified = re.sub(r"\s+", " ", LEGAL_SUFFIXES.sub(" ", original)).strip(" ,.-")
    variants = []
    for value in (original, simplified):
        if len(value) >= 5 and value.lower() not in {item.lower() for item in variants}:
            variants.append(value)
    return variants


def company_name_mentioned(text, variant):
    """Use case-sensitive matching for single-word names to avoid industry-term false positives."""
    if len(variant.split()) == 1:
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(variant)}(?![A-Za-z0-9])", text) is not None
    return _contains_term(text, variant)


def matching_signal_types(text, signal_terms):
    return [label for label, terms in signal_terms if any(_contains_term(text, term) for term in terms)]


def evidence_record(event, evidence_types, basis):
    return {
        "event_id": event.get("event_id"), "date": event.get("event_date"),
        "headline": event.get("headline"), "evidence_types": evidence_types,
        "basis": basis, "source_link": event.get("source_link", ""),
    }


def opportunity_stage(roles, thesis_evidence, confirmation_evidence):
    """Classify discovery maturity without turning the stages into scores."""
    confirmed_events = {item.get("event_id") for item in confirmation_evidence if item.get("event_id")}
    confirmation_types = {kind for item in confirmation_evidence for kind in item.get("evidence_types", [])}
    if len(confirmed_events) >= 2 and len(confirmation_types) >= 2:
        return "Established Beneficiary"
    if confirmation_evidence:
        return "Commercial Confirmation"
    substantive_thesis = {kind for item in thesis_evidence for kind in item.get("evidence_types", [])} - {"Logical Connection"}
    if substantive_thesis and any(role in roles for role in ("First-Order", "Second-Order")):
        return "Early Beneficiary"
    return "Emerging Trend"


def discover_ai_themes(events):
    """Infer unscored subthemes from source-backed event language."""
    records = {}
    for event in events or []:
        if (event.get("news_importance_score") or 0) < 65:
            continue
        text = " ".join(str(event.get(key) or "") for key in ("headline", "new_information", "event_type"))
        for pattern in THEME_PATTERNS:
            matched_terms = [term for term in pattern["terms"] if _contains_term(text, term)]
            if not matched_terms:
                continue
            record = records.setdefault(pattern["theme"], {
                "theme": pattern["theme"], "parent_tracks": list(pattern["parent_tracks"]),
                "related_industries": list(pattern["related_industries"]),
                "technologies": list(pattern["technologies"]), "matched_terms": [],
                "evidence_ids": [], "event_count": 0, "importance_values": [],
                "confirmation_statuses": [], "directions": [],
            })
            record["event_count"] += 1
            for term in matched_terms:
                if term not in record["matched_terms"]:
                    record["matched_terms"].append(term)
            if event.get("event_id") and event["event_id"] not in record["evidence_ids"]:
                record["evidence_ids"].append(event["event_id"])
            record["importance_values"].append(event.get("news_importance_score"))
            if event.get("confirmation_status") not in record["confirmation_statuses"]:
                record["confirmation_statuses"].append(event.get("confirmation_status"))
            if event.get("direction") not in record["directions"]:
                record["directions"].append(event.get("direction"))
    result = []
    for record in records.values():
        values = [value for value in record.pop("importance_values") if isinstance(value, (int, float))]
        record["evidence_importance"] = round(sum(values) / len(values)) if values else None
        record["reasoning"] = (
            f"{record['event_count']} source-backed event(s) connect {', '.join(record['matched_terms'])} "
            f"to {', '.join(record['parent_tracks'])}; related industries include "
            f"{', '.join(record['related_industries'])}."
        )
        commercial_types = set()
        for evidence_id in record["evidence_ids"]:
            event = next((item for item in events if item.get("event_id") == evidence_id), {})
            text = " ".join(str(event.get(key) or "") for key in ("headline", "new_information"))
            commercial_types.update(matching_signal_types(text, CONFIRMATION_SIGNAL_TERMS))
        record["opportunity_stage"] = "Commercial Confirmation" if commercial_types else "Emerging Trend"
        record["commercial_confirmation_types"] = sorted(commercial_types)
        result.append(record)
    return sorted(result, key=lambda item: (-(item["evidence_importance"] or -1), -item["event_count"], item["theme"]))


def _identity_key(identity):
    return str(identity.get("ticker") or "").upper(), str(identity.get("company") or "").lower()


def discover_ai_stocks(events, themes, listed_companies=None):
    """Resolve public companies mentioned by evidence, then link them to inferred themes.

    ``listed_companies`` may be the full SEC-listed company universe.  No ticker is
    selected by a hand-maintained beneficiary list in this function.
    """
    event_by_id = {event.get("event_id"): event for event in events or [] if event.get("event_id")}
    identities_by_event = defaultdict(list)
    for event in events or []:
        seen = set()
        for identity in event.get("company_identities", []):
            key = _identity_key(identity)
            if key not in seen:
                identities_by_event[event.get("event_id")].append(dict(identity, resolution="news_identity"))
                seen.add(key)
        text = " ".join(str(event.get(key) or "") for key in ("headline", "new_information"))
        for company in listed_companies or []:
            if not company.get("ticker") or not company.get("company"):
                continue
            variants = company_name_variants(company["company"])
            if any(company_name_mentioned(text, variant) for variant in variants):
                identity = {"company": min(variants, key=len), "ticker": company["ticker"],
                            "exchange": company.get("exchange", ""), "listing_status": "Public",
                            "resolution": company.get("resolution", "listed_company_universe")}
                key = _identity_key(identity)
                if key not in seen:
                    identities_by_event[event.get("event_id")].append(identity)
                    seen.add(key)

    results = {}
    for theme in themes or []:
        parent_tracks = set(theme.get("parent_tracks", []))
        for evidence_id in theme.get("evidence_ids", []):
            event = event_by_id.get(evidence_id, {})
            direct = parent_tracks.intersection(event.get("direct_effects", []))
            second_order = parent_tracks.intersection(event.get("second_order_effects", []))
            relation = "First-Order" if direct else "Second-Order" if second_order else "Related"
            for identity in identities_by_event.get(evidence_id, []):
                if identity.get("listing_status") != "Public" or identity.get("ticker") in (None, "", "Missing", "Private", "N/A"):
                    continue
                key = identity["ticker"].upper()
                row = results.setdefault(key, {
                    **identity, "beneficiary_roles": [], "themes": [], "parent_tracks": [],
                    "related_industries": [], "technologies": [], "evidence_ids": [],
                    "discovery_sources": [], "thesis_evidence": [], "confirmation_evidence": [],
                })
                if relation not in row["beneficiary_roles"]:
                    row["beneficiary_roles"].append(relation)
                if theme["theme"] not in row["themes"]:
                    row["themes"].append(theme["theme"])
                for field in ("parent_tracks", "related_industries", "technologies", "evidence_ids"):
                    for value in theme.get(field, []):
                        if value not in row[field]:
                            row[field].append(value)
                source = f"Reasoning-derived {relation.lower()} beneficiary of {theme['theme']}"
                if source not in row["discovery_sources"]:
                    row["discovery_sources"].append(source)
                text = " ".join(str(event.get(field) or "") for field in ("headline", "new_information"))
                thesis_types = matching_signal_types(text, THESIS_SIGNAL_TERMS)
                if "Logical Connection" not in thesis_types:
                    thesis_types.append("Logical Connection")
                thesis = evidence_record(
                    event, thesis_types,
                    f"The source explicitly connects {identity['company']} to {theme['theme']} through "
                    f"{', '.join(thesis_types).lower()} evidence; commercial proof is evaluated separately.",
                )
                if thesis not in row["thesis_evidence"]:
                    row["thesis_evidence"].append(thesis)
                confirmation_types = matching_signal_types(text, CONFIRMATION_SIGNAL_TERMS)
                if confirmation_types:
                    confirmation = evidence_record(
                        event, confirmation_types,
                        f"The source reports {', '.join(confirmation_types).lower()} associated with the thesis.",
                    )
                    if confirmation not in row["confirmation_evidence"]:
                        row["confirmation_evidence"].append(confirmation)
    for row in results.values():
        row["opportunity_stage"] = opportunity_stage(
            row["beneficiary_roles"], row["thesis_evidence"], row["confirmation_evidence"])
        row["classification_reason"] = (
            f"{row['opportunity_stage']}: {len(row['thesis_evidence'])} thesis evidence record(s) and "
            f"{len(row['confirmation_evidence'])} commercial confirmation record(s)."
        )
        row["confirmation_missing"] = not bool(row["confirmation_evidence"])
    priority = {"First-Order": 3, "Second-Order": 2, "Related": 1}
    return sorted(results.values(), key=lambda item: (
        -max((priority.get(role, 0) for role in item["beneficiary_roles"]), default=0),
        -len(item["evidence_ids"]), item["company"],
    ))


def build_ai_reasoning_discovery(news_section, listed_companies=None, source_status=None):
    events = news_section.get("radar_evidence_interface", {}).get("events", [])
    themes = discover_ai_themes(events)
    stocks = discover_ai_stocks(events, themes, listed_companies)
    return {
        "schema_version": "ai-reasoning-discovery-v2",
        "flow": "Evidence / News / Industry Data → Reasoning → Theme Discovery → Beneficiary Discovery → Stock Discovery → Radar",
        "theme_signals": themes,
        "stock_candidates": stocks,
        "coverage": {
            "evidence_events": len(events), "themes": len(themes), "public_stocks": len(stocks),
            "first_order": sum("First-Order" in row["beneficiary_roles"] for row in stocks),
            "second_order": sum("Second-Order" in row["beneficiary_roles"] for row in stocks),
            "by_opportunity_stage": {stage: sum(row["opportunity_stage"] == stage for row in stocks)
                                     for stage in ("Emerging Trend", "Early Beneficiary",
                                                   "Commercial Confirmation", "Established Beneficiary")},
        },
        "listed_company_source": source_status or {"status": "not supplied"},
        "policy": {
            "no_manual_ticker_insertion": "Stock discovery uses evidence identities and a general listed-company universe, not a theme-specific ticker list.",
            "discovery_not_scoring": "Reasoning signals create research candidates only; existing Radar scoring remains unchanged.",
            "early_entry_policy": "Orders, backlog, guidance, customers, and revenue are not required for Radar entry when source-backed thesis evidence establishes a logical beneficiary connection.",
            "evidence_separation": "Thesis Evidence explains why a company may benefit; Confirmation Evidence records commercial proof without replacing the thesis.",
            "missing_data": "Unresolved company identity remains unresolved and is not converted into a ticker.",
        },
    }
