"""Independent two-step Swing Trade Opportunity selection.

Step 1 screens for a major decline followed by bottoming or an early reversal.
Step 2 requires a source-backed catalyst. This engine does not read or alter
High-Conviction classifications, and it does not promote Radar scores.
"""

from collections import Counter


SWING_STATES = ("Bottoming", "Early Reversal", "Entry Zone", "Breakout", "Extended")
STATE_PRIORITY = {"Entry Zone": 0, "Early Reversal": 1, "Bottoming": 2,
                  "Breakout": 3, "Extended": 4}


def pct_distance(value, reference):
    return round((value / reference - 1) * 100, 2) if value is not None and reference else None


def average(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values)) if values else None


def technical_setup(snapshot):
    snapshot = snapshot or {}
    price = snapshot.get("current_price")
    mas = snapshot.get("moving_averages") or {}
    returns = snapshot.get("returns") or {}
    inputs = snapshot.get("entry_inputs") or {}
    macd = snapshot.get("macd") or {}
    ma20, ma50 = mas.get("ma20"), mas.get("ma50")
    price_vs_ma20 = pct_distance(price, ma20)
    price_vs_ma50 = pct_distance(price, ma50)
    drawdown = inputs.get("drawdown_from_fifty_two_week_high_pct")
    distance_bottom = inputs.get("distance_from_recent_low_pct")
    week_position = snapshot.get("fifty_two_week_position")
    major_decline_signals = [
        drawdown is not None and drawdown <= -20,
        week_position is not None and week_position <= 35,
        returns.get("six_month") is not None and returns["six_month"] <= -20,
        returns.get("three_month") is not None and returns["three_month"] <= -20,
    ]
    major_decline = any(major_decline_signals)
    tight_range = inputs.get("tight_range_20d_pct")
    base_sessions = inputs.get("base_duration_sessions")
    stabilized = bool(
        distance_bottom is not None and distance_bottom <= 30 and
        (base_sessions in (42, 63) or (tight_range is not None and tight_range <= 28)))
    histogram = macd.get("histogram")
    reversal_signal = bool(
        macd.get("crossover") == "bullish" or macd.get("improving") is True or
        (histogram is not None and histogram > 0))
    rsi = snapshot.get("rsi_14")
    momentum_usable = rsi is not None and 32 <= rsi <= 68
    proximity = inputs.get("breakout_proximity_pct")
    breakout_volume = inputs.get("breakout_volume_ratio")
    breakout = bool(proximity is not None and 0 <= proximity <= 5 and
                    breakout_volume is not None and breakout_volume >= 1.2)
    extension_signals = [
        price_vs_ma20 is not None and price_vs_ma20 > 12,
        price_vs_ma50 is not None and price_vs_ma50 > 18,
        distance_bottom is not None and distance_bottom > 35,
        returns.get("one_month") is not None and returns["one_month"] > 25,
        returns.get("three_month") is not None and returns["three_month"] > 40,
        proximity is not None and proximity > 8,
    ]
    extended = any(extension_signals)
    near_ma50 = price_vs_ma50 is not None and -8 <= price_vs_ma50 <= 8
    above_ma20 = price_vs_ma20 is not None and price_vs_ma20 >= 0
    near_ma20 = price_vs_ma20 is not None and price_vs_ma20 >= -3
    if extended:
        state = "Extended"
    elif breakout:
        state = "Breakout"
    elif major_decline and stabilized and reversal_signal and momentum_usable and above_ma20 and near_ma50:
        state = "Entry Zone"
    elif major_decline and stabilized and reversal_signal and momentum_usable and near_ma20:
        state = "Early Reversal"
    else:
        state = "Bottoming"

    decline_score = (100 if drawdown is not None and -60 <= drawdown <= -20 else
                     80 if major_decline else 25 if drawdown is not None else None)
    bottom_score = (100 if stabilized and distance_bottom is not None and distance_bottom <= 15 else
                    80 if stabilized else 45 if distance_bottom is not None and distance_bottom <= 30 else
                    20 if distance_bottom is not None else None)
    reversal_score = (100 if macd.get("crossover") == "bullish" else
                      85 if reversal_signal and momentum_usable else 60 if reversal_signal else
                      35 if histogram is not None else None)
    entry_score = (100 if state == "Entry Zone" else 90 if state == "Early Reversal" else
                   75 if state == "Breakout" else 60 if state == "Bottoming" else 10)
    volume_ratio = snapshot.get("volume_vs_20d_average")
    accumulation = inputs.get("up_down_volume_ratio_20d")
    volume_score = average([
        90 if volume_ratio is not None and .8 <= volume_ratio <= 1.5 else 65 if volume_ratio is not None else None,
        100 if accumulation is not None and accumulation >= 1.3 else 75 if accumulation is not None and accumulation >= 1 else 40 if accumulation is not None else None,
    ])
    components = [
        ("Major Decline", decline_score, 20), ("Bottom / Stabilization", bottom_score, 25),
        ("Early Reversal", reversal_score, 25), ("Entry / Extension", entry_score, 20),
        ("Volume", volume_score, 10),
    ]
    available = sum(weight for _, score, weight in components if score is not None)
    score = (round(sum(score * weight for _, score, weight in components if score is not None) / available)
             if available else None)
    support_values = [value for value in (inputs.get("recent_low_63d"), inputs.get("base_low"), ma50)
                      if value is not None and price is not None and value < price]
    support = max(support_values) if support_values else None
    invalidation = inputs.get("invalidation_level") or support
    qualified = bool(major_decline and stabilized and state != "Extended" and available >= 60)
    return {
        "state": state, "technical_setup_score": score, "data_completeness": available,
        "qualified_step_1": qualified, "major_decline_confirmed": major_decline,
        "bottom_stabilized": stabilized, "early_reversal_confirmed": reversal_signal and momentum_usable,
        "current_price": price, "ma20": ma20, "ma50": ma50,
        "price_vs_ma20_pct": price_vs_ma20, "price_vs_ma50_pct": price_vs_ma50,
        "fifty_two_week_high": inputs.get("fifty_two_week_high"),
        "drawdown_from_high_pct": drawdown, "recent_low": inputs.get("recent_low_63d"),
        "distance_from_bottom_pct": distance_bottom, "bottom_range_20d_pct": tight_range,
        "base_duration_sessions": base_sessions, "rsi_14": rsi, "macd": macd,
        "volume_vs_20d_average": volume_ratio, "up_down_volume_ratio_20d": accumulation,
        "support": round(support, 4) if support is not None else None,
        "resistance": inputs.get("resistance_level"),
        "breakout_proximity_pct": proximity, "extended": extended,
        "invalidation_level": round(invalidation, 4) if invalidation is not None else None,
        "components": [{"label": label, "score": value, "weight": weight,
                        "missing": value is None} for label, value, weight in components],
        "price_date": snapshot.get("price_date"), "source": snapshot.get("source"),
    }


