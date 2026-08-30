"""Plain-language dashboard commentary derived from existing structured evidence."""

from collections import Counter
from statistics import median


def clean(value, fallback="Missing"):
    value = str(value or "").strip()
    return value if value else fallback


def shorten(value, limit=240):
    value = clean(value)
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def ranked(items, key):
    return sorted(items or [], key=lambda row: row.get(key) if row.get(key) is not None else -1, reverse=True)


def top_counts(values, limit=4):
    return [item for item, _ in Counter(value for value in values if value).most_common(limit)]


def build_category_news_commentary(stories, category):
    stories = ranked(list(stories or []), "news_importance_score")
    event_types = top_counts([row.get("event_type") for row in stories])
    is_ai = category == "AI/technology"
    themes = top_counts([theme for row in stories for theme in
                         (row.get("affected_trends", []) if is_ai else row.get("subsectors", []))])
    factors = top_counts([factor for row in stories for factor in row.get("affected_radar_factors", [])])
    statuses = Counter(row.get("status") for row in stories)
    top = stories[0] if stories else {}
    top_change = shorten(top.get("new_information"), 280)
    implications = [row.get("impact_chain") for row in stories if row.get("impact_chain")]
    category_label = "AI/technology" if is_ai else "biotechnology"
    next_evidence = ("customer deployments, capacity utilization, product adoption, and financial results"
                     if is_ai else "trial readouts, regulatory decisions, catalyst timing, and commercial execution")
    second_order = ("compute, networking, memory, data centers, power, cooling, or emerging applications"
                    if is_ai else "competitor programs, therapeutic platforms, regulatory pathways, or commercial markets")
    material_change = ("observable demand, adoption, capacity, or earnings sensitivity"
                       if is_ai else "clinical evidence, regulatory probability, catalyst timing, or commercial potential")
    implication_path = ("direct technology beneficiaries and then constrained infrastructure or enabling services"
                        if is_ai else "the affected company or program and then competitors, platforms, regulatory pathways, or commercial markets")
    reasoning = [
        {"label": "What is happening?", "text": (f"{len(stories)} prominent {category_label} events are active. "
            f"The main event types are {', '.join(event_types) if event_types else 'not yet established'}. The highest-importance new information is: {top_change}")},
        {"label": "Why does it matter?", "text": (f"The strongest event carries an importance score of {top.get('news_importance_score', 'Missing')}/100 and affects "
            f"{', '.join((top.get('affected_trends') or top.get('affected_radar_factors') or ['unspecified Radar factors']))}. "
            f"This matters because it changes {material_change} rather than merely repeating an existing narrative.")},
        {"label": "What larger trend is forming?", "text": (f"Repeated coverage clusters around {', '.join(themes or factors) if (themes or factors) else 'no single confirmed cluster yet'}. "
            f"{statuses.get('CONFIRMING', 0)} events are confirming and {statuses.get('TREND-CHANGING', 0)} are trend-changing, so the current evidence is best read as "
            f"{'broadening confirmation' if statuses.get('CONFIRMING', 0) >= statuses.get('TREND-CHANGING', 0) else 'a possible change in direction'} rather than a conclusion from one headline.")},
        {"label": "What could happen next?", "text":
            f"Watch for follow-through in {next_evidence}. Subsequent primary-source evidence should determine whether the current change is durable."},
        {"label": "Investment implications", "text": (f"Inference: the news points first to {implication_path}. "
            f"Potential second-order effects can extend into {second_order}. The currently documented impact path is "
            f"{shorten(implications[0], 220) if implications else 'not sufficiently specified'}; this is evidence for Radar review, not a News-generated stock ranking.")},
    ]
    takeaways = [
        f"Treat {', '.join(themes[:2]) if themes else 'the leading evidence clusters'} as the main cross-story signal; isolated headlines carry less weight than repeated confirmation.",
        f"The most important change is evidence-based rather than narrative-only: {top_change}",
        f"Separate direct effects from second-order effects; the current {category_label} evidence can extend into {second_order} over time.",
        f"The next decision point is follow-through in {next_evidence}.",
    ]
    if any(row.get("missing_data") for row in stories):
        takeaways.append("Important fields remain missing in some events; use those stories as evidence to monitor, not as complete investment conclusions.")
    return {"reasoning": reasoning, "take_home_messages": takeaways[:5],
            "evidence_count": len(stories), "category": category_label,
            "engine_version": "dashboard-commentary-v2"}


