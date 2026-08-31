"""Phase 7 entry timing from daily close/volume history.

This module measures when a technically constructive entry may be forming. It
does not select securities and cannot override the fundamental/Radar gates.
"""

from statistics import mean


ENTRY_WEIGHTS = {
    "base_price_structure": 30,
    "moving_average_setup": 20,
    "volume_accumulation": 20,
    "momentum": 15,
    "relative_strength": 10,
    "breakout_extension": 5,
}

TIMING_STATES = {
    "buy-zone": "🟢 Buy Zone",
    "near-buy-zone": "🟡 Near Buy Zone",
    "base-building": "👀 Base Building",
    "breakout-confirmed": "🚀 Breakout Confirmed",
    "extended": "⚠️ Extended / Do Not Chase",
    "deterioration": "🔴 Technical Deterioration",
}

BUY_STATUSES = {
    "wait": "WAIT",
    "approaching-entry": "APPROACHING ENTRY",
    "in-entry-zone": "IN ENTRY ZONE",
    "ready-to-buy": "READY TO BUY",
    "extended": "EXTENDED / TOO LATE",
}


def average(values, minimum=1):
    valid = [value for value in values if value is not None]
    return sum(valid) / len(valid) if len(valid) >= minimum else None


def range_pct(values):
    if not values or min(values) <= 0:
        return None
    return round((max(values) / min(values) - 1) * 100, 2)


def calculate_entry_inputs(rows, moving_averages, macd_record):
    """Create auditable close/volume-derived features without naming chart patterns."""
    closes = [row.get("close") for row in rows if row.get("close") is not None]
    volumes = [row.get("volume") for row in rows if row.get("close") is not None]
    if not closes:
        return {}
    current = closes[-1]
    year_closes = closes[-252:]
    recent_63 = closes[-63:] if len(closes) >= 63 else closes
    year_high = max(year_closes) if year_closes else None
    year_low = min(year_closes) if year_closes else None
    recent_low = min(recent_63) if recent_63 else None
    recent_high = max(recent_63) if recent_63 else None
    drawdown_from_high = round((current / year_high - 1) * 100, 2) if year_high else None
    distance_from_recent_low = round((current / recent_low - 1) * 100, 2) if recent_low else None
    range_63 = range_pct(closes[-63:]) if len(closes) >= 63 else None
    range_42 = range_pct(closes[-42:]) if len(closes) >= 42 else None
    range_20 = range_pct(closes[-20:]) if len(closes) >= 20 else None
    if range_63 is not None and range_63 <= 25:
        base_sessions, base_range, base_low = 63, range_63, min(closes[-63:])
    elif range_42 is not None and range_42 <= 20:
        base_sessions, base_range, base_low = 42, range_42, min(closes[-42:])
    else:
        base_sessions, base_range, base_low = None, None, None
    ma_values = [moving_averages.get(key) for key in ("ma5", "ma10", "ma20", "ma50")]
    compression = ((max(ma_values) / min(ma_values) - 1) * 100
                   if all(value is not None and value > 0 for value in ma_values) else None)
    recent_volume = average(volumes[-10:], 8) if len(volumes) >= 10 else None
    prior_volume = average(volumes[-30:-10], 16) if len(volumes) >= 30 else None
    contraction = round(recent_volume / prior_volume, 2) if recent_volume is not None and prior_volume else None
    up_volume = down_volume = 0
    volume_days = 0
    start = max(1, len(closes) - 20)
    for index in range(start, len(closes)):
        volume = volumes[index] if index < len(volumes) else None
        if volume is None or closes[index] == closes[index - 1]:
            continue
        volume_days += 1
        if closes[index] > closes[index - 1]:
            up_volume += volume
        else:
            down_volume += volume
    accumulation = (round(min(3, up_volume / down_volume), 2) if volume_days >= 12 and down_volume > 0
                    else 3.0 if volume_days >= 12 and up_volume > 0 and down_volume == 0 else None)
    resistance = max(closes[-65:-5]) if len(closes) >= 65 else None
    breakout_pct = round((current / resistance - 1) * 100, 2) if resistance else None
    current_volume = volumes[-1] if volumes else None
    volume_20 = average(volumes[-20:], 12) if len(volumes) >= 20 else None
    breakout_volume = round(current_volume / volume_20, 2) if current_volume is not None and volume_20 else None
    support_candidates = [value for value in (base_low, moving_averages.get("ma50"))
                          if value is not None and value < current]
    invalidation = max(support_candidates) if support_candidates else None
    return {
        "history_sessions": len(closes), "base_duration_sessions": base_sessions,
        "fifty_two_week_high": round(year_high, 4) if year_high else None,
        "fifty_two_week_low": round(year_low, 4) if year_low else None,
        "drawdown_from_fifty_two_week_high_pct": drawdown_from_high,
        "recent_low_63d": round(recent_low, 4) if recent_low else None,
        "recent_high_63d": round(recent_high, 4) if recent_high else None,
        "distance_from_recent_low_pct": distance_from_recent_low,
        "base_range_pct": base_range, "range_63d_pct": range_63, "range_42d_pct": range_42,
        "tight_range_20d_pct": range_20, "base_low": round(base_low, 4) if base_low else None,
        "ma_compression_pct": round(compression, 2) if compression is not None else None,
        "volume_contraction_ratio": contraction, "up_down_volume_ratio_20d": accumulation,
        "resistance_level": round(resistance, 4) if resistance else None,
        "breakout_proximity_pct": breakout_pct, "breakout_volume_ratio": breakout_volume,
        "invalidation_level": round(invalidation, 4) if invalidation else None,
        "macd_improving": macd_record.get("improving"), "macd_crossover": macd_record.get("crossover"),
        "methodology": {
            "base": "A 63-session close range <=25%, or 42-session close range <=20%; this is a price-range screen, not a discretionary chart-pattern claim.",
            "resistance": "Highest close in the 60 sessions ending five sessions before the current close.",
            "invalidation": "Closest available support below price from the detected base low and MA50; omitted when neither is below price.",
            "decline_and_bottom": "Major-decline context uses the current close versus the trailing 252-session high; distance from the bottom uses the trailing 63-session low.",
            "volume": "Last-10-session average versus the preceding 20 sessions; accumulation compares up-day and down-day volume over 20 sessions.",
        },
    }