def section_events(section):
    section = section or {}
    return list(section.get("stories", [])) + list(section.get("important_news_archive", []))


def matching_news_catalyst(ticker, section):
    matches = []
    for event in section_events(section):
        tickers = {event.get("ticker"), *(event.get("related_tickers") or [])}
        source_link = event.get("source_link") or event.get("url")
        if ticker in tickers and source_link and (event.get("news_importance_score") or 0) >= 65:
            matches.append(event)
    if not matches:
        return None
    event = max(matches, key=lambda row: (row.get("news_importance_score") or 0,
                                          row.get("published_at") or row.get("date") or ""))
    return {
        "credible": True, "description": event.get("new_information") or event.get("headline"),
        "event_type": event.get("event_type"), "timing": event.get("published_at") or event.get("date"),
        "source": event.get("source"), "date": event.get("published_at") or event.get("date"),
        "source_link": event.get("source_link") or event.get("url"),
        "importance_score": event.get("news_importance_score"),
        "basis": "Source-backed News event with Importance Score at least 65; News does not set the technical classification.",
    }


def biotech_radar_catalyst(ticker, rows):
    matches = [row for row in rows or [] if row.get("ticker") == ticker and row.get("catalyst") and
               not str(row.get("catalyst")).startswith("Missing") and row.get("sources")]
    if not matches:
        return None
    row = max(matches, key=lambda item: item.get("opportunity_score") or -1)
    source = row["sources"][0]
    return {
        "credible": True, "description": row.get("catalyst"), "event_type": "Biotech Radar catalyst",
        "timing": row.get("expected_timing"), "source": source.get("title") or source.get("name"),
        "date": source.get("date") or source.get("publication_date"),
        "source_link": source.get("url"), "importance_score": None,
        "basis": "Dated, source-backed Company → Program → Indication → Catalyst record; its Radar score does not set the swing classification.",
    }