def build_news_commentary(ai_section, biotech_section):
    return {
        "ai_technology": build_category_news_commentary(
            (ai_section or {}).get("stories", []), "AI/technology"),
        "biotech_healthcare": build_category_news_commentary(
            (biotech_section or {}).get("stories", []), "biotechnology"),
        "engine_version": "dashboard-commentary-v2",
        "separation_policy": "Each category is interpreted only from its own selected news events.",
    }


def build_radar_commentary(ai_rows, biotech_rows):
    top_ai = ranked(ai_rows, "trend_strength")[:3]; top_bio = ranked(biotech_rows, "opportunity_score")[:3]
    stages = top_counts([row.get("adoption_stage_label") or row.get("stage") for row in ai_rows] +
                        [row.get("stage") for row in biotech_rows])
    bottlenecks = top_counts([row.get("current_bottleneck") for row in ai_rows if row.get("current_bottleneck") and not str(row.get("current_bottleneck")).startswith("Missing")], 3)
    beneficiaries = []
    for row in ai_rows or []:
        beneficiaries.extend(item.get("company") for item in row.get("beneficiary_records", [])
                             if item.get("company") and item.get("listing_status") != "Private")
    top_beneficiaries = top_counts(beneficiaries, 4)
    ai_names = ", ".join(f"{row.get('trend')} ({row.get('trend_strength', 'Missing')}/100)" for row in top_ai) or "no scored AI themes"
    bio_names = ", ".join(f"{row.get('ticker')} ({row.get('opportunity_score', 'Missing')}/100)" for row in top_bio) or "no scored biotech catalysts"
    reasoning = [
        {"label": "Why these themes and stocks?", "text": f"Radar is elevating {ai_names}; the leading biotech catalyst records are {bio_names}. They appear because current evidence links demand, adoption, scientific evidence, catalyst impact, or market confirmation to a defined trend or company."},
        {"label": "Current industry stage", "text": f"The observed stages are concentrated in {', '.join(stages) if stages else 'insufficiently classified stages'}. This means opportunity and execution risk coexist: visible adoption or evidence exists, but not every theme has reached mass deployment or every program has cleared its evidence gate."},
        {"label": "What may develop next?", "text": f"The next transition is likely to be governed by {', '.join(shorten(item, 105) for item in bottlenecks) if bottlenecks else 'the next confirmed operating or clinical bottleneck'}. Watch whether capital spending, deployment, regulatory progress, and market confirmation move together."},
        {"label": "Who may benefit next?", "text": f"Current company-linked evidence most often points to {', '.join(top_beneficiaries) if top_beneficiaries else 'no sufficiently repeated public beneficiary yet'}. Beneficiary status remains conditional on revenue sensitivity, moat, company quality, and expectation data."},
        {"label": "Second-order inference", "text": "Inference: when a first-order bottleneck eases, demand can shift to the next constrained layer—such as networking, power, cooling, data-center capacity, manufacturing, or competing clinical platforms. Radar should therefore track the sequence of bottlenecks, not only the current leader."},
    ]
    takeaways = [
        f"The strongest current AI trend signal is {top_ai[0].get('trend')} at {top_ai[0].get('trend_strength')}/100." if top_ai else "No AI trend currently has sufficient evidence for a leading conclusion.",
        f"The leading biotech catalyst record is {top_bio[0].get('company')} / {top_bio[0].get('program')} at {top_bio[0].get('opportunity_score')}/100, subject to its evidence and binary-risk gates." if top_bio else "No biotech catalyst currently has sufficient data for a leading conclusion.",
        "Trend strength is not the same as stock opportunity; valuation, company exposure, evidence quality, and technical confirmation still determine investability.",
        "The best second-order opportunities should emerge where the next bottleneck has evidence-supported demand but is not yet fully reflected in expectations.",
    ]
    return {"reasoning": reasoning, "take_home_messages": takeaways,
            "engine_version": "dashboard-commentary-v1"}


def failed_gate(row):
    return next((gate for gate in row.get("gates", []) if gate.get("passed") is not True), None)