def factor(key, score, rationale, evidence, available_weight=None):
    weight = ENTRY_WEIGHTS[key]
    if score is None:
        available_weight = 0
    elif available_weight is None:
        available_weight = weight
    return {"key": key, "label": key.replace("_", " ").title(), "weight": weight,
            "available_weight": max(0, min(weight, available_weight)), "score": score,
            "missing": score is None, "rationale": rationale, "evidence": evidence}


def score_band(value, bands):
    if value is None:
        return None
    for test, score in bands:
        if test(value):
            return score
    return None


def score_entry_timing(snapshot, domain, thesis_gate):
    snapshot = snapshot or {}
    inputs = snapshot.get("entry_inputs") or {}
    price = snapshot.get("current_price")
    mas = snapshot.get("moving_averages") or {}
    returns = snapshot.get("returns") or {}
    rsi = snapshot.get("rsi_14")
    macd = snapshot.get("macd") or {}
    base_range, base_sessions = inputs.get("base_range_pct"), inputs.get("base_duration_sessions")
    if base_sessions == 63:
        base_score = score_band(base_range, [(lambda x: x <= 12, 100), (lambda x: x <= 15, 92),
                                              (lambda x: x <= 20, 82), (lambda x: x <= 25, 70)])
    elif base_sessions == 42:
        base_score = score_band(base_range, [(lambda x: x <= 12, 85), (lambda x: x <= 15, 78),
                                              (lambda x: x <= 20, 65)])
    elif inputs.get("history_sessions", 0) >= 42 and inputs.get("tight_range_20d_pct") is not None:
        base_score = 55 if inputs["tight_range_20d_pct"] <= 8 and price and mas.get("ma50") and price >= mas["ma50"] else 35
    else:
        base_score = None
    base_rationale = (f"{base_sessions}-session range {base_range}% detected by the close-range rule."
                      if base_sessions else f"No qualifying 42/63-session base; 20-session range is {inputs.get('tight_range_20d_pct', 'Missing')}%.")

    relationship = []
    ma_points = 0
    available_ma = 0
    for key, points in (("ma20", 4), ("ma50", 4), ("ma200", 4)):
        value = mas.get(key)
        if price is not None and value is not None:
            available_ma += points
            above = price >= value
            ma_points += points if above else 0
            relationship.append(f"price {'above' if above else 'below'} {key.upper()}")
    compression = inputs.get("ma_compression_pct")
    if compression is not None:
        available_ma += 8
        ma_points += 8 if compression <= 3 else 6 if compression <= 5 else 3 if compression <= 8 else 0
    ma_score = round(ma_points / available_ma * 100) if available_ma else None
    ma_rationale = f"{'; '.join(relationship) or 'MA relationships missing'}; MA5/10/20/50 spread {compression if compression is not None else 'Missing'}%."

    contraction, accumulation = inputs.get("volume_contraction_ratio"), inputs.get("up_down_volume_ratio_20d")
    volume_parts = []
    if contraction is not None:
        volume_parts.append((100 if contraction <= .75 else 80 if contraction <= .9 else 60 if contraction <= 1.1 else 30, 8))
    if accumulation is not None:
        volume_parts.append((100 if accumulation >= 1.5 else 80 if accumulation >= 1.1 else 55 if accumulation >= .9 else 25, 12))
    volume_score = round(sum(score * weight for score, weight in volume_parts) / sum(weight for _, weight in volume_parts)) if volume_parts else None
    volume_rationale = f"Volume contraction ratio {contraction if contraction is not None else 'Missing'}; 20-session up/down-volume ratio {accumulation if accumulation is not None else 'Missing'}."

    momentum_parts = []
    if rsi is not None:
        rsi_score = 100 if 40 <= rsi <= 60 else 80 if 60 < rsi <= 70 else 65 if 30 <= rsi < 40 else 40 if 70 < rsi <= 75 else 20
        momentum_parts.append((rsi_score, 8))
    histogram = macd.get("histogram")
    if histogram is not None:
        macd_score = 100 if macd.get("crossover") == "bullish" else 85 if histogram > 0 and macd.get("improving") else 70 if histogram > 0 else 55 if macd.get("improving") else 25
        momentum_parts.append((macd_score, 7))
    momentum_score = round(sum(score * weight for score, weight in momentum_parts) / sum(weight for _, weight in momentum_parts)) if momentum_parts else None
    momentum_rationale = f"RSI {rsi if rsi is not None else 'Missing'}; MACD histogram {histogram if histogram is not None else 'Missing'}, crossover {macd.get('crossover') or 'none'}, improving {macd.get('improving') if macd.get('improving') is not None else 'Missing'}."

    benchmark = "qqq" if domain == "ai" else "xbi"
    relative = (snapshot.get("relative_strength") or {}).get(benchmark, {})
    relative_values = [relative.get(key) for key in ("one_month", "three_month") if relative.get(key) is not None]
    relative_average = mean(relative_values) if relative_values else None
    relative_score = score_band(relative_average, [(lambda x: x >= 10, 100), (lambda x: x >= 5, 85),
                                                    (lambda x: x >= 0, 70), (lambda x: x >= -5, 45),
                                                    (lambda x: True, 20)])
    relative_rationale = f"Average available 1M/3M relative return versus {benchmark.upper()} is {round(relative_average, 2) if relative_average is not None else 'Missing'} percentage points."

    proximity = inputs.get("breakout_proximity_pct")
    breakout_volume = inputs.get("breakout_volume_ratio")
    breakout_confirmed = proximity is not None and 0 <= proximity <= 5 and breakout_volume is not None and breakout_volume >= 1.2
    breakout_score = score_band(proximity, [(lambda x: breakout_confirmed, 100), (lambda x: -2 <= x < 0, 90),
                                            (lambda x: -5 <= x < -2, 75), (lambda x: 0 <= x <= 5, 70),
                                            (lambda x: x > 8, 10), (lambda x: 5 < x <= 8, 35),
                                            (lambda x: True, 45)])
    breakout_rationale = f"Price is {proximity if proximity is not None else 'Missing'}% versus calculated resistance; current volume is {breakout_volume if breakout_volume is not None else 'Missing'}x its 20-session average."

    factors = [
        factor("base_price_structure", base_score, base_rationale, {"base_sessions": base_sessions, "range_pct": base_range, "tight_20d_pct": inputs.get("tight_range_20d_pct")}),
        factor("moving_average_setup", ma_score, ma_rationale, {"price": price, "moving_averages": mas, "compression_pct": compression}, available_ma),
        factor("volume_accumulation", volume_score, volume_rationale, {"contraction_ratio": contraction, "accumulation_ratio": accumulation}, sum(weight for _, weight in volume_parts)),
        factor("momentum", momentum_score, momentum_rationale, {"rsi": rsi, "macd": macd}, sum(weight for _, weight in momentum_parts)),
        factor("relative_strength", relative_score, relative_rationale, {"benchmark": benchmark, "relative_strength": relative}, 5 * len(relative_values)),
        factor("breakout_extension", breakout_score, breakout_rationale, {"resistance": inputs.get("resistance_level"), "proximity_pct": proximity, "volume_ratio": breakout_volume}),
    ]
    available = sum(item["available_weight"] for item in factors)
    total_score = round(sum(item["score"] * item["available_weight"] for item in factors if item["score"] is not None) / available) if available else None
    three_month = returns.get("three_month")
    distance_ma20 = round((price / mas["ma20"] - 1) * 100, 2) if price and mas.get("ma20") else None
    distance_ma50 = round((price / mas["ma50"] - 1) * 100, 2) if price and mas.get("ma50") else None
    extension_available = any(value is not None for value in (distance_ma20, distance_ma50, three_month, proximity))
    extension = ((distance_ma20 is not None and distance_ma20 > 12) or
                 (distance_ma50 is not None and distance_ma50 > 18) or
                 (three_month is not None and three_month > 40) or
                 (proximity is not None and proximity > 8)) if extension_available else None
    breakdown_available = all(value is not None for value in (price, mas.get("ma50"), mas.get("ma200"), histogram))
    breakdown = (price < mas["ma50"] and price < mas["ma200"] and histogram < 0) if breakdown_available else None
    gates = [
        {"key": "thesis", "label": "Thesis Gate", "passed": thesis_gate.get("passed"), "rationale": thesis_gate.get("rationale")},
        {"key": "extension", "label": "Extension / Do-Not-Chase Gate", "passed": None if extension is None else not extension,
         "rationale": f"Fails above 12% over MA20, 18% over MA50, 40% 3M run-up, or 8% beyond resistance. Current: MA20 {distance_ma20 if distance_ma20 is not None else 'Missing'}%, MA50 {distance_ma50 if distance_ma50 is not None else 'Missing'}%, 3M {three_month if three_month is not None else 'Missing'}%."},
        {"key": "breakdown", "label": "Breakdown Gate", "passed": None if breakdown is None else not breakdown,
         "rationale": "Fails only when price is below both MA50 and MA200 with a negative MACD histogram."},
    ]
    if breakdown:
        state_key = "deterioration"
    elif extension:
        state_key = "extended"
    elif thesis_gate.get("passed") is not True or extension is None or breakdown is None:
        state_key = "base-building"
    elif breakout_confirmed:
        state_key = "breakout-confirmed"
    elif total_score is not None and total_score >= 75 and base_sessions and ma_score is not None and ma_score >= 65:
        state_key = "buy-zone"
    elif total_score is not None and total_score >= 65 and proximity is not None and -5 <= proximity <= 2:
        state_key = "near-buy-zone"
    else:
        state_key = "base-building"
    actionable = all(gate["passed"] is True for gate in gates) and state_key in ("buy-zone", "near-buy-zone", "breakout-confirmed")
    if thesis_gate.get("passed") is not True:
        guidance = "Not actionable: the fundamental/Radar Thesis Gate has not passed. Technical conditions cannot override it."
    elif state_key == "buy-zone":
        guidance = "Technically actionable for a staged entry while the extension and breakdown gates remain clear; use the calculated invalidation support only if available."
    elif state_key == "near-buy-zone":
        guidance = "Watch for a close through calculated resistance with confirming volume, or a controlled pullback that holds MA20/MA50."
    elif state_key == "breakout-confirmed":
        guidance = "Breakout has close-and-volume confirmation under this ruleset; avoid entry if price moves beyond the extension gate and consider a retest rather than chasing."
    elif state_key == "extended":
        guidance = "Do not chase. Wait for distance from MA20/MA50 to normalize or for a new multiweek range to form."
    elif state_key == "deterioration":
        guidance = "No technical entry. Require price recovery above key moving averages and momentum stabilization before reassessment."
    else:
        guidance = "Continue monitoring the base/range; no rules-based entry confirmation is present."
    return {"entry_timing_score": total_score, "data_completeness": available,
            "state_key": state_key, "state": TIMING_STATES[state_key], "actionable": actionable,
            "factors": factors, "gates": gates, "key_technical_evidence": [item["rationale"] for item in factors],
            "entry_guidance": guidance, "resistance_level": inputs.get("resistance_level"),
            "invalidation_level": inputs.get("invalidation_level"), "price_date": snapshot.get("price_date"),
            "data_source": snapshot.get("source"), "entry_inputs": inputs,
            "engine_version": "entry-timing-v1"}