def ai_radar_catalyst(ticker, rows):
    matches = []
    for row in rows or []:
        beneficiary = next((item for item in row.get("beneficiary_records", []) if item.get("ticker") == ticker), None)
        if not beneficiary:
            continue
        evidence_ids = set(beneficiary.get("evidence_ids", []))
        for event in row.get("confirming_evidence", []) + row.get("mixed_evidence", []):
            if event.get("event_id") in evidence_ids and event.get("source_link"):
                matches.append((event, row.get("trend")))
    if not matches:
        return None
    event, trend = max(matches, key=lambda item: (item[0].get("event_date") or "",
                                                  item[0].get("news_importance_score") or 0))
    return {
        "credible": True, "description": event.get("new_information"),
        "event_type": event.get("event_type") or f"{trend} industry event", "timing": event.get("event_date"),
        "source": event.get("source"), "date": event.get("event_date"),
        "source_link": event.get("source_link"), "importance_score": event.get("news_importance_score"),
        "basis": "Company-linked, source-backed AI Radar evidence; Radar strength does not set the swing classification.",
    }


def catalyst_check(ticker, domain, ai_radar, biotech_radar, ai_news, biotech_news):
    news = matching_news_catalyst(ticker, biotech_news if domain == "biotech" else ai_news)
    if news:
        return news
    return (biotech_radar_catalyst(ticker, biotech_radar) if domain == "biotech"
            else ai_radar_catalyst(ticker, ai_radar)) or {
                "credible": False, "description": "Missing: no source-backed catalyst is connected.",
                "event_type": None, "timing": None, "source": None, "date": None,
                "source_link": None, "importance_score": None,
                "basis": "A technical setup alone cannot enter Swing Trade Opportunity.",
            }


def build_explanation(company, technical, catalyst):
    state = technical["state"]
    early = (f"Price is {technical.get('distance_from_bottom_pct')}% above the trailing 63-session low"
             if technical.get("distance_from_bottom_pct") is not None else
             "Distance from the trailing low is unavailable")
    invalidation = (f"A close below {technical.get('invalidation_level')} would invalidate the calculated setup."
                    if technical.get("invalidation_level") is not None else
                    "Missing: no reliable support-based invalidation level can be calculated.")
    decline_text = (f"{technical.get('drawdown_from_high_pct')}% from the trailing high"
                    if technical.get("drawdown_from_high_pct") is not None else
                    "confirmed by available 52-week-position or multi-month return evidence")
    return {
        "summary": f"{company} passed the technical-first screen as {state} and has a separate source-backed catalyst check.",
        "why_chart_selected": (f"A major decline is {decline_text}; "
                               f"the 20-session range is {technical.get('bottom_range_20d_pct')}%."),
        "bottom_reversal_stage": (f"The setup is classified {state}; price versus MA20/MA50 is "
                                  f"{technical.get('price_vs_ma20_pct')}% / {technical.get('price_vs_ma50_pct')}%."),
        "why_still_early": f"{early}. The extension screen has {'failed; do not chase' if technical.get('extended') else 'not identified an extended setup'}.",
        "catalyst_support": f"{catalyst.get('description')} Timing: {catalyst.get('timing') or 'Missing'}.",
        "invalidation": invalidation,
    }