def annotate_high_conviction(rows_by_domain):
    all_rows = [row for domain in ("ai", "biotech") for row in rows_by_domain.get(domain, [])]
    scores = [row.get("final_score") for row in all_rows if row.get("final_score") is not None]
    score_midpoint = median(scores) if scores else None
    for domain in ("ai", "biotech"):
        domain_rows = rows_by_domain.get(domain, [])
        for row in domain_rows:
            factors = {factor.get("key"): factor for factor in row.get("factor_scores", [])}
            radar = factors.get("radar_conviction", {})
            quality = factors.get("beneficiary_company_quality", {})
            missing = failed_gate(row)
            trend = (", ".join(link.get("trend", "") if isinstance(link, dict) else str(link)
                               for link in row.get("radar_links", [])[:2]) if row.get("radar_links") else
                     ", ".join(row.get("therapeutic_trends", [])[:2]) if row.get("therapeutic_trends") else row.get("catalyst"))
            relative = (f"Ranked #{row.get('rank')} with a final score of {row.get('final_score', 'Missing')}/100"
                        + (f", versus a current shortlist median of {score_midpoint:g}/100" if score_midpoint is not None else ""))
            row["why_this_stock"] = {
                "summary": shorten(row.get("why_selected"), 330),
                "trend_or_catalyst": f"The thesis is linked to {clean(trend)}.",
                "supporting_evidence": f"Radar evidence: {shorten(radar.get('rationale'), 220)} Company/beneficiary evidence: {shorten(quality.get('rationale'), 220)}",
                "relative_strength": f"{relative}. Ranking reflects the existing factor weights and gates, not commentary-generated scoring.",
                "main_risk_or_missing": (f"The main unresolved condition is {missing.get('label')}: {missing.get('rationale')}" if missing else
                                         f"All current selection gates pass; the main documented invalidation is {clean(row.get('thesis_invalidation')).rstrip('.')}."),
                "buy_status": f"Current buy status is {row.get('buy_decision', {}).get('status', 'WAIT')}. {row.get('buy_decision', {}).get('missing_condition', 'Entry condition unavailable')}",
            }
    classification_counts = Counter(row.get("classification") for row in all_rows)
    buy_counts = Counter(row.get("buy_decision", {}).get("status") for row in all_rows)
    reasons = [
        "Each stock is linked to an existing Radar trend or biotech catalyst; discovery alone is not enough for selection.",
        "The ranking combines Radar conviction, beneficiary/company quality, expectation gap, technical setup, and a near-term catalyst using the existing weights.",
        "Evidence, beneficiary proof, expectation, technical-entry, and biotech binary/integrity gates can block High Conviction even when a total score is high.",
        f"The current shortlist contains {classification_counts.get('🔥 High Conviction', 0)} fully High-Conviction names; lower classifications remain visible as serious candidates with unresolved conditions.",
        f"Buy readiness remains separate from selection: {', '.join(f'{count} {status}' for status, count in buy_counts.items() if status) or 'no status coverage'}.",
    ]
    return {"reasons": reasons, "engine_version": "dashboard-commentary-v1"}


def price_distance(price, reference):
    return round((price / reference - 1) * 100, 2) if isinstance(price, (int, float)) and isinstance(reference, (int, float)) and reference > 0 else None


