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
        "terms": ("ai factory", "ai factories", "accelerated computing", "gpu cloud", "additional gpus", "gpu", "gpus"),
        "parent_tracks": ("Compute", "Data Centers", "Networking/Optical"),
        "related_industries": ("Semiconductors", "Data centers", "Network infrastructure"),
        "technologies": ("Accelerated computing", "Rack-scale systems", "AI networking"),
    },
    {
        "theme": "Physical AI and production robotics",
        "terms": ("physical ai", "robotics", "robot computer", "deployed robots", "production units",
                  "industrial automation", "machine vision", "autonomous systems", "sensors"),
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
        "terms": ("power demand", "power capacity", "grid", "megawatt", "gigawatt", "electricity",
                  "backup power", "switchgear", "transformer", "electrical equipment"),
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
    {
        "theme": "Quantum computing and sensing",
        "terms": ("quantum computing", "quantum computer", "quantum processor", "quantum sensing",
                  "quantum networking", "qubit"),
        "parent_tracks": ("Compute", "Networking/Optical"),
        "related_industries": ("Quantum computing", "Precision instrumentation", "Photonics"),
        "technologies": ("Quantum processors", "Quantum control", "Quantum networking"),
    },
    {
        "theme": "Space-based AI and connectivity",
        "terms": ("space technology", "space-based", "satellite network", "satellite connectivity",
                  "on-orbit", "space systems"),
        "parent_tracks": ("Networking/Optical", "Physical AI / Robotics", "Edge AI"),
        "related_industries": ("Space systems", "Satellite communications", "Autonomous platforms"),
        "technologies": ("On-orbit computing", "Satellite networking", "Autonomous navigation"),
    },
)


# General product/capability rules used after an evidence-derived theme is active.
# These are category definitions, not company or ticker lists.  A company must
# match its own source-backed profile; size never creates relevance.
PROFILE_DISCOVERY_RULES = {
    "AI Models/Applications": {
        "role": "First-Order",
        "terms": ("artificial intelligence", "machine learning", "enterprise software", "cloud computing",
                  "data analytics", "application software", "ai platform", "inference software"),
    },
    "Compute": {
        "role": "First-Order",
        "terms": ("semiconductor", "semiconductors", "accelerator", "processor", "processors", "gpu", "gpus", "chip",
                  "integrated circuit", "computer hardware", "quantum computing", "quantum processor",
                  "electronic components"),
    },
    "HBM/Memory": {
        "role": "Bottleneck/Picks-and-Shovels",
        "terms": ("memory semiconductor", "dram", "high bandwidth memory", "high-bandwidth memory", "hbm",
                  "memory device", "memory products", "semiconductor equipment"),
    },
    "Foundry/Advanced Packaging": {
        "role": "Bottleneck/Picks-and-Shovels",
        "terms": ("semiconductor manufacturing", "foundry", "wafer fabrication", "wafer processing",
                  "advanced packaging", "semiconductor equipment", "test equipment", "lithography"),
    },
    "Networking/Optical": {
        "role": "Bottleneck/Picks-and-Shovels",
        "terms": ("optical", "photonics", "fiber optic", "networking equipment", "networking solutions",
                  "network infrastructure", "telecommunications equipment", "communications equipment",
                  "network switch", "ethernet", "interconnect", "satellite communications",
                  "quantum networking"),
    },
    "Data Centers": {
        "role": "Second-Order",
        "terms": ("data center", "data centers", "datacenter", "colocation",
                  "server infrastructure", "data storage", "cloud infrastructure", "cloud computing infrastructure"),
    },
    "Power/Electrical": {
        "role": "Bottleneck/Picks-and-Shovels",
        "terms": ("electrical equipment", "electrical products", "switchgear", "transformer", "power distribution",
                  "power management", "power devices", "power solutions", "backup power", "uninterruptible power",
                  "generator", "microgrid"),
    },
    "Cooling": {
        "role": "Bottleneck/Picks-and-Shovels",
        "terms": ("liquid cooling", "thermal management", "heat exchanger", "cooling equipment", "cooling solutions",
                  "hvac", "refrigeration equipment", "data center cooling"),
    },
    "Grid/Energy/Materials": {
        "role": "Second-Order",
        "terms": ("grid infrastructure", "power generation", "electric utility", "electric utilities", "transmission",
                  "grid modernization", "energy storage",
                  "nuclear energy", "battery materials", "critical materials", "renewable energy equipment"),
    },
    "Physical AI / Robotics": {
        "role": "First-Order",
        "terms": ("robotics", "robotic", "industrial automation", "factory automation", "automation systems",
                  "machine vision", "motion control", "industrial sensor", "advanced sensing", "radar solutions",
                  "autonomous system", "embedded vision", "lidar", "space systems",
                  "satellite systems"),
    },
    "Edge AI": {
        "role": "Second-Order",
        "terms": ("edge computing", "embedded systems", "industrial sensor", "machine vision", "on-device",
                  "internet of things", "autonomous system", "space systems"),
    },
}