def thesis_gate_for_pick(row, domain):
    gates = {gate.get("key"): gate for gate in row.get("gates", [])}
    required = (["proven_business", "profitability", "growth_durability",
                 "financial_strength", "competitive_position", "valuation"]
                if "proven_business" in gates else
                ["evidence", "beneficiary_proof", "expectation"])
    if domain == "biotech":
        required.append("binary_integrity")
    passed = all(gates.get(key, {}).get("passed") is True for key in required)
    failures = [gates.get(key, {}).get("label", key) for key in required if gates.get(key, {}).get("passed") is not True]
    return {"passed": passed, "rationale": ("All nontechnical High-Conviction gates passed."
             if passed else "Not passed: " + ", ".join(failures) + ".")}


def compact_entry_timing(record):
    keys = ("entry_timing_score", "data_completeness", "state_key", "state", "actionable",
            "entry_guidance", "resistance_level", "invalidation_level", "price_date", "data_source")
    return {key: record.get(key) for key in keys}


def build_buy_decision(timing):
    """Translate existing thesis/timing outputs into an explicit buy-now decision."""
    timing = timing or {}
    state_key = timing.get("state_key")
    if state_key == "extended":
        status_key = "extended"
    elif state_key == "breakout-confirmed" and timing.get("actionable"):
        status_key = "ready-to-buy"
    elif state_key == "buy-zone" and timing.get("actionable"):
        status_key = "in-entry-zone"
    elif state_key == "near-buy-zone" and timing.get("actionable"):
        status_key = "approaching-entry"
    else:
        status_key = "wait"

    thesis_gate = next((gate for gate in timing.get("gates", []) if gate.get("key") == "thesis"), {})
    if status_key in ("ready-to-buy", "in-entry-zone"):
        missing_condition = "None under the current rules; continue monitoring the extension, breakdown, and thesis-invalidation conditions."
        why_buy_now = ("The fundamental/Radar thesis gate has passed and the existing Entry Timing engine identifies an actionable "
                       f"{timing.get('state', 'technical setup')}. {timing.get('entry_guidance', '')}").strip()
    elif status_key == "approaching-entry":
        missing_condition = timing.get("entry_guidance") or "A rules-based entry confirmation is still required."
        why_buy_now = "Not ready now. The thesis gate has passed, but the entry setup still needs confirmation."
    elif status_key == "extended":
        missing_condition = timing.get("entry_guidance") or "Price must reset below the extension threshold or form a new base."
        why_buy_now = "Not ready now. The existing Extension / Do-Not-Chase Gate blocks a new entry."
    elif thesis_gate.get("passed") is not True:
        missing_condition = thesis_gate.get("rationale") or "The fundamental/Radar thesis gate has not passed."
        why_buy_now = "Not ready now. Technical conditions cannot override an incomplete fundamental/Radar thesis."
    else:
        missing_condition = timing.get("entry_guidance") or "A complete, rules-based technical entry setup is still missing."
        why_buy_now = "Not ready now. The stock remains selected, but the technical entry setup is incomplete."

    return {"status_key": status_key, "status": BUY_STATUSES[status_key],
            "ready_now": status_key in ("ready-to-buy", "in-entry-zone"),
            "why_buy_now": why_buy_now, "missing_condition": missing_condition,
            "timing_state": timing.get("state"), "entry_timing_score": timing.get("entry_timing_score"),
            "as_of": timing.get("price_date"), "engine_version": "high-conviction-buy-decision-v1"}