def watchlist_technical_record(row, domain, biotech_radar):
    snapshot = row.get("market_data") or {}; mas = snapshot.get("moving_averages") or {}
    inputs = snapshot.get("entry_inputs") or {}; macd = snapshot.get("macd") or {}
    price = snapshot.get("current_price"); ma20 = mas.get("ma20"); ma50 = mas.get("ma50")
    support_candidates = [value for value in (inputs.get("base_low"), ma20, ma50) if isinstance(value, (int, float)) and isinstance(price, (int, float)) and value < price]
    support = max(support_candidates) if support_candidates else None
    resistance = inputs.get("resistance_level") or row.get("entry_timing", {}).get("resistance_level")
    invalidation = row.get("entry_timing", {}).get("invalidation_level") or inputs.get("invalidation_level")
    above20 = price_distance(price, ma20); above50 = price_distance(price, ma50)
    trend = ("Constructive uptrend" if above20 is not None and above50 is not None and above20 >= 0 and above50 >= 0 else
             "Weak/downtrend" if above20 is not None and above50 is not None and above20 < 0 and above50 < 0 else "Mixed / transition")
    base_sessions = inputs.get("base_duration_sessions")
    bottom = (f"{base_sessions}-session consolidation detected; this is a range rule, not proof of a durable bottom."
              if base_sessions else "No qualifying 42/63-session consolidation; bottom formation is not confirmed.")
    reversal = ("Bullish MACD crossover detected." if macd.get("crossover") == "bullish" else
                "Momentum is improving, but reversal confirmation is incomplete." if macd.get("improving") else
                "No confirmed momentum reversal in the available MACD data." if macd.get("histogram") is not None else "Reversal data unavailable.")
    proximity = inputs.get("breakout_proximity_pct"); volume_ratio = inputs.get("breakout_volume_ratio")
    timing_state = row.get("entry_timing", {}).get("state_key")
    if timing_state == "extended":
        buy_status = "EXTENDED / TOO LATE"
    elif timing_state == "deterioration":
        buy_status = "WAIT"
    elif proximity is not None and 0 <= proximity <= 5 and volume_ratio is not None and volume_ratio >= 1.2:
        buy_status = "READY TO BUY"
    elif proximity is not None and -5 <= proximity < 0:
        buy_status = "APPROACHING ENTRY"
    else:
        buy_status = "WAIT"
    entry_reference = resistance if isinstance(resistance, (int, float)) and resistance > 0 else None
    entry_zone = ({"low": round(entry_reference * .99, 2), "high": round(entry_reference * 1.01, 2), "reference": round(entry_reference, 2)}
                  if entry_reference else {"low": None, "high": None, "reference": None})
    condition = ("A close through resistance with at least 1.2x 20-day volume." if buy_status == "APPROACHING ENTRY" else
                 "Maintain the breakout without triggering extension or breakdown conditions." if buy_status == "READY TO BUY" else
                 "Require a tighter base, improving momentum, and price confirmation around resistance." if buy_status == "WAIT" else
                 "Wait for price extension to normalize or a new base to form.")
    stronger = "Stronger if price holds above MA20/MA50, MACD improves, and volume confirms a move through resistance."
    weaker = "Weaker if price loses support/invalidation, relative strength fades, or volume expands on down days."
    radar = biotech_radar.get(row.get("ticker"), {}) if domain == "biotech" else {}
    targets = ({"plus_10": round(entry_reference * 1.10, 2), "plus_15": round(entry_reference * 1.15, 2),
                "plus_20": round(entry_reference * 1.20, 2)} if domain == "biotech" and entry_reference else None)
    commentary = {
        "why_on_watchlist": clean(row.get("why")),
        "chart": f"{trend}. Price is {above20 if above20 is not None else 'an unknown distance'}% versus MA20 and {above50 if above50 is not None else 'an unknown distance'}% versus MA50. {bottom} {reversal}",
        "entry": f"Buy status is {buy_status}. {condition}",
        "stronger": stronger, "weaker": weaker,
    }
    technical = {"current_price": price, "ma20": ma20, "ma50": ma50, "price_vs_ma20_pct": above20,
                 "price_vs_ma50_pct": above50, "support": support, "resistance": resistance,
                 "volume_vs_20d_average": snapshot.get("volume_vs_20d_average"), "trend": trend,
                 "bottom_formation": bottom, "reversal_status": reversal, "entry_zone": entry_zone,
                 "buy_status": buy_status, "invalidation_level": invalidation,
                 "targets": targets, "target_basis": "Planned watchlist entry reference" if targets else None,
                 "catalyst": radar.get("catalyst") or row.get("catalyst") or "Missing",
                 "catalyst_timing": radar.get("expected_timing") or "Missing",
                 "binary_risk": radar.get("binary_risk") or "Missing" if domain == "biotech" else None}
    return commentary, technical


def annotate_watchlists(watchlists, biotech_rows):
    biotech_radar = {row.get("ticker"): row for row in biotech_rows or []}
    for domain in ("ai", "biotech"):
        for row in watchlists.get(domain, []):
            commentary, technical = watchlist_technical_record(row, domain, biotech_radar)
            row["watchlist_commentary"] = commentary
            row["watchlist_technical"] = technical
    return watchlists
