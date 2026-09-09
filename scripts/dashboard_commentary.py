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


def build_radar_commentary(ai_rows, biotech_rows, crypto_rows=None):
    ai_candidates = sorted(
        [(row, item) for row in ai_rows or [] for item in row.get("beneficiary_records", [])],
        key=lambda pair: pair[1].get("radar_rank_score") if pair[1].get("radar_rank_score") is not None else -1,
        reverse=True)
    top_ai = ai_candidates[:3]
    top_bio = ranked(biotech_rows, "radar_rank_score")[:3]
    ai_names = ", ".join(
        f"{item.get('ticker')} ({item.get('bottleneck_opportunity_score', 'Missing')}/100)"
        for _, item in top_ai) or "no evidence-qualified AI/technology beneficiaries"
    bio_names = ", ".join(
        f"{row.get('ticker')} ({row.get('biotech_opportunity_score', row.get('opportunity_score', 'Missing'))}/100)"
        for row in top_bio) or "no evidence-qualified biotech catalysts"
    ai_penalized = sum((item.get("priced_in_penalty") or 0) > 0 for _, item in ai_candidates)
    bio_penalized = sum((row.get("priced_in_penalty") or 0) > 0 for row in biotech_rows or [])
    top_crypto = ranked(crypto_rows, "radar_rank_score")[:3]
    crypto_names = ", ".join(
        f"{row.get('ticker')} ({row.get('crypto_opportunity_score', 'Missing')}/100)"
        for row in top_crypto) or "no evidence-qualified crypto/stablecoin opportunities"
    crypto_penalized = sum((row.get("priced_in_penalty") or 0) > 0 for row in crypto_rows or [])
    ai_summary = (
        f"The AI/Technology Radar currently evaluates {len(ai_candidates)} public beneficiaries across "
        f"{len(ai_rows or [])} active technology tracks. Its leading early-opportunity records are {ai_names}. "
        f"{ai_penalized} candidates receive an Already-Ran or Priced-In ranking penalty.")
    bio_summary = (
        f"The Biotech Radar currently evaluates {len(biotech_rows or [])} company–program–indication catalysts. "
        f"The leading evidence-adjusted records are {bio_names}. {bio_penalized} candidates receive an "
        "Already-Ran or Priced-In ranking penalty, while scientific-evidence and binary-risk gates remain active.")
    ai_takeaways = [
        (f"The highest-ranked current AI/technology candidate is {top_ai[0][1].get('ticker')} in "
         f"{top_ai[0][0].get('trend')}, with Bottleneck Opportunity {top_ai[0][1].get('bottleneck_opportunity_score', 'Missing')}/100 and "
         f"Multibagger Potential {top_ai[0][1].get('multibagger_potential_score', 'Missing')}/100."
         if top_ai else "No AI/technology candidate currently has sufficient evidence for a leading conclusion."),
        "Bottleneck Opportunity requires category-specific constraint or limited-supplier evidence; general AI exposure alone is capped below 50.",
        f"Price discovery matters to rank: {ai_penalized} current candidates are penalized because a re-rating or priced-in condition is already visible.",
        "Entry Stage is a quick reference from the shared technical engine; detailed timing analysis remains in Swing Trade Opportunity.",
    ]
    bio_takeaways = [
        (f"The leading biotech record is {top_bio[0].get('ticker')} / {top_bio[0].get('program')}, with Biotech Opportunity "
         f"{top_bio[0].get('biotech_opportunity_score', top_bio[0].get('opportunity_score', 'Missing'))}/100 and Multibagger Potential "
         f"{top_bio[0].get('multibagger_potential_score', 'Missing')}/100."
         if top_bio else "No biotech catalyst currently has sufficient evidence for a leading conclusion."),
        "Scientific evidence, catalyst sensitivity, unmet need, valuation headroom, and binary risk remain distinct; a price move cannot substitute for clinical evidence.",
        f"Price discovery matters to rank: {bio_penalized} current candidates are penalized because a re-rating or priced-in condition is already visible.",
        "Missing company sensitivity, cash-runway, or probability inputs remain missing rather than being scored as zero.",
    ]
    crypto_summary = (
        f"The Crypto & Stablecoin Radar evaluates {len(crypto_rows or [])} source-backed crypto assets and public-company beneficiaries. "
        f"The leading early-opportunity records are {crypto_names}. {crypto_penalized} candidates receive an "
        "Already-Ran or Priced-In ranking penalty.")
    crypto_takeaways = [
        (f"The leading current crypto/stablecoin record is {top_crypto[0].get('ticker')}, with Crypto Opportunity "
         f"{top_crypto[0].get('crypto_opportunity_score', 'Missing')}/100 and Multibagger Potential "
         f"{top_crypto[0].get('multibagger_potential_score', 'Missing')}/100."
         if top_crypto else "No crypto/stablecoin record currently has enough evidence for a leading conclusion."),
        "Stablecoin/payment adoption, institutional access, network or company monetization, token economics, liquidity, and regulation are assessed separately.",
        f"Price discovery matters to rank: {crypto_penalized} current candidates are penalized because a re-rating or priced-in condition is already visible.",
        "Missing on-chain activity, fees, valuation, or token-economic evidence is excluded rather than scored as zero.",
    ]
    return {
        "ai_technology": {"summary": ai_summary, "take_home_messages": ai_takeaways},
        "biotech_healthcare": {"summary": bio_summary, "take_home_messages": bio_takeaways},
        "crypto_stablecoin": {"summary": crypto_summary, "take_home_messages": crypto_takeaways},
        "engine_version": "dashboard-radar-commentary-v2",
        "separation_policy": "AI/Technology, Biotechnology, and Crypto/Stablecoin commentary use only their own Radar records.",
    }


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
            business = factors.get("business_quality", {})
            growth = factors.get("sustained_growth", {})
            profit = factors.get("profitability_cash_flow", {})
            moat = factors.get("competitive_advantage", {})
            valuation = factors.get("valuation", {})
            missing = failed_gate(row)
            trend = (", ".join(link.get("trend", "") if isinstance(link, dict) else str(link)
                               for link in row.get("radar_links", [])[:2]) if row.get("radar_links") else
                     ", ".join(row.get("therapeutic_trends", [])[:2]) if row.get("therapeutic_trends") else row.get("catalyst"))
            relative = (f"Ranked #{row.get('rank')} with a final score of {row.get('final_score', 'Missing')}/100"
                        + (f", versus a current shortlist median of {score_midpoint:g}/100" if score_midpoint is not None else ""))
            row["why_this_stock"] = {
                "summary": shorten(row.get("why_selected"), 330),
                "trend_or_catalyst": f"The thesis is linked to {clean(trend)}.",
                "supporting_evidence": (f"Business quality: {shorten(business.get('rationale'), 150)} Growth: {shorten(growth.get('rationale'), 150)} "
                                        f"Profitability/cash flow: {shorten(profit.get('rationale'), 150)} Competitive position: {shorten(moat.get('rationale'), 150)} "
                                        f"Valuation: {shorten(valuation.get('rationale'), 150)}"),
                "relative_strength": (f"{relative}. Market confirmation is {row.get('market_confirmation', {}).get('status', 'Unavailable')}; "
                                      f"Mountain Position is {row.get('mountain_position', 'Unconfirmed')}. Radar is context only and commentary does not score stocks."),
                "main_risk_or_missing": (f"The main unresolved condition is {missing.get('label')}: {missing.get('rationale')}" if missing else
                                         f"All current selection gates pass; the main documented invalidation is {clean(row.get('thesis_invalidation')).rstrip('.')}."),
                "buy_status": f"Current buy status is {row.get('buy_decision', {}).get('status', 'WAIT')}. {row.get('buy_decision', {}).get('missing_condition', 'Entry condition unavailable')}",
            }
    classification_counts = Counter(row.get("classification") for row in all_rows)
    buy_counts = Counter(row.get("buy_decision", {}).get("status") for row in all_rows)
    reasons = [
        "High Conviction requires a proven-quality bullish thesis that is confirmed by a multi-signal market uptrend; Radar discovery and Radar rank do not grant eligibility.",
        "The ranking favors newly confirmed moves in Confirmed Early or Lower Mountain positions with constructive entries and meaningful remaining upside, before raw Conviction Score.",
        "Proven-business, profitability, growth-durability, financial-strength, competitive-position, valuation, market-confirmation, and biotech binary/integrity gates can block High Conviction even when a total score is high.",
        f"The current main list contains {classification_counts.get('🔥 High Conviction', 0)} fully qualified High-Conviction names; candidates with an unresolved gate are excluded from the main list.",
        f"Entry timing remains separate from company selection: {', '.join(f'{count} {status}' for status, count in buy_counts.items() if status) or 'no status coverage'}.",
    ]
    return {"reasons": reasons, "engine_version": "dashboard-commentary-v2"}