PROFILE_TEXT_FIELDS = (
    "company", "sector", "industry", "description", "products", "technologies", "capabilities",
    "customer_exposure", "supply_chain_role",
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


def market_cap_bucket(value):
    """Provide size context for diversity; never used as a relevance score."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "Unknown"
    if amount >= 200_000_000_000:
        return "Mega"
    if amount >= 10_000_000_000:
        return "Large"
    if amount >= 2_000_000_000:
        return "Mid"
    if amount > 0:
        return "Small/Emerging"
    return "Unknown"


def profile_matches(company, track):
    """Return source-backed category matches from a general company profile."""
    return profile_match_details(company, track)["terms"]


def profile_match_details(company, track):
    """Validate a category link and retain which profile fields support it."""
    rule = PROFILE_DISCOVERY_RULES.get(track)
    if not rule:
        return {"terms": [], "fields": [], "strength": 0}
    matches_by_field = {}
    for field in PROFILE_TEXT_FIELDS:
        text = str(company.get(field) or "")
        matched = [term for term in rule["terms"] if _contains_term(text, term)]
        if matched:
            matches_by_field[field] = matched
    terms = sorted({term for values in matches_by_field.values() for term in values})
    field_weights = {
        "company": 1, "sector": 1, "industry": 2, "description": 3, "products": 3,
        "technologies": 3, "capabilities": 3, "customer_exposure": 3, "supply_chain_role": 3,
    }
    strength = sum(field_weights[field] for field in matches_by_field) + min(3, len(terms))
    return {"terms": terms, "fields": sorted(matches_by_field), "strength": strength}


def credible_profile_match(company, track):
    """Require category evidence from a business profile, not a name alone."""
    validation = profile_match_details(company, track)
    evidence_fields = set(validation["fields"]) - {"company", "sector"}
    validation["credible"] = bool(validation["terms"] and evidence_fields)
    validation["reason"] = ("category-specific business profile evidence" if validation["credible"] else
                            "no category-specific industry, product, capability, or business-description evidence")
    return validation


def event_company_track_match(event, identity, track):
    """Accept direct event evidence only when both company and category are explicit."""
    if track not in event.get("direct_effects", []) and track not in event.get("affected_trends", []):
        return {"credible": False, "terms": [], "reason": "category is not a direct event effect"}
    text = " ".join(str(event.get(field) or "") for field in ("headline", "new_information"))
    variants = company_name_variants(identity.get("company"))
    company_explicit = any(company_name_mentioned(text, variant) for variant in variants)
    terms = [term for term in PROFILE_DISCOVERY_RULES.get(track, {}).get("terms", ()) if _contains_term(text, term)]
    credible = bool(company_explicit and terms)
    return {"credible": credible, "terms": terms,
            "reason": ("company and category are explicit in direct event evidence" if credible else
                       "event does not explicitly connect this company to the category")}


def _profile_evidence(company, theme, track, matched_terms, matched_fields):
    source_date = company.get("source_date") or company.get("retrieved_at")
    return {
        "event_id": next(iter(theme.get("evidence_ids", [])), None),
        "date": source_date,
        "headline": f"{company.get('company')} company-profile relevance validation",
        "evidence_types": ["Product / Technology", "Industry Position", "Logical Connection"],
        "basis": (
            f"The listed-company profile connects {company.get('company')} to {track} through "
            f"{', '.join(matched_terms)}. The separate theme evidence establishes current industry demand; "
            "commercial confirmation is not assumed."
        ),
        "source": company.get("profile_source") or company.get("resolution"),
        "source_link": company.get("source_link", ""),
        "matched_profile_terms": matched_terms,
        "matched_profile_fields": matched_fields,
    }


def _diverse_profile_selection(rows, limit=5):
    """Keep relevance ordering while preventing an all-mega-cap result set."""
    ordered = sorted(rows, key=lambda row: (-row["profile_validation_strength"],
                                            -len(row["matched_terms"]), row["company"]))
    selected = ordered[:limit]
    has_smaller = any(row["market_cap_bucket"] in ("Mid", "Small/Emerging") for row in selected)
    mega_dominated = sum(row["market_cap_bucket"] == "Mega" for row in selected) >= max(3, len(selected) - 1)
    if selected and mega_dominated and not has_smaller:
        emerging = next((row for row in ordered if row["market_cap_bucket"] in ("Mid", "Small/Emerging")), None)
        if emerging and emerging not in selected:
            selected[-1] = emerging
    return selected


def opportunity_stage(roles, thesis_evidence, confirmation_evidence):
    """Classify discovery maturity without turning the stages into scores."""
    confirmed_events = {item.get("event_id") for item in confirmation_evidence if item.get("event_id")}
    confirmation_types = {kind for item in confirmation_evidence for kind in item.get("evidence_types", [])}
    if len(confirmed_events) >= 2 and len(confirmation_types) >= 2:
        return "Established Beneficiary"
    if confirmation_evidence:
        return "Commercial Confirmation"
    substantive_thesis = {kind for item in thesis_evidence for kind in item.get("evidence_types", [])} - {"Logical Connection"}
    if substantive_thesis and any(role in roles for role in
                                  ("First-Order", "Second-Order", "Bottleneck/Picks-and-Shovels")):
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
        structured_tracks = {
            track for field in ("direct_effects", "affected_trends", "second_order_effects")
            for track in event.get(field, []) if track in PROFILE_DISCOVERY_RULES
        }
        for track in structured_tracks:
            theme_name = f"{track} evidence-linked demand"
            record = records.setdefault(theme_name, {
                "theme": theme_name, "parent_tracks": [track],
                "related_industries": [], "technologies": [],
                "matched_terms": ["structured News→Radar effect"],
                "evidence_ids": [], "event_count": 0, "importance_values": [],
                "confirmation_statuses": [], "directions": [],
            })
            record["event_count"] += 1
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


def discover_ai_stocks(events, themes, listed_companies=None, diagnostics=None):
    """Discover named and profile-validated public beneficiaries of inferred themes.

    ``listed_companies`` is a general listed-company universe with whatever
    source-backed industry/product metadata is available. No ticker is selected
    by a hand-maintained beneficiary list in this function.
    """
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics.setdefault("named_company_rejections", [])
    diagnostics.setdefault("profile_rejections", {})
    diagnostics.setdefault("profile_top_n_removed", {})
    diagnostics.setdefault("accepted_by_track", {})
    event_by_id = {event.get("event_id"): event for event in events or [] if event.get("event_id")}
    company_by_ticker = {str(company.get("ticker") or "").upper(): company for company in listed_companies or []
                         if company.get("ticker")}
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
        for evidence_id in theme.get("evidence_ids", []):
            event = event_by_id.get(evidence_id, {})
            for identity in identities_by_event.get(evidence_id, []):
                if identity.get("listing_status") != "Public" or identity.get("ticker") in (None, "", "Missing", "Private", "N/A"):
                    continue
                key = str(identity["ticker"]).upper()
                company = company_by_ticker.get(key, identity)
                for track in theme.get("parent_tracks", []):
                    profile_validation = credible_profile_match(company, track)
                    event_validation = event_company_track_match(event, identity, track)
                    if not profile_validation["credible"] and not event_validation["credible"]:
                        diagnostics["named_company_rejections"].append({
                            "ticker": key, "company": identity.get("company"), "track": track,
                            "event_id": evidence_id, "reason": event_validation["reason"],
                        })
                        continue
                    relation = (PROFILE_DISCOVERY_RULES.get(track, {}).get("role")
                                if profile_validation["credible"] else "First-Order")
                    row = results.setdefault(key, {
                        "company": company.get("company") or identity.get("company"), "ticker": key,
                        "exchange": company.get("exchange", identity.get("exchange", "")),
                        "listing_status": "Public", "resolution": company.get("resolution", "news_identity"),
                        "beneficiary_roles": [], "themes": [], "parent_tracks": [],
                        "related_industries": [], "technologies": [], "evidence_ids": [],
                        "discovery_sources": [], "thesis_evidence": [], "confirmation_evidence": [],
                    })
                    if relation not in row["beneficiary_roles"]:
                        row["beneficiary_roles"].append(relation)
                    if theme["theme"] not in row["themes"]:
                        row["themes"].append(theme["theme"])
                    if track not in row["parent_tracks"]:
                        row["parent_tracks"].append(track)
                    for field in ("related_industries", "technologies"):
                        for value in theme.get(field, []):
                            if value not in row[field]:
                                row[field].append(value)
                    if evidence_id and evidence_id not in row["evidence_ids"]:
                        row["evidence_ids"].append(evidence_id)
                    source = f"Category-validated news identity: {track}"
                    if source not in row["discovery_sources"]:
                        row["discovery_sources"].append(source)
                    text = " ".join(str(event.get(field) or "") for field in ("headline", "new_information"))
                    thesis_types = matching_signal_types(text, THESIS_SIGNAL_TERMS) or ["Logical Connection"]
                    basis = (f"The company profile and event evidence connect {row['company']} to {track}."
                             if profile_validation["credible"] else
                             f"The event explicitly connects {row['company']} to {track} through {', '.join(event_validation['terms'])}.")
                    thesis = evidence_record(event, thesis_types, basis)
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
                    row["discovery_method"] = "news_identity_category_validation"
                    row["profile_matches"] = sorted(set(row.get("profile_matches", []) + profile_validation["terms"]))
                    row["profile_match_fields"] = sorted(set(row.get("profile_match_fields", []) + profile_validation["fields"]))
                    row["market_cap"] = company.get("market_cap")
                    row["market_cap_bucket"] = market_cap_bucket(company.get("market_cap"))

        # Broad discovery deliberately starts from the active theme and scans the
        # general public-company universe.  It does not require a company mention,
        # order, backlog, revenue, or prior membership in the focused universe.
        for track in theme.get("parent_tracks", []):
            profile_rows = []
            rejected = []
            for company in listed_companies or []:
                if company.get("listing_status") != "Public" or not company.get("ticker"):
                    continue
                validation = credible_profile_match(company, track)
                if not validation["credible"]:
                    rejected.append(str(company.get("ticker")))
                    continue
                variants = company_name_variants(company.get("company"))
                profile_rows.append({
                    **company,
                    "company": min(variants, key=len) if variants else company.get("company"),
                    "matched_terms": validation["terms"],
                    "matched_fields": validation["fields"],
                    "profile_validation_strength": validation["strength"],
                    "market_cap_bucket": market_cap_bucket(company.get("market_cap")),
                })
            selected_profiles = _diverse_profile_selection(profile_rows)
            selected_tickers = {str(company.get("ticker")) for company in selected_profiles}
            diagnostics["profile_rejections"].setdefault(track, []).extend(rejected)
            diagnostics["profile_top_n_removed"].setdefault(track, []).extend(
                str(company.get("ticker")) for company in profile_rows
                if str(company.get("ticker")) not in selected_tickers)
            for company in selected_profiles:
                key = str(company["ticker"]).upper()
                role = PROFILE_DISCOVERY_RULES[track]["role"]
                row = results.setdefault(key, {
                    "company": company["company"], "ticker": key,
                    "exchange": company.get("exchange", ""), "listing_status": "Public",
                    "resolution": company.get("resolution", "listed_company_profile"),
                    "beneficiary_roles": [], "themes": [], "parent_tracks": [],
                    "related_industries": [], "technologies": [], "evidence_ids": [],
                    "discovery_sources": [], "thesis_evidence": [], "confirmation_evidence": [],
                })
                if role not in row["beneficiary_roles"]:
                    row["beneficiary_roles"].append(role)
                if theme["theme"] not in row["themes"]:
                    row["themes"].append(theme["theme"])
                for field in ("related_industries", "technologies", "evidence_ids"):
                    for value in theme.get(field, []):
                        if value not in row[field]:
                            row[field].append(value)
                if track not in row["parent_tracks"]:
                    row["parent_tracks"].append(track)
                source = f"Broad listed-company profile discovery: {track} ({', '.join(company['matched_terms'])})"
                if source not in row["discovery_sources"]:
                    row["discovery_sources"].append(source)
                thesis = _profile_evidence(company, theme, track, company["matched_terms"], company["matched_fields"])
                if thesis not in row["thesis_evidence"]:
                    row["thesis_evidence"].append(thesis)
                row["discovery_method"] = "category_profile_validation"
                row["profile_matches"] = sorted(set(row.get("profile_matches", []) + company["matched_terms"]))
                row["profile_match_fields"] = sorted(set(row.get("profile_match_fields", []) + company["matched_fields"]))
                row["profile_validation_strength"] = max(
                    row.get("profile_validation_strength", 0), company["profile_validation_strength"])
                row["market_cap"] = company.get("market_cap")
                row["market_cap_bucket"] = company["market_cap_bucket"]
                diagnostics["accepted_by_track"].setdefault(track, [])
                if key not in diagnostics["accepted_by_track"][track]:
                    diagnostics["accepted_by_track"][track].append(key)
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
    discovery_trace = {}
    stocks = discover_ai_stocks(events, themes, listed_companies, discovery_trace)
    return {
        "schema_version": "ai-reasoning-discovery-v4",
        "flow": "Evidence / News / Industry Data → Reasoning → Theme Discovery → Beneficiary Discovery → Stock Discovery → Radar",
        "theme_signals": themes,
        "stock_candidates": stocks,
        "coverage": {
            "evidence_events": len(events), "themes": len(themes), "public_stocks": len(stocks),
            "first_order": sum("First-Order" in row["beneficiary_roles"] for row in stocks),
            "second_order": sum("Second-Order" in row["beneficiary_roles"] for row in stocks),
            "profile_discovered": sum(row.get("discovery_method") == "category_profile_validation" for row in stocks),
            "by_market_cap_bucket": {bucket: sum(row.get("market_cap_bucket", "Unknown") == bucket for row in stocks)
                                     for bucket in ("Mega", "Large", "Mid", "Small/Emerging", "Unknown")},
            "by_parent_track": {track: sum(track in row.get("parent_tracks", []) for row in stocks)
                                for track in PROFILE_DISCOVERY_RULES},
            "by_opportunity_stage": {stage: sum(row["opportunity_stage"] == stage for row in stocks)
                                     for stage in ("Emerging Trend", "Early Beneficiary",
                                                   "Commercial Confirmation", "Established Beneficiary")},
        },
        "listed_company_source": source_status or {"status": "not supplied"},
        "production_trace": discovery_trace,
        "diagnostics": {
            "primary_bottleneck_fixed": "Company discovery previously required an explicit company mention in a current news event; active themes now scan and validate a general listed-company profile universe.",
            "focused_universe_entry_gate": False,
            "market_cap_entry_filter": False,
            "category_candidate_limit": 5,
            "remaining_source_constraint": "Discovery breadth depends on the industry/product metadata present in the listed-company source; missing profile detail remains missing.",
        },
        "policy": {
            "no_manual_ticker_insertion": "Stock discovery scans source-backed company profiles in a general listed-company universe using category capability rules, not a theme-specific ticker list.",
            "size_diversity": "Market capitalization is context only. It never raises relevance; diversity selection prevents equally credible results from being dominated by mega caps.",
            "discovery_not_scoring": "Reasoning signals create research candidates only; existing Radar scoring remains unchanged.",
            "early_entry_policy": "Orders, backlog, guidance, customers, and revenue are not required for Radar entry when source-backed thesis evidence establishes a logical beneficiary connection.",
            "evidence_separation": "Thesis Evidence explains why a company may benefit; Confirmation Evidence records commercial proof without replacing the thesis.",
            "missing_data": "Unresolved company identity remains unresolved and is not converted into a ticker.",
        },
    }