def build_swing_trade_engine(candidate_pool, market_data, ai_radar, biotech_radar,
                             ai_news_section=None, biotech_news_section=None, limit=8):
    candidates = {}
    for candidate in (candidate_pool or {}).get("candidates", []):
        ticker = candidate.get("ticker")
        if ticker not in (None, "Private", "N/A", "Missing"):
            candidates.setdefault(ticker, candidate)
    evaluated_states = []
    qualified_records = []
    technical_qualified = []
    for ticker, candidate in candidates.items():
        snapshot = (market_data or {}).get("securities", {}).get(ticker)
        if not snapshot:
            continue
        technical = technical_setup(snapshot)
        evaluated_states.append(technical["state"])
        if not technical["qualified_step_1"]:
            continue
        technical_qualified.append(ticker)
        domain = candidate.get("domain") or (snapshot.get("domains") or ["ai"])[0]
        catalyst = catalyst_check(ticker, domain, ai_radar, biotech_radar,
                                  ai_news_section, biotech_news_section)
        if not catalyst["credible"]:
            continue
        explanation = build_explanation(candidate.get("company") or ticker, technical, catalyst)
        evaluated_record = {
            "company": candidate.get("company") or ticker, "ticker": ticker,
            "exchange": candidate.get("exchange", ""), "listing_status": candidate.get("listing_status", "Public"),
            "domain": domain, "classification": technical["state"],
            "technical": technical, "catalyst": catalyst,
            "why_this_swing_trade_opportunity": explanation,
            "selection_principle": "Early Technical Reversal + Credible Catalyst",
            "market_data": {key: snapshot.get(key) for key in
                            ("current_price", "price_date", "currency", "source", "data_status")},
            "engine_version": "swing-trade-opportunity-v1",
        }
        evaluated_record["selection_score"] = round(
            technical["technical_setup_score"] * .8 +
            (catalyst.get("importance_score") if catalyst.get("importance_score") is not None else 75) * .2)
        evaluated_record["selection_score_note"] = (
            "Used only to order candidates that independently passed both steps; it cannot rescue a failed technical setup or missing catalyst.")
        qualified_records.append(evaluated_record)
    catalyst_qualified_count = len(qualified_records)
    opportunities = list(qualified_records)
    opportunities.sort(key=lambda item: (STATE_PRIORITY[item["classification"]],
                                         -item["selection_score"], item["ticker"]))
    opportunities = opportunities[:limit]
    for rank, row in enumerate(opportunities, 1):
        row["rank"] = rank
    state_counts = Counter(evaluated_states)
    selected_states = Counter(row["classification"] for row in opportunities)
    selected_names = ", ".join(row["ticker"] for row in opportunities[:4]) or "none"
    reasoning = [
        "Step 1 screens independently for a major decline, stabilization near a recent low, and an early reversal or entry-zone structure. Extended stocks are rejected.",
        "Step 2 runs only after the technical screen and requires a dated, source-backed clinical, regulatory, corporate, commercial, or industry catalyst.",
        "Early Reversal and Entry Zone rank ahead of Bottoming and Breakout because the strategy seeks improving setups before a substantial run-up.",
    ]
    takeaways = [
        f"{len(technical_qualified)} stocks passed the technical-first screen; {catalyst_qualified_count} also had a credible connected catalyst.",
        f"Current selected candidates: {selected_names}.",
        f"Selected-state distribution: {', '.join(f'{state} {count}' for state, count in selected_states.items()) or 'none'}.",
        "A catalyst cannot compensate for a failed or extended technical setup, and missing data never becomes a positive signal.",
    ]
    return {
        "methodology": {
            "engine_version": "swing-trade-opportunity-v1",
            "strategy": "Major Decline → Bottoming → Early Reversal → Entry Zone, followed by a separate credible-catalyst check.",
            "selection_principle": "Early Technical Reversal + Credible Catalyst = Strong Swing Trade Opportunity",
            "state_priority": ["Entry Zone", "Early Reversal", "Bottoming", "Breakout", "Extended"],
            "missing_data_policy": "Missing values remain missing and cannot satisfy either selection step.",
            "independence": "This engine does not use High-Conviction classification and does not modify Radar or Watchlist outputs.",
        },
        "reasoning": reasoning, "take_home_messages": takeaways,
        "opportunities": opportunities,
        "coverage": {"candidate_pool": len(candidates), "market_evaluated": len(evaluated_states),
                     "technical_qualified": len(technical_qualified), "catalyst_qualified": catalyst_qualified_count,
                     "selected": len(opportunities),
                     "state_counts": {state: state_counts.get(state, 0) for state in SWING_STATES}},
    }