def _rounded_price(value):
    if value is None or value <= 0:
        return None
    return round(value, 4 if value < 1 else 2)


def build_biotech_swing_plan(snapshot, timing, buy_decision):
    """Create transparent swing-planning levels; these are not valuation price targets."""
    snapshot, timing = snapshot or {}, timing or {}
    current = snapshot.get("current_price")
    resistance = timing.get("resistance_level")
    state_key = timing.get("state_key")
    current = current if isinstance(current, (int, float)) and current > 0 else None
    resistance = resistance if isinstance(resistance, (int, float)) and resistance > 0 else None

    if state_key in ("extended", "deterioration"):
        anchor = None
        basis = "No active entry zone while the setup is extended or technically deteriorating."
    elif buy_decision.get("ready_now") and current is not None:
        anchor = current
        basis = "Current daily close is the reference because the existing Entry Timing engine is actionable now."
    elif resistance is not None:
        anchor = resistance
        basis = ("Planned entry reference is the existing calculated resistance level; the zone is inactive until all thesis gates "
                 "pass and the Entry Timing engine confirms the setup.")
    else:
        anchor = None
        basis = "Missing: no reliable current-price or calculated-resistance entry reference is available."

    if anchor is None:
        entry_zone = {"low": None, "high": None, "reference": None, "active": False, "basis": basis}
        targets = {"plus_10": None, "plus_15": None, "plus_20": None,
                   "basis": "Missing: targets require a reliable entry reference."}
    else:
        entry_zone = {"low": _rounded_price(anchor * .99), "high": _rounded_price(anchor * 1.01),
                      "reference": _rounded_price(anchor), "active": bool(buy_decision.get("ready_now")), "basis": basis}
        targets = {"plus_10": _rounded_price(anchor * 1.10), "plus_15": _rounded_price(anchor * 1.15),
                   "plus_20": _rounded_price(anchor * 1.20),
                   "basis": "Mechanical swing levels measured from the entry-zone reference; not analyst or valuation targets."}
    return {"current_price": _rounded_price(current), "currency": snapshot.get("currency"),
            "price_date": snapshot.get("price_date"), "entry_zone": entry_zone, "targets": targets,
            "engine_version": "biotech-swing-plan-v1"}