def price_distance(price, reference):
    return round((price / reference - 1) * 100, 2) if isinstance(price, (int, float)) and isinstance(reference, (int, float)) and reference > 0 else None


def watchlist_technical_record(row, domain, biotech_radar):
    snapshot = row.get("market_data") or {}; mas = snapshot.get("moving_averages") or {}
    inputs = snapshot.get("entry_inputs") or {}; macd = snapshot.get("macd") or {}
    readiness = (snapshot.get("watchlist_entry_readiness") or {}).get(domain, {})
    decision = readiness.get("buy_decision") or row.get("buy_decision") or {}
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
    timing_state = readiness.get("state_key") or row.get("entry_timing", {}).get("state_key")
    buy_status = decision.get("status") or row.get("buy_decision", {}).get("status") or "WAIT"
    entry_reference = resistance if isinstance(resistance, (int, float)) and resistance > 0 else None
    entry_zone = ({"low": round(entry_reference * .99, 2), "high": round(entry_reference * 1.01, 2), "reference": round(entry_reference, 2)}
                  if entry_reference else {"low": None, "high": None, "reference": None})
    condition = decision.get("missing_condition") or readiness.get("entry_guidance") or (
        "Require a tighter base, improving momentum, and price confirmation around resistance.")
    stronger = "Stronger if price holds above MA20/MA50, MACD improves, and volume confirms a move through resistance."
    weaker = "Weaker if price loses support/invalidation, relative strength fades, or volume expands on down days."
    tight_range = inputs.get("tight_range_20d_pct")
    chart_pattern = (f"{base_sessions}-session base/range under the existing close-range rule."
                     if base_sessions else
                     f"Tight 20-session range ({tight_range}%)." if tight_range is not None and tight_range <= 8 else
                     "No rules-based base or constructive chart pattern is confirmed.")
    early_reversal = ("Early reversal confirmed by a bullish MACD crossover and price recovery above MA20."
                      if macd.get("crossover") == "bullish" and above20 is not None and above20 >= 0 else
                      "Early reversal is developing but not fully confirmed." if macd.get("improving") else
                      "No early reversal is confirmed by the available momentum data.")
    breakout_volume = inputs.get("breakout_volume_ratio")
    volume_confirmation = (f"Confirmed at {breakout_volume}x 20-day volume." if breakout_volume is not None and breakout_volume >= 1.2 else
                           f"Not confirmed; current ratio is {breakout_volume}x." if breakout_volume is not None else
                           "Volume confirmation is unavailable.")
    accumulation = inputs.get("up_down_volume_ratio_20d")
    accumulation_signal = (f"Constructive accumulation-like signal ({accumulation}x up/down volume)."
                           if accumulation is not None and accumulation >= 1.1 else
                           f"No constructive accumulation signal ({accumulation}x up/down volume)." if accumulation is not None else
                           "Accumulation signal is unavailable.")
    extended = timing_state == "extended"
    radar = biotech_radar.get(row.get("ticker"), {}) if domain == "biotech" else {}
    targets = ({"plus_10": round(entry_reference * 1.10, 2), "plus_15": round(entry_reference * 1.15, 2),
                "plus_20": round(entry_reference * 1.20, 2)} if domain == "biotech" and entry_reference else None)
    commentary = {
        "why_on_watchlist": clean(row.get("why")),
        "chart": f"{trend}. Price is {above20 if above20 is not None else 'an unknown distance'}% versus MA20 and {above50 if above50 is not None else 'an unknown distance'}% versus MA50. {bottom} {reversal}",
        "bottom_base": bottom, "early_reversal": early_reversal, "chart_pattern": chart_pattern,
        "volume_confirmation": volume_confirmation, "accumulation_signal": accumulation_signal,
        "entry": f"Buy status is {buy_status}. {condition}", "waiting_for": condition,
        "stronger": stronger, "weaker": weaker,
        "extension": ("Extended / too late under the existing do-not-chase gate."
                      if extended else "Not currently blocked by the extension gate."),
    }
    technical = {"current_price": price, "ma20": ma20, "ma50": ma50, "price_vs_ma20_pct": above20,
                 "price_vs_ma50_pct": above50, "support": support, "resistance": resistance,
                 "volume_vs_20d_average": snapshot.get("volume_vs_20d_average"), "trend": trend,
                 "bottom_formation": bottom, "reversal_status": reversal, "entry_zone": entry_zone,
                 "buy_status": buy_status, "invalidation_level": invalidation,
                 "chart_pattern": chart_pattern, "early_reversal": early_reversal,
                 "volume_confirmation": volume_confirmation, "accumulation_signal": accumulation_signal,
                 "technical_entry_readiness_score": readiness.get("entry_timing_score") or row.get("technical_entry_readiness_score"),
                 "entry_timing_state": readiness.get("state"), "extended": extended,
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
            sources = row.get("watchlist_sources") or []
            commentary["selection_source"] = f"Sources: {' + '.join(sources)}. {' '.join(row.get('strategy_contexts') or [])}"
            row["watchlist_commentary"] = commentary
            row["watchlist_technical"] = technical
    return watchlists