def build_entry_timing_layer(ai_rows, biotech_rows, market_data, watchlists=None):
    records = {}
    for domain, rows in (("ai", ai_rows), ("biotech", biotech_rows)):
        for row in rows:
            ticker = row.get("ticker")
            snapshot = (market_data or {}).get("securities", {}).get(ticker)
            timing = score_entry_timing(snapshot, domain,
                                        thesis_gate_for_pick(row, domain))
            row["entry_timing"] = timing
            row["buy_decision"] = build_buy_decision(timing)
            if domain == "biotech":
                row["swing_trade"] = build_biotech_swing_plan(snapshot, timing, row["buy_decision"])
            records[f"{domain}:{ticker}"] = timing
    for domain, rows in (watchlists or {}).items():
        for row in rows:
            key = f"{domain}:{row.get('ticker')}"
            if key not in records:
                records[key] = score_entry_timing((market_data or {}).get("securities", {}).get(row.get("ticker")), domain,
                    {"passed": False, "rationale": "Watchlist-only name lacks a complete current High-Conviction thesis evaluation."})
            row["entry_timing"] = compact_entry_timing(records[key])
    states = {label: sum(item["state_key"] == key for item in records.values()) for key, label in TIMING_STATES.items()}
    actionable = [key for key, item in records.items() if item.get("actionable")]
    return {"schema_version": "entry-timing-v1", "methodology": {"weights": ENTRY_WEIGHTS,
        "states": list(TIMING_STATES.values()), "missing_policy": "Missing factors are excluded and available weights renormalize; missing inputs are never zero.",
        "selection_boundary": "Entry Timing does not alter candidate discovery, High-Conviction scores, rankings, or fundamental/Radar gates.",
        "buy_decision": "WAIT, APPROACHING ENTRY, IN ENTRY ZONE, READY TO BUY, and EXTENDED / TOO LATE are direct mappings of the existing thesis and Entry Timing gates; they do not rescore or rerank candidates.",
        "biotech_swing_plan": "Biotech entry zones use a +/-1% band around the actionable current close or the existing calculated resistance planning reference. +10%/+15%/+20% levels are mechanical swing levels from that reference, not valuation targets.",
        "price_basis": "Daily provider close and volume history from the existing shared market layer; no adjusted-close or intraday series is claimed."},
        "records": records, "coverage": {"requested": len(records),
            "scored": sum(item["entry_timing_score"] is not None for item in records.values()),
            "complete": sum(item["data_completeness"] == 100 for item in records.values()),
            "states": states, "actionable": len(actionable), "actionable_keys": actionable}}
