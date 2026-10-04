"""Independent full-market Swing Trade execution system.

The production engine receives a broad U.S.-listed universe directly, never a
Radar or High-Conviction shortlist. It separates biotech from non-biotech and
applies three shared technical definitions: Stage 1 launch, Stage 2 trend
continuation, and post-advance re-base/re-acceleration. Catalyst validation is
a separate pool-specific decision layer, not a technical classifier.
"""

from collections import Counter
from datetime import date, datetime
from email.utils import parsedate_to_datetime
import math
import re

try:
    from .catalyst_validation import (THEME_ONLY_STATUS, WAIT_FOR_CATALYST_ACTION,
                                      company_catalyst_validation, company_evidence_source_priority,
                                      company_name_variants)
except ImportError:
    from catalyst_validation import (THEME_ONLY_STATUS, WAIT_FOR_CATALYST_ACTION,
                                     company_catalyst_validation, company_evidence_source_priority,
                                     company_name_variants)


SWING_STATES = ("Falling", "Bottoming", "Early Reversal", "Entry Zone", "Breakout",
                "Extended", "Failed Reversal / Technical Deterioration")
STATE_PRIORITY = {"Entry Zone": 0, "Early Reversal": 1, "Bottoming": 2,
                  "Breakout": 3, "Falling": 4, "Extended": 5,
                  "Failed Reversal / Technical Deterioration": 6}
FAVORABLE_TRANSITION_PRIORITY = {
    ("Bottoming", "Early Reversal"): 0,
    ("Early Reversal", "Entry Zone"): 1,
    ("Entry Zone", "Breakout"): 2,
    ("Falling", "Bottoming"): 3,
}

SWING_TECHNICAL_SCAN_LIMIT = None
SWING_BIOTECH_SCAN_LIMIT = None
SWING_BUY_NOW_LIMIT = 10
STRATEGY_B_CATALYST_STATUSES = (
    "QUALIFYING", "IDENTITY_FAILED", "SOURCE_UNAVAILABLE", "OUTSIDE_WINDOW",
    "NO_COMPANY_CATALYST",
)
STRATEGY_B_CATALYST_LOOKBACK_DAYS = 3
MATERIAL_INSIDER_PURCHASE_USD = 250_000
BIOTECH_TERMS = (
    "biotech", "biotechnology", "biopharma", "biopharmaceutical", "pharmaceutical",
    "therapeutic", "drug manufacturer", "drug development", "genomic medicine",
)
BIOTECH_AMBIGUOUS_TERMS = (
    "animal health", "veterinary", "livestock", "nutrition", "nutritional", "dietary supplement",
    "consumer health", "medical device", "medical instrument", "laboratory instrument",
    "diagnostic", "clinical research service", "contract research", "health care plan",
    "medical distribution", "other pharmaceuticals",
    "commercial physical & biological research", "commercial physical & biological resarch",
)
HUMAN_THERAPEUTIC_EVIDENCE = (
    "clinical-stage biopharmaceutical", "commercial-stage biopharmaceutical",
    "develops and commercializes medicines", "develops and commercializes therapies",
    "discovery and development of therapeutics", "pipeline of drug candidates",
    "proprietary therapeutics", "human therapeutics", "medicines for patients",
)


def _number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def biotech_classification_needs_profile(company):
    sector = str(company.get("sector") or "").lower()
    industry = str(company.get("industry") or "").lower()
    name = str(company.get("company") or company.get("name") or "").lower()
    text = " ".join((sector, industry, name)).replace("no diagnostic substances", "")
    healthcare_sector = any(term in sector for term in ("health", "medical", "biotech", "pharma"))
    biotech_taxonomy = healthcare_sector and any(term in text for term in BIOTECH_TERMS)
    return bool(biotech_taxonomy and any(term in text for term in BIOTECH_AMBIGUOUS_TERMS))


def _direct_human_therapeutic_evidence(company):
    description = " ".join(str(company.get(key) or "") for key in
                           ("description", "business_description", "business_evidence")).lower()
    if any(term in description for term in HUMAN_THERAPEUTIC_EVIDENCE):
        return True
    develops = any(term in description for term in
                   ("develops", "developing", "discovers", "discovery", "researching",
                    "clinical pipeline"))
    therapeutic = any(term in description for term in
                      ("therapeutic", "drug candidate", "medicine", "treatment"))
    human = any(term in description for term in
                ("human", "patient", "oncology", "disease", "clinical-stage"))
    proprietary = any(term in description for term in
                      ("proprietary", "our pipeline", "its pipeline", "commercializes",
                       "commercializing"))
    medicine_portfolio = "portfolio" in description and any(
        term in description for term in ("medicine", "therapeutic", "drug candidate"))
    return bool((develops or medicine_portfolio) and therapeutic and human and
                (proprietary or medicine_portfolio))


def is_biotech_company(company):
    sector = str(company.get("sector") or "").lower()
    industry = str(company.get("industry") or "").lower()
    name = str(company.get("company") or company.get("name") or "").lower()
    text = " ".join((sector, industry, name)).replace("no diagnostic substances", "")
    healthcare_sector = any(term in sector for term in ("health", "medical", "biotech", "pharma"))
    if not (healthcare_sector and any(term in text for term in BIOTECH_TERMS)):
        return False
    if any(term in text for term in BIOTECH_AMBIGUOUS_TERMS):
        return _direct_human_therapeutic_evidence(company)
    return True


def buy_now_first_display(rows, limit):
    """Keep independent candidate rank while guaranteeing visible BUY NOW rows."""
    buy_now = [row for row in rows if row.get("action") == "BUY NOW"]
    waiting = [row for row in rows if row.get("action") != "BUY NOW"]
    return (buy_now + waiting)[:limit]


def select_swing_market_universe(listed_companies, limit=SWING_TECHNICAL_SCAN_LIMIT,
                                 biotech_limit=SWING_BIOTECH_SCAN_LIMIT,
                                 fallback_rows=None):
    """Run the cheap investability screen across every listed company.

    Price history is the expensive stage, so the full-market pass is followed
    by a liquidity-ranked, pool-balanced technical-history request.  This is
    independent of all Radar and High-Conviction membership and scores.
    """
    eligible = []
    rejected = {"price": 0, "market_cap": 0, "liquidity": 0, "classification": 0}
    for company in listed_companies or []:
        ticker = str(company.get("ticker") or "").upper()
        price = _number(company.get("last_price"))
        market_cap = _number(company.get("market_cap"))
        volume = _number(company.get("daily_volume"))
        if not ticker or price is None or price < 2:
            rejected["price"] += 1
            continue
        if market_cap is None or market_cap < 200_000_000:
            rejected["market_cap"] += 1
            continue
        if volume is None or volume < 150_000 or price * volume < 3_000_000:
            rejected["liquidity"] += 1
            continue
        if not company.get("sector") or not company.get("industry"):
            rejected["classification"] += 1
            continue
        pool = "biotech" if is_biotech_company(company) else "non_biotech"
        eligible.append({**company, "domain": "swing", "swing_pool": pool,
                         "listing_status": "Public", "dollar_volume_proxy": round(price * volume, 2)})
    biotech = sorted((row for row in eligible if row["swing_pool"] == "biotech"),
                     key=lambda row: (-row["dollar_volume_proxy"], -(row.get("market_cap") or 0), row["ticker"]))
    non_biotech = sorted((row for row in eligible if row["swing_pool"] == "non_biotech"),
                         key=lambda row: (-row["dollar_volume_proxy"], -(row.get("market_cap") or 0), row["ticker"]))
    selected_biotech = biotech if biotech_limit is None else biotech[:biotech_limit]
    remaining = None if limit is None else max(0, limit - len(selected_biotech))
    selected_non_biotech = non_biotech if remaining is None else non_biotech[:remaining]
    selected = selected_biotech + selected_non_biotech
    if not selected and fallback_rows:
        selected = [{**row, "domain": "swing",
                     "swing_pool": "biotech" if is_biotech_company(row) else "non_biotech",
                     "fallback_from_previous": True}
                    for row in (fallback_rows if limit is None else fallback_rows[:limit])]
    return selected, {
        "total_stocks_scanned": len(listed_companies or []),
        "initial_screen_pass": len(eligible),
        "technical_history_requested": len(selected),
        "biotech_initial_pass": len(biotech), "non_biotech_initial_pass": len(non_biotech),
        "biotech_history_requested": len(selected_biotech),
        "non_biotech_history_requested": len(selected_non_biotech),
        "initial_screen": (
            "Every company in the Nasdaq-listed U.S. stock feed is evaluated: price >= $2, "
            "market cap >= $200M, daily volume >=150K, dollar-volume proxy >=$3M, and sector/industry present."),
        "technical_history_funnel": (
            "Every eligible name receives daily OHLCV history. No Radar, Growth, or High-Conviction "
            "membership or score is read, and no arbitrary history-request quota truncates the screen."),
        "rejection_counts": rejected,
    }


def pct_distance(value, reference):
    return round((value / reference - 1) * 100, 2) if value is not None and reference else None


def average(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values)) if values else None


def swing_dynamic_final_score(technical, catalyst, transition=None):
    """Swing rank is technical-first; catalyst is a small secondary confirmation."""
    technical = technical or {}
    current, support, resistance = (technical.get(key) for key in
                                    ("current_price", "support", "resistance"))
    risk = current - support if all(isinstance(value, (int, float)) for value in (current, support)) and current > support else None
    reward = resistance - current if all(isinstance(value, (int, float)) for value in (current, resistance)) and resistance > current else None
    reward_risk = reward / risk if risk and reward is not None else None
    reward_score = (100 if reward_risk is not None and reward_risk >= 3 else
                    85 if reward_risk is not None and reward_risk >= 2 else
                    65 if reward_risk is not None and reward_risk >= 1.5 else
                    35 if reward_risk is not None else None)
    catalyst_score = ((catalyst or {}).get("importance_score")
                      if (catalyst or {}).get("credible") else 30)
    parts = [(technical.get("technical_setup_score"), 75),
             (reward_score, 20), (catalyst_score, 5)]
    available = [(value, weight) for value, weight in parts if isinstance(value, (int, float))]
    score = sum(value * weight for value, weight in available) / sum(weight for _, weight in available) if available else None
    if score is not None and (transition or {}).get("fresh_favorable_transition"):
        score += 15
    if technical.get("state") in ("Falling", "Failed Reversal / Technical Deterioration"):
        score -= 25
    if technical.get("extended") or technical.get("state") == "Extended":
        score -= 30
    return None if score is None else max(0, min(100, round(score)))


def technical_setup(snapshot, domain=None):
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
    base_range = inputs.get("base_range_pct")
    range_transitions = inputs.get("range_zone_transitions_63d")
    established_wave = bool(base_sessions in (42, 63) and base_range is not None and
                            12 <= base_range <= (20 if base_sessions == 42 else 25) and
                            range_transitions is not None and range_transitions >= 2)
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
    failed_pattern = inputs.get("failed_breakout") is True
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
    if failed_pattern:
        state = "Failed Reversal / Technical Deterioration"
    elif extended:
        state = "Extended"
    elif breakout:
        state = "Breakout"
    elif established_wave and stabilized and reversal_signal and momentum_usable and above_ma20 and near_ma50:
        state = "Entry Zone"
    elif established_wave and stabilized and reversal_signal and momentum_usable and near_ma20:
        state = "Early Reversal"
    elif not stabilized and not reversal_signal and (price_vs_ma20 is None or price_vs_ma20 < 0):
        state = "Falling"
    else:
        state = "Bottoming"

    wave_score = (100 if established_wave and base_range is not None and base_range >= 15 else
                  85 if established_wave else 40 if base_sessions in (42, 63) else
                  20 if base_range is not None else None)
    bottom_score = (100 if stabilized and distance_bottom is not None and distance_bottom <= 15 else
                    80 if stabilized else 45 if distance_bottom is not None and distance_bottom <= 30 else
                    20 if distance_bottom is not None else None)
    reversal_score = (100 if macd.get("crossover") == "bullish" else
                      85 if reversal_signal and momentum_usable else 60 if reversal_signal else
                      35 if histogram is not None else None)
    entry_score = (100 if state == "Entry Zone" else 90 if state == "Early Reversal" else
                   75 if state == "Breakout" else 60 if state == "Bottoming" else
                   30 if state == "Falling" else 10)
    volume_ratio = snapshot.get("volume_vs_20d_average")
    accumulation = inputs.get("up_down_volume_ratio_20d")
    contraction = inputs.get("volume_contraction_ratio")
    higher_low = inputs.get("higher_low_confirmed") is True
    daily_return = returns.get("daily")
    volume_contracted = contraction is not None and contraction <= .95
    accumulation_confirmed = accumulation is not None and accumulation >= 1.1
    breakout_volume_confirmed = breakout
    distribution_warning = bool(
        (accumulation is not None and accumulation < .85) or
        (volume_ratio is not None and volume_ratio >= 1.3 and
         daily_return is not None and daily_return < 0))
    exhaustion_warning = bool(volume_ratio is not None and volume_ratio >= 1.8 and
                              rsi is not None and rsi >= 72)
    volume_score = average([
        95 if breakout_volume_confirmed else 85 if volume_contracted else 55 if contraction is not None else None,
        95 if accumulation_confirmed else 45 if accumulation is not None else None,
    ])
    if distribution_warning:
        volume_score = min(volume_score or 30, 30)
    benchmark = "xbi" if domain == "biotech" else "qqq"
    relative = (snapshot.get("relative_strength") or {}).get(benchmark, {})
    relative_values = [relative.get(key) for key in ("one_month", "three_month")
                       if isinstance(relative.get(key), (int, float))]
    relative_score = (90 if relative_values and max(relative_values) >= 5 else
                      75 if relative_values and max(relative_values) > 0 else
                      50 if relative_values and max(relative_values) >= -2 else
                      25 if relative_values else None)
    momentum_score = average([
        95 if macd.get("crossover") == "bullish" else 80 if reversal_signal else 35 if histogram is not None else None,
        85 if rsi is not None and 40 <= rsi <= 65 else 60 if rsi is not None and 32 <= rsi <= 72 else 25 if rsi is not None else None,
        relative_score,
    ])
    trend_score = (95 if state in ("Entry Zone", "Breakout") else
                   85 if state == "Early Reversal" else 60 if state == "Bottoming" else
                   25 if state in ("Falling", "Failed Reversal / Technical Deterioration") else 35)
    entry_invalidation_score = average([
        entry_score,
        90 if inputs.get("invalidation_level") is not None else 60 if ma50 is not None else None,
    ])
    components = [
        ("Pattern / Base", wave_score, 20),
        ("Stage / Trend", average([bottom_score, trend_score]), 20),
        ("Price / Volume", volume_score, 20),
        ("Momentum / Relative Strength", momentum_score, 20),
        ("Entry / Invalidation", entry_invalidation_score, 20),
    ]
    available = sum(weight for _, score, weight in components if score is not None)
    score = (round(sum(score * weight for _, score, weight in components if score is not None) / available)
             if available else None)
    support_values = [value for value in (inputs.get("recent_low_63d"), inputs.get("base_low"), ma50)
                      if value is not None and price is not None and value < price]
    support = max(support_values) if support_values else None
    risk = price - support if price is not None and support is not None and price > support else None
    resistance = inputs.get("resistance_level")
    reward = resistance - price if price is not None and resistance is not None and resistance > price else None
    reward_risk = round(reward / risk, 2) if risk and reward is not None else None
    near_support = bool(distance_bottom is not None and distance_bottom <= 15 and
                        (price_vs_ma50 is None or price_vs_ma50 <= 8))
    selling_exhaustion = bool((contraction is not None and contraction <= .95) or
                              (accumulation is not None and accumulation >= 1))
    confirmed_reversal = bool(reversal_signal and momentum_usable and above_ma20 and higher_low)
    invalidation = inputs.get("invalidation_level") or support
    qualified = bool(established_wave and near_support and selling_exhaustion and
                     confirmed_reversal and state in ("Early Reversal", "Entry Zone") and
                     reward_risk is not None and reward_risk >= 1.5 and not extended and available >= 60)
    patterns = []
    def add_pattern(name, confirmed, evidence):
        if confirmed:
            patterns.append({"name": name, "evidence": evidence})
    add_pattern("Major Base", base_sessions in (42, 63) and base_range is not None,
                f"{base_sessions}-session base with {base_range}% range.")
    add_pattern("Tight / Flat Base", base_sessions in (42, 63) and tight_range is not None and
                tight_range <= 15 and volume_contracted,
                f"{tight_range}% 20-session range with contracting volume.")
    add_pattern("Triangle / Consolidation", range_transitions is not None and range_transitions >= 3 and
                tight_range is not None and tight_range <= 18 and volume_contracted,
                f"{range_transitions} range-zone transitions with price/volume contraction; exact trendlines are not inferred.")
    add_pattern("Cup with Handle", inputs.get("cup_with_handle_confirmed") is True,
                "Explicit history-derived cup-with-handle flag is confirmed.")
    add_pattern("Double Bottom", inputs.get("double_bottom_confirmed") is True,
                "Explicit history-derived double-bottom flag is confirmed.")
    add_pattern("Support / MA Pullback", near_support and higher_low,
                "Price is near calculated support with a confirmed higher low.")
    add_pattern("Reversal", confirmed_reversal,
                "Higher low, MA20 reclaim, usable momentum, and reversal evidence are present.")
    add_pattern("Breakout", breakout,
                "Price is within 5% above resistance with at least 1.2x breakout volume.")
    add_pattern("Failed Breakout / Reversal", failed_pattern,
                "The shared history layer explicitly flags a failed breakout.")
    primary_pattern = (next((item["name"] for preferred in
                            ("Failed Breakout / Reversal", "Breakout", "Cup with Handle", "Double Bottom",
                             "Tight / Flat Base", "Triangle / Consolidation", "Support / MA Pullback",
                             "Reversal", "Major Base") for item in patterns if item["name"] == preferred),
                            "Unclassified / Insufficient Pattern Evidence"))
    return {
        "state": state, "technical_setup_score": score, "data_completeness": available,
        "qualified_step_1": qualified, "major_decline_confirmed": major_decline,
        "bottom_stabilized": stabilized, "established_wave": established_wave,
        "near_support": near_support, "selling_exhaustion": selling_exhaustion,
        "higher_low_confirmed": higher_low, "early_reversal_confirmed": confirmed_reversal,
        "current_price": price, "ma20": ma20, "ma50": ma50,
        "price_vs_ma20_pct": price_vs_ma20, "price_vs_ma50_pct": price_vs_ma50,
        "fifty_two_week_high": inputs.get("fifty_two_week_high"),
        "drawdown_from_high_pct": drawdown, "recent_low": inputs.get("recent_low_63d"),
        "distance_from_bottom_pct": distance_bottom, "bottom_range_20d_pct": tight_range,
        "base_duration_sessions": base_sessions, "range_zone_transitions_63d": range_transitions,
        "rsi_14": rsi, "macd": macd,
        "returns": returns, "relative_strength": snapshot.get("relative_strength") or {},
        "volume_vs_20d_average": volume_ratio, "up_down_volume_ratio_20d": accumulation,
        "pattern": primary_pattern, "recognized_patterns": patterns,
        "pattern_policy": "Named patterns require calculable history evidence; cup-handle and double-bottom labels are never inferred without explicit confirmation.",
        "volume_state": {"accumulation": accumulation_confirmed,
                         "contraction": volume_contracted,
                         "breakout_confirmation": breakout_volume_confirmed,
                         "distribution_warning": distribution_warning,
                         "exhaustion_warning": exhaustion_warning},
        "momentum_relative_strength": {"benchmark": benchmark.upper(),
                                        "score": momentum_score,
                                        "relative_strength_score": relative_score},
        "support": round(support, 4) if support is not None else None,
        "resistance": resistance, "reward_risk_to_resistance": reward_risk,
        "breakout_proximity_pct": proximity, "extended": extended,
        "invalidation_level": round(invalidation, 4) if invalidation is not None else None,
        "components": [{"label": label, "score": value, "weight": weight,
                        "missing": value is None} for label, value, weight in components],
        "price_date": snapshot.get("price_date"), "source": snapshot.get("source"),
    }


def parse_day(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def transition_metrics(record):
    technical = (record or {}).get("technical") or record or {}
    return {
        "current_price": technical.get("current_price"), "ma20": technical.get("ma20"),
        "ma50": technical.get("ma50"), "price_vs_ma20_pct": technical.get("price_vs_ma20_pct"),
        "price_vs_ma50_pct": technical.get("price_vs_ma50_pct"), "recent_low": technical.get("recent_low"),
        "support": technical.get("support"), "resistance": technical.get("resistance"),
        "breakout_proximity_pct": technical.get("breakout_proximity_pct"),
        "volume_vs_20d_average": technical.get("volume_vs_20d_average"),
        "macd": technical.get("macd") or {}, "returns": technical.get("returns") or {},
        "relative_strength": technical.get("relative_strength") or {},
    }


def stage_transition(previous, technical, domain="ai"):
    """Compare daily technical states; price acceleration alone never confirms a change."""
    previous = previous or {}
    prior_stage = previous.get("stage") or previous.get("classification")
    current_stage = technical.get("state")
    prior = transition_metrics(previous)
    current = transition_metrics(technical)
    signals = []

    higher_low = (prior.get("recent_low") is not None and current.get("recent_low") is not None and
                  current["recent_low"] >= prior["recent_low"] * 1.005)
    if higher_low:
        signals.append("Higher trailing low")
    ma20_reclaim = (prior.get("price_vs_ma20_pct") is not None and current.get("price_vs_ma20_pct") is not None and
                    prior["price_vs_ma20_pct"] < 0 <= current["price_vs_ma20_pct"])
    if ma20_reclaim:
        signals.append("Price reclaimed MA20")
    support_reclaim = (prior.get("support") is not None and prior.get("current_price") is not None and
                       current.get("current_price") is not None and
                       prior["current_price"] <= prior["support"] < current["current_price"])
    if support_reclaim:
        signals.append("Price reclaimed prior support")
    ma20_slope = (prior.get("ma20") is not None and current.get("ma20") is not None and prior["ma20"] > 0 and
                  current["ma20"] >= prior["ma20"] * 1.001)
    if ma20_slope:
        signals.append("MA20 slope turned/improved upward")
    prior_spread = pct_distance(prior.get("ma20"), prior.get("ma50"))
    current_spread = pct_distance(current.get("ma20"), current.get("ma50"))
    ma_structure = (prior_spread is not None and current_spread is not None and
                    current_spread >= prior_spread + .5)
    if ma_structure:
        signals.append("MA20/MA50 structure improved")
    resistance_breakout = (current_stage == "Breakout" and current.get("breakout_proximity_pct") is not None and
                           0 <= current["breakout_proximity_pct"] <= 5)
    if resistance_breakout:
        signals.append("Price cleared calculated resistance")
    volume_expansion = (current.get("volume_vs_20d_average") is not None and
                        current["volume_vs_20d_average"] >= 1.2)
    if volume_expansion:
        signals.append("Volume expanded versus 20-day average")
    prior_macd = prior.get("macd") or {}
    current_macd = current.get("macd") or {}
    momentum_improvement = bool(
        current_macd.get("crossover") == "bullish" or
        (current_macd.get("improving") is True and prior_macd.get("improving") is not True))
    if momentum_improvement:
        signals.append("MACD reversal momentum improved")
    benchmark = "xbi" if domain == "biotech" else "qqq"
    prior_relative = (prior.get("relative_strength") or {}).get(benchmark, {})
    current_relative = (current.get("relative_strength") or {}).get(benchmark, {})
    relative_acceleration = (prior_relative.get("one_month") is not None and
                             current_relative.get("one_month") is not None and
                             current_relative["one_month"] >= prior_relative["one_month"] + 2)
    if relative_acceleration:
        signals.append(f"Relative strength versus {benchmark.upper()} accelerated")
    prior_daily = (prior.get("returns") or {}).get("daily")
    current_daily = (current.get("returns") or {}).get("daily")
    price_acceleration = (current_daily is not None and current_daily >= 4 and
                          (prior_daily is None or current_daily > prior_daily))
    if price_acceleration:
        signals.append("Daily price acceleration detected")

    deterioration = bool(
        prior_stage in ("Early Reversal", "Entry Zone", "Breakout") and
        current_stage in ("Falling", "Bottoming") and
        ((current.get("price_vs_ma20_pct") is not None and current["price_vs_ma20_pct"] < -3) or
         current_macd.get("crossover") == "bearish" or
         (prior.get("support") is not None and current.get("current_price") is not None and
          current["current_price"] < prior["support"])))
    display_stage = "Failed Reversal / Technical Deterioration" if deterioration else current_stage
    pair = (prior_stage, display_stage)
    changed = bool(prior_stage and prior_stage != display_stage)
    structural_count = sum((higher_low, ma20_reclaim, support_reclaim, ma20_slope, ma_structure, resistance_breakout))
    confirming_count = sum((volume_expansion, momentum_improvement, relative_acceleration))
    confirmed_today = bool(changed and pair in FAVORABLE_TRANSITION_PRIORITY and structural_count >= 1 and
                           structural_count + confirming_count >= 2)
    as_of = technical.get("price_date")
    previous_transition = previous.get("transition") or {}
    previous_change = (previous.get("last_changed_on") or previous_transition.get("last_changed_on") or
                       previous.get("as_of"))
    last_changed_on = as_of if changed else previous_change
    current_day, changed_day = parse_day(as_of), parse_day(last_changed_on)
    days_since = ((current_day - changed_day).days if current_day and changed_day and current_day >= changed_day else None)
    carried_transition = bool(
        not changed and previous_transition.get("current_stage") == display_stage and
        previous_transition.get("previous_stage") not in (None, "", "Unavailable"))
    display_previous = previous_transition.get("previous_stage") if carried_transition else prior_stage
    if carried_transition:
        signals = list(previous_transition.get("signals") or signals)
    fresh_favorable = bool(
        confirmed_today or
        (carried_transition and previous_transition.get("fresh_favorable_transition") and
         days_since is not None and days_since <= 5))
    return {
        "previous_stage": display_previous or "Unavailable", "current_stage": display_stage,
        "transition": f"{display_previous or 'Unavailable'} → {display_stage}", "changed": changed,
        "fresh_favorable_transition": fresh_favorable, "failed_reversal": deterioration,
        "days_since_change": days_since, "last_changed_on": last_changed_on,
        "signals": signals, "large_one_day_gain_only": bool(price_acceleration and not confirmed_today and len(signals) == 1),
        "confirmation_note": ("Confirmed by multiple non-price technical signals." if fresh_favorable else
                              "No fresh favorable transition is confirmed; a large one-day gain alone is insufficient."),
    }


def prior_stage_map(section):
    mapped = {row.get("ticker"): row for row in (section or {}).get("stage_tracking", []) if row.get("ticker")}
    for row in (section or {}).get("opportunities", []):
        ticker = row.get("ticker")
        if ticker and ticker not in mapped:
            mapped[ticker] = {"ticker": ticker, "stage": row.get("classification"),
                              "as_of": (row.get("technical") or {}).get("price_date"),
                              "technical": row.get("technical") or {}}
    return mapped


def section_events(section):
    section = section or {}
    return list(section.get("stories", [])) + list(section.get("important_news_archive", []))


def matching_news_catalyst(ticker, section, company=None):
    matches = []
    for event in section_events(section):
        source_link = event.get("source_link") or event.get("url")
        validation = company_catalyst_validation(event, ticker, company)
        if validation["valid"] and source_link and (event.get("news_importance_score") or 0) >= 65:
            matches.append((event, validation))
    if not matches:
        return None
    event, validation = max(matches, key=lambda pair: (company_evidence_source_priority(pair[0]),
                                                       pair[0].get("news_importance_score") or 0,
                                                       pair[0].get("published_at") or pair[0].get("date") or ""))
    return {
        "credible": True, "description": event.get("new_information") or event.get("headline"),
        "status": validation["status"], "validation_reason": validation["reason"],
        "company_specific_catalyst": event.get("new_information") or event.get("headline"),
        "industry_theme_catalyst": None,
        "event_type": event.get("event_type"), "timing": event.get("published_at") or event.get("date"),
        "source": event.get("source"), "date": event.get("published_at") or event.get("date"),
        "source_link": event.get("source_link") or event.get("url"),
        "importance_score": event.get("news_importance_score"),
        "basis": "Source-backed News event with Importance Score at least 65; News does not set the technical classification.",
    }


def _event_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
    return parsed.date()


def strategy_b_identity_terms(candidate, retrieval=None):
    """Build reusable current/former-name, ticker and product identity terms."""
    retrieval = retrieval or {}
    terms = [candidate.get("company"), candidate.get("name"), candidate.get("ticker")]
    for key in ("aliases", "former_names", "dba_names", "products", "programs", "drug_names"):
        value = candidate.get(key) or retrieval.get(key) or []
        terms.extend(value if isinstance(value, (list, tuple, set)) else [value])
    expanded = []
    for term in terms:
        if not term:
            continue
        expanded.append(str(term).strip())
        expanded.extend(company_name_variants(term))
    return list(dict.fromkeys(item for item in expanded if item))


def strategy_b_event_category(event):
    """Classify source events without allowing analyst or peer news into the core gate."""
    text = " ".join(str(event.get(key) or "") for key in (
        "headline", "new_information", "description", "event_type", "form", "transaction_type",
    )).lower()
    if event.get("theme_only") or event.get("peer_readthrough") or any(
            term in text for term in ("peer read-through", "peer readthrough", "sector read-through",
                                      "sector readthrough", "rival's results", "competitor's results")):
        return "THEME_EVIDENCE"
    if event.get("analyst_action") or any(term in text for term in (
            "analyst upgrade", "upgraded to", "initiates coverage", "initiated coverage",
            "price target", "reiterates buy", "reiterated buy")):
        return "ANALYST_ACTION"
    if event.get("catalyst_category"):
        return event["catalyst_category"]
    purchase_value = event.get("purchase_value_usd")
    transaction_code = str(event.get("transaction_code") or "").upper()
    open_market = event.get("open_market_purchase") is True or transaction_code == "P" or any(
        term in text for term in ("open-market purchase", "open market purchase", "insider bought", "insider purchase"))
    if open_market and isinstance(purchase_value, (int, float)) and purchase_value >= MATERIAL_INSIDER_PURCHASE_USD:
        return "MATERIAL_INSIDER_PURCHASE"
    if "trial" in text and any(term in text for term in ("surges on", "jumps on", "rallies on")):
        return "CLINICAL_DATA"
    categories = (
        ("EARNINGS_GUIDANCE_BUYBACK", ("earnings", "financial results", "revenue", "guidance",
                                        "outlook", "share repurchase", "buyback")),
        ("CLINICAL_DATA", ("clinical results", "trial results", "trial win", "topline", "readout", "primary endpoint",
                           "phase 1", "phase 2", "phase 3", "pivotal")),
        ("REGULATORY", ("fda", "approval", "approved", "complete response letter", "clinical hold",
                        "bla", "nda", "pdufa", "fast track", "breakthrough therapy")),
        ("TRANSACTION", ("acquisition", "acquires", "merger", "license", "licensing", "partnership",
                         "contract", "deal")),
        ("CAPITAL_OR_COMMERCIAL", ("financing", "offering", "launch", "commercial", "sales",
                                   "reimbursement", "manufacturing", "orders", "backlog")),
    )
    return next((label for label, terms in categories if any(term in text for term in terms)), None)


def _strategy_b_result(status, reason, event=None, category=None, theme_event=None, analyst_event=None):
    event = event or {}
    qualifying = status == "QUALIFYING"
    description = (event.get("new_information") or event.get("headline")
                   if qualifying else "Missing / Not Yet Confirmed")
    return {
        "credible": qualifying,
        "status": status,
        "catalyst_status": status,
        "description": description,
        "validation_reason": reason,
        "company_specific_catalyst": description if qualifying else None,
        "industry_theme_catalyst": ((theme_event or {}).get("new_information") or
                                     (theme_event or {}).get("headline")),
        "analyst_evidence": ((analyst_event or {}).get("new_information") or
                             (analyst_event or {}).get("headline")),
        "event_type": category or event.get("event_type"),
        "timing": event.get("published_at") or event.get("date"),
        "source": event.get("source"),
        "date": event.get("published_at") or event.get("date"),
        "source_link": event.get("source_link") or event.get("url"),
        "importance_score": event.get("news_importance_score"),
        "basis": reason,
    }


def resolve_strategy_b_catalyst(candidate, assessment, retrieval=None,
                                ai_news_section=None, biotech_news_section=None):
    """Resolve a company catalyst only after a qualifying Strategy B gap exists."""
    ticker = str(candidate.get("ticker") or "").upper()
    company = candidate.get("company") or candidate.get("name") or ticker
    gap_date = _event_datetime((assessment.get("gap") or {}).get("event_date"))
    retrieval = retrieval or {}
    events = list(retrieval.get("events") or [])
    # Retained news is supplemental evidence. It is still subjected to the
    # candidate identity and gap-date checks below.
    events.extend(section_events(ai_news_section))
    events.extend(section_events(biotech_news_section))
    aliases = strategy_b_identity_terms(candidate, retrieval)
    products = list(retrieval.get("products") or []) + list(retrieval.get("programs") or [])
    deduped, seen = [], set()
    for event in events:
        key = (event.get("source_link") or event.get("url"), event.get("headline"),
               event.get("published_at") or event.get("date"), event.get("ticker"))
        if key in seen:
            continue
        seen.add(key); deduped.append(event)

    qualifying, outside, identity_failed = [], [], []
    theme_events, analyst_events = [], []
    for event in deduped:
        category = strategy_b_event_category(event)
        if category == "THEME_EVIDENCE":
            theme_events.append(event); continue
        if category == "ANALYST_ACTION":
            analyst_events.append(event); continue
        if not category:
            continue
        validation = company_catalyst_validation(event, ticker, company, linked_names=aliases + products)
        event_date = _event_datetime(event.get("published_at") or event.get("date"))
        if not validation["valid"]:
            if event.get("identity_hint"):
                identity_failed.append((event, category, validation))
            continue
        if not gap_date or not event_date:
            outside.append((event, category, validation)); continue
        age = (gap_date - event_date).days
        if 0 <= age <= STRATEGY_B_CATALYST_LOOKBACK_DAYS:
            qualifying.append((event, category, validation))
        else:
            outside.append((event, category, validation))

    if qualifying:
        event, category, validation = max(qualifying, key=lambda item: (
            company_evidence_source_priority(item[0]),
            item[0].get("published_at") or item[0].get("date") or ""))
        return _strategy_b_result(
            "QUALIFYING",
            f"{validation['reason']} The {category.lower().replace('_', ' ')} event occurred within "
            f"{STRATEGY_B_CATALYST_LOOKBACK_DAYS} calendar days before/on the detected gap.",
            event, category, theme_events[0] if theme_events else None,
            analyst_events[0] if analyst_events else None)
    if identity_failed:
        event, category, validation = identity_failed[0]
        return _strategy_b_result("IDENTITY_FAILED", validation["reason"], event, category,
                                  theme_events[0] if theme_events else None,
                                  analyst_events[0] if analyst_events else None)
    if outside:
        event, category, _validation = max(outside, key=lambda item: (
            item[0].get("published_at") or item[0].get("date") or ""))
        return _strategy_b_result(
            "OUTSIDE_WINDOW",
            f"A company-specific {category.lower().replace('_', ' ')} event was found, but it did not occur "
            f"within {STRATEGY_B_CATALYST_LOOKBACK_DAYS} calendar days before/on the detected gap.",
            event, category, theme_events[0] if theme_events else None,
            analyst_events[0] if analyst_events else None)
    if retrieval.get("attempted") and retrieval.get("source_available") is False:
        return _strategy_b_result(
            "SOURCE_UNAVAILABLE", "Candidate-specific news/IR and SEC retrieval did not return an available source.",
            theme_event=theme_events[0] if theme_events else None,
            analyst_event=analyst_events[0] if analyst_events else None)
    reason = ("Only peer/sector Theme Evidence was found; it cannot satisfy the company catalyst gate."
              if theme_events else
              "Candidate-specific sources contained no qualifying company catalyst aligned with the detected gap.")
    return _strategy_b_result("NO_COMPANY_CATALYST", reason,
                              theme_event=theme_events[0] if theme_events else None,
                              analyst_event=analyst_events[0] if analyst_events else None)


def biotech_radar_catalyst(ticker, rows):
    matches = [row for row in rows or [] if row.get("ticker") == ticker and row.get("catalyst") and
               not str(row.get("catalyst")).startswith("Missing") and row.get("sources")]
    if not matches:
        return None
    row = max(matches, key=lambda item: item.get("opportunity_score") or -1)
    source = row["sources"][0]
    return {
        "credible": True, "description": row.get("catalyst"), "event_type": "Biotech Radar catalyst",
        "status": "COMPANY-SPECIFIC CATALYST",
        "validation_reason": "The source-backed Company → Program → Indication → Catalyst record directly identifies this company.",
        "company_specific_catalyst": row.get("catalyst"), "industry_theme_catalyst": None,
        "timing": row.get("expected_timing"), "source": source.get("title") or source.get("name"),
        "date": source.get("date") or source.get("publication_date"),
        "source_link": source.get("url"), "importance_score": None,
        "basis": "Dated, source-backed Company → Program → Indication → Catalyst record; its Radar score does not set the swing classification.",
    }


def ai_radar_catalyst(ticker, rows):
    matches = []
    theme_matches = []
    for row in rows or []:
        beneficiary = next((item for item in row.get("beneficiary_records", []) if item.get("ticker") == ticker), None)
        if not beneficiary:
            continue
        evidence_ids = set(beneficiary.get("evidence_ids", []))
        for event in row.get("confirming_evidence", []) + row.get("mixed_evidence", []):
            if event.get("event_id") in evidence_ids and event.get("source_link"):
                validation = company_catalyst_validation(event, ticker, beneficiary.get("company"))
                (matches if validation["valid"] else theme_matches).append((event, row.get("trend"), validation))
    if not matches:
        if not theme_matches:
            return None
        event, trend, validation = max(theme_matches, key=lambda item: (
            item[0].get("event_date") or "", item[0].get("news_importance_score") or 0))
        return {
            "credible": False, "description": THEME_ONLY_STATUS,
            "status": THEME_ONLY_STATUS, "validation_reason": validation["reason"],
            "company_specific_catalyst": None,
            "industry_theme_catalyst": event.get("new_information") or event.get("headline"),
            "event_type": event.get("event_type") or f"{trend} industry event",
            "timing": event.get("event_date"), "source": event.get("source"),
            "date": event.get("event_date"), "source_link": event.get("source_link"),
            "importance_score": event.get("news_importance_score"),
            "basis": validation["reason"],
        }
    event, trend, validation = max(matches, key=lambda item: (company_evidence_source_priority(item[0]),
                                                              item[0].get("event_date") or "",
                                                              item[0].get("news_importance_score") or 0))
    return {
        "credible": True, "description": event.get("new_information"),
        "status": validation["status"], "validation_reason": validation["reason"],
        "company_specific_catalyst": event.get("new_information") or event.get("headline"),
        "industry_theme_catalyst": None,
        "event_type": event.get("event_type") or f"{trend} industry event", "timing": event.get("event_date"),
        "source": event.get("source"), "date": event.get("event_date"),
        "source_link": event.get("source_link"), "importance_score": event.get("news_importance_score"),
        "basis": "Company-linked, source-backed AI Radar evidence; Radar strength does not set the swing classification.",
    }


def catalyst_check(ticker, domain, ai_radar, biotech_radar, ai_news, biotech_news, company=None):
    news = matching_news_catalyst(ticker, biotech_news if domain == "biotech" else ai_news, company)
    if news:
        return news
    return (biotech_radar_catalyst(ticker, biotech_radar) if domain == "biotech"
            else ai_radar_catalyst(ticker, ai_radar)) or {
                "credible": False, "description": "Missing: no source-backed catalyst is connected.",
                "status": THEME_ONLY_STATUS,
                "validation_reason": f"No source directly identifies {company or ticker} or a clearly linked company event.",
                "company_specific_catalyst": None, "industry_theme_catalyst": None,
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
        "summary": (f"{company} passes the complete technical Action screen as {state}."
                    if technical.get("qualified_step_1") else
                    f"{company} is ranked as a {state} WATCH setup; pattern recognition alone does not qualify an entry."),
        "why_chart_selected": (f"A major decline is {decline_text}; "
                               f"the 20-session range is {technical.get('bottom_range_20d_pct')}%."),
        "bottom_reversal_stage": (f"The setup is classified {state}; price versus MA20/MA50 is "
                                  f"{technical.get('price_vs_ma20_pct')}% / {technical.get('price_vs_ma50_pct')}%."),
        "why_still_early": f"{early}. The extension screen has {'failed; do not chase' if technical.get('extended') else 'not identified an extended setup'}.",
        "catalyst_support": f"{catalyst.get('description')} Timing: {catalyst.get('timing') or 'Missing'}.",
        "invalidation": invalidation,
    }


def swing_action(technical, catalyst, transition):
    """Action is downstream of pattern, stage, confirmation, risk, and reward/risk."""
    state = (transition or {}).get("current_stage") or (technical or {}).get("state")
    if (technical or {}).get("extended") or state == "Extended":
        return "DO NOT CHASE"
    if state in ("Falling", "Bottoming", "Failed Reversal / Technical Deterioration"):
        return "WATCH"
    if not (catalyst or {}).get("credible"):
        return WAIT_FOR_CATALYST_ACTION
    if (technical or {}).get("qualified_step_1") is not True:
        return "WATCH"
    if state == "Entry Zone":
        return "BUY"
    if state == "Early Reversal" and (transition or {}).get("fresh_favorable_transition"):
        return "SCALE IN"
    return "WATCH"


def _independent_catalyst(ticker, company, ai_news_section, biotech_news_section):
    """Use source-backed news only; no Radar rows or scores are consulted."""
    matches = [matching_news_catalyst(ticker, section, company)
               for section in (biotech_news_section, ai_news_section)]
    matches = [item for item in matches if item]
    if matches:
        return max(matches, key=lambda item: (item.get("importance_score") or 0,
                                              item.get("date") or ""))
    return {
        "credible": False, "description": "Missing / Not Yet Confirmed",
        "status": THEME_ONLY_STATUS,
        "validation_reason": f"No source directly identifies {company or ticker} or a linked company event.",
        "company_specific_catalyst": None, "industry_theme_catalyst": None,
        "event_type": None, "timing": None, "source": None, "date": None,
        "source_link": None, "importance_score": None,
        "basis": "No Radar evidence is used; only directly matched source-backed news can verify a catalyst.",
    }


def _relative_strength(snapshot, benchmark):
    values = ((snapshot.get("relative_strength") or {}).get(benchmark) or {})
    usable = [values.get(key) for key in ("one_month", "three_month", "six_month")
              if _number(values.get(key)) is not None]
    return round(sum(usable) / len(usable), 2) if usable else None


def _extension(snapshot, pivot=None):
    price = _number(snapshot.get("current_price"))
    mas = snapshot.get("moving_averages") or {}
    ma20, ma50 = _number(mas.get("ma20")), _number(mas.get("ma50"))
    one_month = _number((snapshot.get("returns") or {}).get("one_month"))
    return bool(
        (price and ma20 and price > ma20 * 1.12) or
        (price and ma50 and price > ma50 * 1.18) or
        (price and pivot and price > pivot * 1.05) or
        (one_month is not None and one_month > 30))


def _score(values):
    usable = [value for value in values if _number(value) is not None]
    return round(sum(usable) / len(usable)) if usable else None


def _swing_position_metrics(snapshot):
    """Return 52-week position context; these values are not BUY NOW gates."""
    inputs = snapshot.get("entry_inputs") or {}
    price = _number(snapshot.get("current_price"))
    low = _number(inputs.get("fifty_two_week_low"))
    high = _number(inputs.get("fifty_two_week_high"))
    available = bool(price is not None and low is not None and high is not None and
                     low > 0 and high > 0)
    if not available:
        return {
            "available": False,
            "pct_above_52_week_low": None, "pct_below_52_week_high": None,
            "fifty_two_week_low": low, "fifty_two_week_high": high,
        }
    pct_above_low = (price - low) / low * 100
    pct_below_high = (high - price) / high * 100
    return {
        "available": True,
        "pct_above_52_week_low": round(pct_above_low, 2),
        "pct_below_52_week_high": round(pct_below_high, 2),
        "fifty_two_week_low": low, "fifty_two_week_high": high,
    }


def _swing_mountain_position(snapshot, support, extended=False):
    """Locate price within the current advance, independent of 52-week position."""
    price = _number(snapshot.get("current_price"))
    distance = ((price - support) / support * 100
                if price is not None and support is not None and support > 0 else None)
    one_month = _number((snapshot.get("returns") or {}).get("one_month"))
    if extended or (distance is not None and distance > 12) or (one_month is not None and one_month > 25):
        return "Upper"
    if distance is not None and distance <= 5:
        return "Lower"
    return "Middle"


def _swing_entry_context(assessment, snapshot):
    """Map each strategy to its current support/pivot execution levels."""
    price = _number(snapshot.get("current_price"))
    mas = snapshot.get("moving_averages") or {}
    inputs = snapshot.get("entry_inputs") or {}
    returns = snapshot.get("returns") or {}
    macd = snapshot.get("macd") or {}
    strategy = assessment.get("strategy")
    signals = assessment.get("signals") or {}
    stage = assessment.get("stage")
    support_candidates = [_number(assessment.get("support"))]
    if strategy in ("B", "C"):
        support_candidates.extend([_number(mas.get("ma20")), _number(mas.get("ma50"))])
    pivot = _number(assessment.get("major_resistance") or assessment.get("pivot"))
    usable_supports = [value for value in support_candidates
                       if value is not None and value > 0 and price is not None and value <= price]
    support = max(usable_supports, default=None)

    def distance_from(level):
        return (round((price - level) / level * 100, 2)
                if price is not None and level is not None and level > 0 else None)

    support_distance = distance_from(support)
    pivot_distance = distance_from(pivot)
    # Five percent is the engine's existing pivot-extension boundary. Reuse it
    # here rather than adding a new strategy or ranking threshold.
    near_support = bool(support_distance is not None and 0 <= support_distance <= 5)
    near_pivot = bool(pivot_distance is not None and 0 <= pivot_distance <= 5)
    breakout_age = assessment.get("breakout_age_sessions")
    fresh_breakout = bool(assessment.get("candidate_qualified") and
                          signals.get("fresh_breakout") and near_pivot and
                          not assessment.get("extended"))
    support_reversal = bool(assessment.get("candidate_qualified") and
                            signals.get("support_reversal") and near_support and
                            not assessment.get("extended"))
    if strategy == "A":
        fresh_breakout = bool(fresh_breakout and signals.get("recent_breakout"))
        # Entry 2 is specifically the first retest of the former Stage 1 pivot.
        retest_distance = pivot_distance
        support_reversal = bool(
            signals.get("first_retest") and retest_distance is not None and
            -2 <= retest_distance <= 5 and not assessment.get("extended"))
        if support_reversal:
            support = pivot
            support_distance = pivot_distance
            near_support = True
    entry_qualified = support_reversal or fresh_breakout
    if fresh_breakout:
        level = pivot
        level_kind = {"A": "Stage 1 base pivot", "B": "Stage 2 continuation pivot",
                      "C": "re-base pivot"}.get(strategy, "pivot")
        entry_stage = {"A": "Entry 1 — Initial Breakout",
                       "B": "Trend Continuation Breakout",
                       "C": "Re-Base Breakout"}.get(strategy, "Fresh Breakout")
    elif support_reversal:
        level = support
        level_kind = {"A": "Stage 1 breakout support", "B": "rising Stage 2 support",
                      "C": "re-base support"}.get(strategy, "support")
        entry_stage = {"A": "Entry 2 — First Pullback/Retest",
                       "B": "Pullback / Tight-Consolidation Renewal",
                       "C": "Re-Base Support Retest"}.get(strategy, "Fresh Reversal Near Support")
    elif pivot_distance is not None and pivot_distance >= 0:
        level, level_kind = pivot, "current pivot"
        entry_stage = "Breakout Stale / Unconfirmed"
    else:
        level, level_kind = support, "current support"
        entry_stage = "Waiting for Reversal"
    distance = distance_from(level)
    materially_extended = bool(assessment.get("extended") or
                               (distance is not None and distance > 5))
    limit_price = round(level * 1.002, 2) if entry_qualified and level is not None else None
    reason = (f"Fresh {breakout_age}-session volume-confirmed breakout at {level_kind}"
              if fresh_breakout else
              f"Fresh confirmed reversal near {level_kind}" if support_reversal else
              f"Extended above {level_kind}" if materially_extended else
              "Existing entry confirmation is incomplete")
    return {
        "level": level, "level_kind": level_kind, "distance_pct": distance,
        "base_support": support, "base_pivot": pivot,
        "support_distance_pct": support_distance, "pivot_distance_pct": pivot_distance,
        "near_level": near_support or near_pivot, "support_reversal": support_reversal,
        "fresh_breakout": fresh_breakout, "entry_stage": entry_stage,
        "materially_extended": materially_extended,
        "entry_qualified": entry_qualified, "limit_price": limit_price,
        "qualification_reason": reason, "breakout_age_sessions": breakout_age,
    }


def _swing_execution_action(company_gate_passed, assessment, snapshot, entry_context):
    """Apply support/breakout execution semantics without changing setup scores."""
    if entry_context.get("materially_extended"):
        distance = entry_context.get("distance_pct")
        kind = entry_context.get("level_kind") or "support/pivot"
        detail = f"+{distance:.1f}% above {kind}" if distance is not None else "too far from a valid entry level"
        return f"DO NOT CHASE — Extended: {detail}"
    if not company_gate_passed or not entry_context.get("entry_qualified"):
        return "WAIT"
    current = _number(snapshot.get("current_price"))
    limit_price = _number(entry_context.get("limit_price"))
    if current is None or limit_price is None:
        return "WAIT — actionable entry price unavailable"
    if limit_price < current * .99:
        return f"SET LIMIT ${limit_price:.2f} — wait for pullback"
    return "BUY NOW"


def _swing_strategy_entry_classification(assessment, entry_context):
    """Classify strategy and entry independently without changing qualification."""
    if assessment.get("strategy") == "A":
        strategy = "Strategy A — Stage 1 → Stage 2 Launch"
        if entry_context.get("fresh_breakout"):
            entry = "Entry 1 — Initial Breakout"
            cycle_stage = "Stage 1 → Stage 2"
        elif (entry_context.get("support_reversal") and
              (assessment.get("signals") or {}).get("recent_breakout_attempt")):
            entry = "Entry 2 — First Pullback/Retest"
            cycle_stage = "Stage 2 — First Retest"
        elif assessment.get("stage") == "Extended":
            entry = "No Entry — Extended"
            cycle_stage = "Stage 2 / Stage 3 Watch"
        else:
            entry = "Monitoring — Stage 1 Base"
            cycle_stage = "Stage 1"
    elif assessment.get("strategy") == "B":
        strategy = "Strategy B — Stage 2 Trend Continuation"
        if entry_context.get("fresh_breakout"):
            entry = "Continuation Pivot Breakout"
        elif entry_context.get("support_reversal"):
            entry = "Pullback / Tight-Consolidation Renewal"
        else:
            entry = "Monitoring — Stage 2 Continuation"
        cycle_stage = "Healthy Stage 2 Advance"
    else:
        strategy = "Strategy C — Re-Base / Re-Acceleration"
        if entry_context.get("fresh_breakout"):
            entry = "Fresh Re-Base Breakout"
        elif entry_context.get("support_reversal"):
            entry = "Re-Base Pullback/Retest"
        else:
            entry = "Monitoring — Re-Base"
        cycle_stage = "Post-Advance Re-Base"
    return {"strategy": strategy, "entry": entry, "cycle_stage": cycle_stage}


def assess_long_base_breakout(snapshot, biotech=False):
    """Assess a genuine Stage 1 base for launch or first breakout retest."""
    inputs = snapshot.get("entry_inputs") or {}
    mas = snapshot.get("moving_averages") or {}
    returns = snapshot.get("returns") or {}
    macd = snapshot.get("macd") or {}
    price = _number(snapshot.get("current_price"))
    pivot = _number(inputs.get("resistance_level"))
    base_sessions, base_range = inputs.get("base_duration_sessions"), _number(inputs.get("base_range_pct"))
    tight_range = _number(inputs.get("tight_range_20d_pct"))
    contraction = _number(inputs.get("volume_contraction_ratio"))
    accumulation = _number(inputs.get("up_down_volume_ratio_20d"))
    breakout_volume = _number(inputs.get("breakout_volume_ratio"))
    breakout_age = inputs.get("breakout_age_sessions")
    proximity = _number(inputs.get("breakout_proximity_pct"))
    ma20, ma50 = _number(mas.get("ma20")), _number(mas.get("ma50"))
    ma20_slope, ma50_slope = (_number(inputs.get("ma20_slope_10d_pct")),
                              _number(inputs.get("ma50_slope_20d_pct")))
    relative = _relative_strength(snapshot, "xbi" if biotech else "sp500")
    recent_low = _number(inputs.get("recent_low_63d"))
    base_low = _number(inputs.get("base_low"))
    distance_from_bottom = _number(inputs.get("distance_from_recent_low_pct"))
    drawdown_from_high = _number(inputs.get("drawdown_from_fifty_two_week_high_pct"))
    range_transitions = _number(inputs.get("range_zone_transitions_63d"))
    short_term_high = _number(inputs.get("short_term_high_10d"))
    rsi = _number(snapshot.get("rsi_14"))
    current_volume = _number(snapshot.get("volume_vs_20d_average"))
    daily_return = _number(returns.get("daily"))
    histogram = _number(macd.get("histogram"))
    mature_base = base_sessions in (42, 63) and base_range is not None and base_range <= 25
    contracted = bool((tight_range is not None and tight_range <= 15) or
                      (contraction is not None and contraction <= .95))
    distribution_warning = bool((accumulation is not None and accumulation < .8) or
                                (current_volume is not None and current_volume >= 1.5 and
                                 daily_return is not None and daily_return < 0))
    volume_structure = bool(((contraction is not None and contraction <= 1) or
                             (accumulation is not None and accumulation >= 1)) and
                            not distribution_warning)
    higher_low = inputs.get("higher_low_confirmed") is True
    support_holding = bool((higher_low or (range_transitions is not None and range_transitions >= 2)) and
                           distance_from_bottom is not None and distance_from_bottom <= 25)
    selling_pressure_declining = bool(contracted and volume_structure)
    momentum_improving = bool(
        macd.get("crossover") == "bullish" or macd.get("improving") is True or
        (histogram is not None and histogram > 0))
    momentum_usable = rsi is None or 35 <= rsi <= 68
    ma_turning = bool((ma20_slope is None or ma20_slope >= 0) and
                      (ma50_slope is None or ma50_slope >= -1))
    above_or_near_ma20 = bool(price and ma20 and price >= ma20 * .97)
    short_reclaim = inputs.get("short_term_high_reclaimed") is True
    right_side = bool(higher_low and short_reclaim and above_or_near_ma20 and
                      momentum_improving and ma_turning)
    pivot_cleared = bool(proximity is not None and 0 <= proximity <= 3 and
                         short_reclaim)
    volume_confirmed = breakout_volume is not None and breakout_volume >= 1.2
    rs_confirmed = relative is not None and relative > 0
    extended = _extension(snapshot, pivot)
    persistent_downtrend = bool(not higher_low and not momentum_improving and
                                price and ma20 and price < ma20 and
                                ma20_slope is not None and ma20_slope < -1 and
                                ma50_slope is not None and ma50_slope < -1)
    breakout = bool(pivot_cleared and volume_confirmed)
    recent_breakout = bool(inputs.get("recent_breakout_attempt") is True and
                           isinstance(breakout_age, int) and 0 <= breakout_age <= 4)
    breakout_ready = bool(not breakout and proximity is not None and -5 <= proximity < 0 and
                          higher_low and right_side)
    early_right_side = bool(right_side and (proximity is None or proximity < -5))
    early_reversal = bool(not early_right_side and higher_low and momentum_improving and
                          momentum_usable and above_or_near_ma20 and ma_turning)
    bottoming = bool(mature_base and support_holding and selling_pressure_declining)
    if inputs.get("failed_breakout") or persistent_downtrend:
        stage = "Falling"
    elif extended:
        stage = "Extended"
    elif breakout:
        stage = "Breakout"
    elif breakout_ready:
        stage = "Breakout Ready"
    elif early_right_side:
        stage = "Early Right-Side"
    elif early_reversal:
        stage = "Early Reversal"
    elif bottoming:
        stage = "Bottoming"
    else:
        stage = "Falling"
    candidate_qualified = bool(mature_base and support_holding and selling_pressure_declining and
                               not inputs.get("failed_breakout") and not persistent_downtrend)
    invalidation = _number(inputs.get("invalidation_level"))
    support_candidates = [value for value in (recent_low, base_low, ma50, invalidation)
                          if value is not None and price is not None and value < price]
    support = max(support_candidates) if support_candidates else invalidation
    entry_reference = short_term_high if short_reclaim and short_term_high else ma20 or support
    risk_to_invalidation = (entry_reference - invalidation
                            if entry_reference and invalidation and entry_reference > invalidation else None)
    reward_to_resistance = (pivot - entry_reference
                            if pivot and entry_reference and pivot > entry_reference else None)
    reward_risk = (round(reward_to_resistance / risk_to_invalidation, 2)
                   if risk_to_invalidation and reward_to_resistance is not None else None)
    one_day_bounce = bool(daily_return is not None and daily_return >= 8 and
                          not short_reclaim and macd.get("crossover") != "bullish")
    demand_confirmation = bool((accumulation is not None and accumulation >= 1.05) or
                               (current_volume is not None and current_volume >= 1 and
                                daily_return is not None and daily_return > 0))
    controlled_pullback = bool(contraction is not None and contraction <= 1 and
                               higher_low and not inputs.get("failed_breakout"))
    breakout_support_reclaimed = bool(pivot is not None and price is not None and
                                      pivot <= price <= pivot * 1.05 and short_reclaim)
    renewed_price_volume = bool(daily_return is not None and daily_return > 0 and
                                current_volume is not None and current_volume >= 1 and
                                momentum_improving)
    first_retest = bool(
        inputs.get("recent_breakout_attempt") is True and not breakout and
        controlled_pullback and breakout_support_reclaimed and renewed_price_volume and
        not one_day_bounce)
    fresh_initial_breakout = bool(breakout and recent_breakout and not extended)
    actionable = bool(candidate_qualified and (fresh_initial_breakout or first_retest) and not extended)
    limit_buy = round(entry_reference * 1.002, 2) if actionable and entry_reference else None
    stage_score = {"Early Reversal": 100, "Early Right-Side": 98, "Bottoming": 86,
                   "Breakout Ready": 72, "Breakout": 55, "Falling": 15,
                   "Extended": 5}.get(stage, 20)
    pattern_score = _score([100 if mature_base else 25, 95 if contracted else 40,
                            95 if support_holding else 30])
    trend_score = _score([stage_score, 95 if higher_low else 35,
                          90 if ma_turning else 30])
    volume_score = _score([
        90 if volume_structure else 30,
        95 if accumulation is not None and accumulation >= 1.2 else
        75 if accumulation is not None and accumulation >= 1 else
        40 if accumulation is not None else None,
    ])
    candidate_score = _score([pattern_score, trend_score, volume_score])
    decision_score = _score([stage_score,
                             100 if demand_confirmation else 35,
                             95 if momentum_improving else 30,
                             90 if rs_confirmed else 55 if relative is not None else None,
                             10 if extended else 90])
    confirmation_score = _score([
        95 if support_holding else 30,
        95 if higher_low else 35,
        95 if momentum_improving else 30,
        95 if demand_confirmation else 35,
        95 if short_reclaim else 50,
    ])
    rank_parts = [(pattern_score, .25), (stage_score, .35),
                  (volume_score, .20), (confirmation_score, .20)]
    available_rank_parts = [(value, weight) for value, weight in rank_parts if value is not None]
    score = (round(sum(value * weight for value, weight in available_rank_parts) /
                   sum(weight for _, weight in available_rank_parts))
             if available_rank_parts else candidate_score)
    if score is not None:
        stage_adjustment = {"Breakout Ready": -3, "Breakout": -8,
                            "Falling": -20, "Extended": -35}.get(stage, 0)
        score = max(0, min(100, score + stage_adjustment))
    failures = [label for label, passed in (
        ("long/mature base", mature_base), ("volatility contraction", contracted),
        ("support hold/tightening", support_holding), ("higher low", higher_low),
        ("momentum improving", momentum_improving), ("short-term reclaim", short_reclaim),
        ("moving averages flattening/turning up", ma_turning),
        ("constructive base volume", volume_structure),
        ("demand confirmation", demand_confirmation),
        ("favorable reward/risk", reward_risk is not None and reward_risk >= 1.5),
        ("not one-day bounce", not one_day_bounce),
        ("not failed", not inputs.get("failed_breakout") and not persistent_downtrend),
        ("not Extended", not extended)) if not passed]
    patterns = []
    if mature_base:
        patterns.append("Long Base")
    if mature_base and contracted and ma20_slope is not None and ma20_slope >= 0 and ma50_slope is not None and ma50_slope <= 1:
        patterns.append("Rounded Bottom")
    if range_transitions is not None and range_transitions >= 2 and higher_low and support_holding:
        patterns.append("Double Bottom")
    if higher_low and momentum_improving:
        patterns.append("Higher-Low Reversal")
    if tight_range is not None and tight_range <= 12 and contracted:
        patterns.append("Tight Base")
    if stage == "Early Right-Side":
        patterns.append("Early Right-Side")
    pattern_label = " / ".join(dict.fromkeys(patterns)) or "Base evidence incomplete"
    zone_low = support or invalidation
    zone_high = ma20 if ma20 and price and ma20 <= price * 1.03 else entry_reference
    support_entry_zone = (f"{round(zone_low, 2)}–{round(zone_high, 2)}"
                          if zone_low and zone_high and zone_high >= zone_low else
                          f"Support {round(zone_low, 2)}" if zone_low else "N/A")
    confirmation = (f"Higher low {'yes' if higher_low else 'no'} · short-term reclaim "
                    f"{'yes' if short_reclaim else 'no'} · momentum {'improving' if momentum_improving else 'not confirmed'} "
                    f"· demand {'confirmed' if demand_confirmation else 'not confirmed'}")
    return {
        "strategy": "A", "strategy_name": "Stage 1 → Stage 2 Launch",
        "stage": stage, "technical_pattern": pattern_label,
        "support_entry_zone": support_entry_zone, "confirmation": confirmation,
        "pattern": (f"{base_sessions}-session base; {base_range}% range; major resistance {pivot}"
                    if mature_base else "No qualifying multi-week/month base"),
        "candidate_qualified": candidate_qualified, "actionable": actionable,
        "candidate_score": candidate_score, "decision_score": decision_score,
        "score": score, "limit_buy": limit_buy,
        "pivot": entry_reference, "major_resistance": pivot, "support": support,
        "breakout_age_sessions": breakout_age,
        "invalidation": invalidation, "reward_risk": reward_risk,
        "extended": extended, "failed_gates": failures,
        "signals": {"mature_base": mature_base, "contracted": contracted,
                    "higher_low": higher_low, "right_side": right_side,
                    "support_holding": support_holding, "momentum_improving": momentum_improving,
                    "ma_turning": ma_turning, "short_term_reclaim": short_reclaim,
                    "demand_confirmation": demand_confirmation, "one_day_bounce": one_day_bounce,
                    "volume_structure": volume_structure, "accumulation": accumulation,
                    "pivot_cleared": pivot_cleared, "volume_confirmed": volume_confirmed,
                    "recent_breakout": recent_breakout,
                    "fresh_breakout": fresh_initial_breakout,
                    "first_retest": first_retest,
                    "support_reversal": first_retest,
                    "controlled_pullback": controlled_pullback,
                    "breakout_support_reclaimed": breakout_support_reclaimed,
                    "renewed_price_volume": renewed_price_volume,
                    "recent_breakout_attempt": inputs.get("recent_breakout_attempt") is True,
                    "relative_strength_confirmed": rs_confirmed, "relative_strength": relative},
        "pattern_summary": pattern_label,
        "trend_summary": (f"{stage} · higher low {'confirmed' if higher_low else 'missing'} · "
                          f"MA turn {'confirmed' if ma_turning else 'missing'}"),
        "volume_summary": (f"Base volume {contraction if contraction is not None else 'N/A'}x prior · "
                           f"up/down volume {accumulation if accumulation is not None else 'N/A'}x · "
                           f"current RVOL {breakout_volume if breakout_volume is not None else 'N/A'}x"),
    }


def assess_gap_continuation(snapshot, biotech=False):
    inputs = snapshot.get("entry_inputs") or {}
    gap = inputs.get("gap_up_continuation") or {}
    price = _number(snapshot.get("current_price"))
    pivot = _number(gap.get("continuation_pivot"))
    current_volume = _number(snapshot.get("volume_vs_20d_average"))
    days = gap.get("days_since_gap")
    major_gap = gap.get("detected") is True and _number(gap.get("gap_pct")) is not None
    abnormal_volume = bool(_number(gap.get("gap_volume_ratio")) is not None and
                           gap["gap_volume_ratio"] >= 1.8)
    event_quality = bool(abnormal_volume and
                         _number(gap.get("gap_close_position")) is not None and
                         gap["gap_close_position"] >= .65)
    seasoned = isinstance(days, int) and 2 <= days <= 15
    held = gap.get("held_gap_support") is True
    tight = (_number(gap.get("post_gap_consolidation_range_pct")) is not None and
             gap["post_gap_consolidation_range_pct"] <= 12)
    continuation = bool(price and pivot and pivot <= price <= pivot * 1.035 and
                        current_volume is not None and current_volume >= 1.15 and
                        inputs.get("short_term_high_reclaimed") is True)
    ma20 = _number((snapshot.get("moving_averages") or {}).get("ma20"))
    one_month = _number((snapshot.get("returns") or {}).get("one_month"))
    # A valid gap continuation is naturally far above the pre-gap MA50.  Chase
    # risk is therefore measured from the new continuation pivot and MA20,
    # rather than reusing the long-base MA50 extension rule.
    extended = bool((price and pivot and price > pivot * 1.05) or
                    (price and ma20 and price > ma20 * 1.12) or
                    (one_month is not None and one_month > 40))
    candidate_qualified = bool(major_gap and abnormal_volume)
    actionable = bool(candidate_qualified and event_quality and seasoned and held and tight and
                      continuation and not inputs.get("failed_breakout") and not extended)
    limit_buy = round(pivot * 1.002, 2) if actionable and pivot else None
    invalidation = _number(gap.get("gap_low"))
    risk_to_invalidation = (pivot - invalidation if pivot and invalidation and pivot > invalidation else None)
    reward_risk = (round((pivot * .30) / risk_to_invalidation, 2)
                   if risk_to_invalidation else None)
    pattern_score = _score([100 if major_gap else 20,
                            100 if event_quality else 60 if abnormal_volume else 25])
    volume_score = (100 if _number(gap.get("gap_volume_ratio")) is not None and
                    gap["gap_volume_ratio"] >= 3 else 90 if abnormal_volume else 25)
    trend_score = _score([95 if held else 30, 90 if tight else 45,
                          90 if seasoned else 55 if days == 0 else 30])
    candidate_score = _score([pattern_score, volume_score])
    decision_score = _score([trend_score, 100 if continuation else 30, 10 if extended else 90])
    score = (round(candidate_score * .7 + decision_score * .3)
             if candidate_score is not None and decision_score is not None else candidate_score)
    failures = [label for label, passed in (
        ("major >=8% catalyst gap", major_gap), ("strong event volume/close", event_quality),
        ("at least two follow-through sessions", seasoned), ("gap midpoint/low support held", held),
        ("tight post-gap consolidation", tight), ("new continuation pivot/volume confirmation", continuation),
        ("not failed", not inputs.get("failed_breakout")), ("not Extended", not extended)) if not passed]
    return {
        "strategy": "B", "strategy_name": "Re-Acceleration / Continuation",
        "pattern": (f"{gap.get('gap_pct')}% gap on {gap.get('event_date')}; "
                    f"{gap.get('days_since_gap')} sessions; continuation pivot {pivot}"
                    if major_gap else "No qualifying >=8% gap in the last 20 sessions"),
        "candidate_qualified": candidate_qualified, "actionable": actionable,
        "candidate_score": candidate_score, "decision_score": decision_score,
        "score": score, "limit_buy": limit_buy,
        "pivot": pivot, "invalidation": invalidation, "reward_risk": reward_risk,
        "extended": extended, "failed_gates": failures, "gap": gap,
        "pattern_summary": (f"{gap.get('gap_pct')}% gap on {gap.get('event_date')}" if major_gap
                            else "No qualifying recent gap"),
        "trend_summary": ("Day 1 gap under evaluation" if days == 0 else
                          f"Day {days} · gap support {'held' if held else 'failed'} · "
                          f"post-gap range {gap.get('post_gap_consolidation_range_pct')}%"),
        "volume_summary": (f"Event volume {gap.get('gap_volume_ratio')}x prior average · "
                           f"event close position {gap.get('gap_close_position')}"),
    }


def _renewal_signals(snapshot):
    inputs = snapshot.get("entry_inputs") or {}
    returns = snapshot.get("returns") or {}
    macd = snapshot.get("macd") or {}
    histogram = _number(macd.get("histogram"))
    current_volume = _number(snapshot.get("volume_vs_20d_average"))
    daily_return = _number(returns.get("daily"))
    momentum = bool(macd.get("crossover") == "bullish" or macd.get("improving") is True or
                    (histogram is not None and histogram > 0))
    demand = bool(current_volume is not None and current_volume >= 1 and
                  daily_return is not None and daily_return > 0)
    volume_confirmed = bool(
        (_number(inputs.get("breakout_volume_ratio")) is not None and
         _number(inputs.get("breakout_volume_ratio")) >= 1.2) or
        (current_volume is not None and current_volume >= 1.15))
    return momentum, demand, volume_confirmed


def assess_stage2_continuation(snapshot, biotech=False):
    """Assess healthy established Stage 2 winners; a long Stage 1 base is not required."""
    inputs = snapshot.get("entry_inputs") or {}
    mas = snapshot.get("moving_averages") or {}
    returns = snapshot.get("returns") or {}
    price = _number(snapshot.get("current_price"))
    ma20, ma50, ma200 = (_number(mas.get("ma20")), _number(mas.get("ma50")),
                         _number(mas.get("ma200")))
    ma20_slope = _number(inputs.get("ma20_slope_10d_pct"))
    ma50_slope = _number(inputs.get("ma50_slope_20d_pct"))
    tight_range = _number(inputs.get("tight_range_20d_pct"))
    pivot = _number(inputs.get("short_term_high_10d") or inputs.get("resistance_level"))
    invalidation = _number(inputs.get("invalidation_level") or inputs.get("recent_low_20d"))
    supports = [value for value in (ma20, ma50, _number(inputs.get("recent_low_20d")))
                if value is not None and price is not None and value <= price]
    support = max(supports, default=invalidation)
    support_distance = ((price - support) / support * 100
                        if price is not None and support is not None and support > 0 else None)
    six_month = _number(returns.get("six_month"))
    three_month = _number(returns.get("three_month"))
    established_uptrend = bool(price and ma50 and ma200 and price > ma50 > ma200 and
                               (ma50_slope is None or ma50_slope > 0) and
                               (six_month is None or six_month > 0))
    rising_support = bool(support is not None and
                          (ma20_slope is None or ma20_slope >= 0) and
                          (ma50_slope is None or ma50_slope > 0))
    healthy_pullback = bool(support_distance is not None and 0 <= support_distance <= 8 and
                            (tight_range is None or tight_range <= 15))
    higher_low = inputs.get("higher_low_confirmed") is True
    momentum, demand, volume_confirmed = _renewal_signals(snapshot)
    reclaim = inputs.get("short_term_high_reclaimed") is True
    proximity = ((price - pivot) / pivot * 100
                 if price is not None and pivot is not None and pivot > 0 else None)
    fresh_breakout = bool(reclaim and volume_confirmed and proximity is not None and
                          0 <= proximity <= 5 and not inputs.get("failed_breakout"))
    support_reversal = bool(healthy_pullback and higher_low and momentum and demand and reclaim)
    extended = _extension(snapshot, pivot)
    mountain = _swing_mountain_position(snapshot, support, extended)
    candidate_qualified = bool(established_uptrend and rising_support and
                               (healthy_pullback or (tight_range is not None and tight_range <= 15)) and
                               not inputs.get("failed_breakout"))
    actionable = bool(candidate_qualified and (support_reversal or fresh_breakout) and
                      mountain != "Upper" and not extended)
    pattern_score = _score([100 if established_uptrend else 25,
                            90 if healthy_pullback else 55,
                            90 if tight_range is not None and tight_range <= 12 else 55])
    trend_score = _score([95 if rising_support else 30, 95 if higher_low else 55,
                          90 if three_month is not None and three_month > 0 else 55])
    volume_score = _score([95 if demand else 45, 95 if volume_confirmed else 50])
    decision_score = _score([100 if support_reversal or fresh_breakout else 40,
                             95 if momentum else 35, 10 if mountain == "Upper" else 90])
    score = _score([pattern_score, trend_score, volume_score, decision_score])
    failures = [label for label, passed in (
        ("established Stage 2 uptrend", established_uptrend),
        ("rising support", rising_support), ("healthy pullback/tight consolidation", healthy_pullback),
        ("higher low", higher_low), ("momentum improving", momentum),
        ("short-term reclaim", reclaim), ("demand confirmation", demand),
        ("volume/RVOL confirmation", volume_confirmed),
        ("not failed", not inputs.get("failed_breakout")),
        ("not Extended", not extended and mountain != "Upper")) if not passed]
    return {
        "strategy": "B", "strategy_name": "Stage 2 Trend Continuation",
        "stage": f"Stage 2 — {mountain}", "mountain_position": mountain,
        "candidate_qualified": candidate_qualified, "actionable": actionable,
        "candidate_score": _score([pattern_score, trend_score, volume_score]),
        "decision_score": decision_score, "score": score,
        "pivot": pivot, "major_resistance": pivot, "support": support,
        "invalidation": invalidation, "reward_risk": None, "extended": extended,
        "breakout_age_sessions": inputs.get("breakout_age_sessions"),
        "failed_gates": failures,
        "signals": {"fresh_breakout": fresh_breakout, "support_reversal": support_reversal,
                    "volume_confirmed": volume_confirmed, "higher_low": higher_low,
                    "momentum_improving": momentum, "demand_confirmation": demand},
        "pattern": "Established Stage 2 uptrend with pullback/tight-consolidation continuation setup",
        "pattern_summary": "Stage 2 Pullback" if healthy_pullback else "Stage 2 Tight Consolidation",
        "technical_pattern": "Healthy Stage 2 Trend Continuation",
        "support_entry_zone": f"Rising support {round(support, 2)}" if support else "N/A",
        "confirmation": (f"Higher low {'yes' if higher_low else 'no'} · momentum "
                         f"{'improving' if momentum else 'unconfirmed'} · demand "
                         f"{'confirmed' if demand else 'unconfirmed'}"),
        "trend_summary": f"Established Stage 2 · Mountain {mountain}",
        "volume_summary": f"Current RVOL {snapshot.get('volume_vs_20d_average', 'N/A')}x",
    }


def assess_rebase_reacceleration(snapshot, biotech=False):
    """Assess a shorter post-advance base and its support retest or new breakout."""
    inputs = snapshot.get("entry_inputs") or {}
    mas = snapshot.get("moving_averages") or {}
    returns = snapshot.get("returns") or {}
    price = _number(snapshot.get("current_price"))
    ma20, ma50, ma200 = (_number(mas.get("ma20")), _number(mas.get("ma50")),
                         _number(mas.get("ma200")))
    tight_range = _number(inputs.get("tight_range_20d_pct"))
    contraction = _number(inputs.get("volume_contraction_ratio"))
    pivot = _number(inputs.get("short_term_high_10d") or inputs.get("resistance_level"))
    recent_low = _number(inputs.get("recent_low_20d") or inputs.get("recent_low_63d"))
    supports = [value for value in (recent_low, ma20, ma50)
                if value is not None and price is not None and value <= price]
    support = max(supports, default=_number(inputs.get("invalidation_level")))
    support_distance = ((price - support) / support * 100
                        if price is not None and support is not None and support > 0 else None)
    prior_advance = bool(((_number(returns.get("three_month")) or 0) > 8 or
                          (_number(returns.get("six_month")) or 0) > 15) and
                         (ma200 is None or (price is not None and price > ma200)))
    shorter_base = bool(tight_range is not None and tight_range <= 15 and
                        (contraction is None or contraction <= 1.05))
    higher_low = inputs.get("higher_low_confirmed") is True
    momentum, demand, volume_confirmed = _renewal_signals(snapshot)
    reclaim = inputs.get("short_term_high_reclaimed") is True
    proximity = ((price - pivot) / pivot * 100
                 if price is not None and pivot is not None and pivot > 0 else None)
    fresh_breakout = bool(shorter_base and reclaim and volume_confirmed and
                          proximity is not None and 0 <= proximity <= 5 and
                          not inputs.get("failed_breakout"))
    support_reversal = bool(shorter_base and support_distance is not None and
                            0 <= support_distance <= 5 and higher_low and momentum and demand and reclaim)
    extended = _extension(snapshot, pivot)
    mountain = _swing_mountain_position(snapshot, support, extended)
    candidate_qualified = bool(prior_advance and shorter_base and support is not None and
                               not inputs.get("failed_breakout"))
    actionable = bool(candidate_qualified and (fresh_breakout or support_reversal) and
                      not extended and mountain != "Upper")
    pattern_score = _score([100 if prior_advance else 25, 95 if shorter_base else 35,
                            90 if higher_low else 50])
    volume_score = _score([90 if contraction is not None and contraction <= 1 else 55,
                           95 if demand or volume_confirmed else 40])
    decision_score = _score([100 if fresh_breakout or support_reversal else 40,
                             95 if momentum else 35, 10 if extended else 90])
    score = _score([pattern_score, volume_score, decision_score])
    failures = [label for label, passed in (
        ("prior advance", prior_advance), ("shorter re-base", shorter_base),
        ("higher low", higher_low), ("momentum improving", momentum),
        ("short-term reclaim", reclaim), ("demand confirmation", demand),
        ("volume/RVOL confirmation", volume_confirmed),
        ("not failed", not inputs.get("failed_breakout")),
        ("not Extended", not extended and mountain != "Upper")) if not passed]
    return {
        "strategy": "C", "strategy_name": "Re-Base / Re-Acceleration",
        "stage": "Re-Base", "mountain_position": mountain,
        "candidate_qualified": candidate_qualified, "actionable": actionable,
        "candidate_score": _score([pattern_score, volume_score]),
        "decision_score": decision_score, "score": score,
        "pivot": pivot, "major_resistance": pivot, "support": support,
        "invalidation": _number(inputs.get("invalidation_level") or recent_low),
        "reward_risk": None, "extended": extended,
        "breakout_age_sessions": inputs.get("breakout_age_sessions"),
        "failed_gates": failures,
        "signals": {"fresh_breakout": fresh_breakout, "support_reversal": support_reversal,
                    "volume_confirmed": volume_confirmed, "higher_low": higher_low,
                    "momentum_improving": momentum, "demand_confirmation": demand},
        "pattern": "Post-advance shorter base with a current support/pivot execution structure",
        "pattern_summary": "Post-Advance Re-Base",
        "technical_pattern": "Re-Base / Re-Acceleration",
        "support_entry_zone": f"Re-base support {round(support, 2)}" if support else "N/A",
        "confirmation": (f"Higher low {'yes' if higher_low else 'no'} · reclaim "
                         f"{'yes' if reclaim else 'no'} · volume "
                         f"{'confirmed' if volume_confirmed else 'unconfirmed'}"),
        "trend_summary": f"Prior advance → Re-Base · Mountain {mountain}",
        "volume_summary": (f"Contraction {contraction if contraction is not None else 'N/A'}x · "
                           f"current RVOL {snapshot.get('volume_vs_20d_average', 'N/A')}x"),
    }


def _dilution_risk(candidate, snapshot):
    market_cap = _number(candidate.get("market_cap")) or _number(snapshot.get("market_cap"))
    price = _number(snapshot.get("current_price"))
    if (market_cap is not None and market_cap < 500_000_000) or (price is not None and price < 5):
        return "High — small-cap/low-price financing sensitivity; cash runway not verified in this technical scan."
    return "Unverified — review cash runway, shelf/ATM capacity, and recent financing before execution."


def _candidate_record(candidate, snapshot, assessment, catalyst, pool_name, action,
                      position=None, entry_context=None):
    position = position or _swing_position_metrics(snapshot)
    entry_context = entry_context or _swing_entry_context(assessment, snapshot)
    classification = _swing_strategy_entry_classification(assessment, entry_context)
    limit_buy = entry_context.get("limit_price")
    biotech = pool_name == "biotech"
    rank_score = assessment.get("score")
    if _number(rank_score) is not None:
        rank_score = max(0, min(100, rank_score + (5 if catalyst.get("credible") else -5)))
    failures = list(assessment.get("failed_gates") or [])
    primary_failures = {"long/mature base", "volatility contraction", "support hold/tightening",
                        "constructive base volume",
                        "major >=8% catalyst gap", "established Stage 2 uptrend",
                        "rising support", "healthy pullback/tight consolidation",
                        "prior advance", "shorter re-base"}
    decision_failures = [item for item in failures if item not in primary_failures]
    if biotech and catalyst.get("credible") is not True:
        decision_failures.append("verified company catalyst")
    failure_explanations = {
        "pivot cleared": "pivot not yet cleared",
        "volume/RVOL confirmation": "breakout volume/RVOL not confirmed",
        "relative strength": "relative strength not confirmed",
        "strong event volume/close": "event-day close quality not confirmed",
        "at least two follow-through sessions": "outside the 2–15 session continuation window",
        "gap midpoint/low support held": "gap midpoint/low support not held",
        "tight post-gap consolidation": "post-gap consolidation is not yet tight",
        "new continuation pivot/volume confirmation": "new continuation pivot/volume not confirmed",
        "not failed": "failed-breakout/reversal flag is active",
        "not Extended": "setup is Extended / Do Not Chase",
        "verified company catalyst": "company-specific catalyst not verified",
        "higher low": "first higher low not confirmed",
        "momentum improving": "momentum improvement not confirmed",
        "short-term reclaim": "early higher high / short-term resistance reclaim missing",
        "moving averages flattening/turning up": "short-term moving averages have not flattened or turned up",
        "demand confirmation": "improving price/volume demand not confirmed",
        "favorable reward/risk": "reward/risk to major resistance is below 1.5x or unavailable",
        "not one-day bounce": "move is only a one-day bounce without confirmation",
    }
    decision_failure_text = [failure_explanations.get(item, item) for item in decision_failures]
    gap = assessment.get("gap") or {}
    if action == "BUY NOW":
        entry_status = "Confirmed actionable entry"
        next_confirmation = "All current BUY NOW gates passed."
    elif action.startswith("DO NOT CHASE — Extended:"):
        entry_status = "Extended above valid entry level / DO NOT CHASE"
        next_confirmation = "Wait for an orderly pullback to valid support/pivot or a new confirmed base and breakout."
    elif action.startswith("SET LIMIT"):
        entry_status = "SET LIMIT / wait for pullback"
        next_confirmation = f"Price must pull back to the {limit_buy:.2f} limit without invalidating the setup."
    elif action.startswith("WAIT — current price above"):
        entry_status = "WAIT / current price above limit"
        next_confirmation = f"Price must reach the {limit_buy:.2f} limit without invalidating the setup."
    elif assessment.get("extended"):
        entry_status = "Extended / DO NOT CHASE"
        next_confirmation = "Wait for a new base or orderly pullback and fresh confirmation."
    elif biotech and catalyst.get("credible") is not True:
        catalyst_status = catalyst.get("catalyst_status") or catalyst.get("status") or "NO_COMPANY_CATALYST"
        entry_status = f"Technical candidate / {catalyst_status}"
        next_confirmation = f"Verify a company-specific biotech catalyst, then require the stated technical entry."
    else:
        entry_status = f"{assessment.get('stage') or 'Technical setup'} / entry incomplete"
        next_confirmation = "Require a fresh price-and-volume confirmation near the current valid support or pivot."
    execution_reason = (action if action.startswith(("DO NOT CHASE — Extended:", "SET LIMIT", "WAIT —"))
                        else None)
    why_not_now = ("None — all BUY NOW gates passed." if action == "BUY NOW" else
                   execution_reason or "; ".join(decision_failure_text) or
                   "Entry confirmation remains incomplete.")
    risk = (_dilution_risk(candidate, snapshot) if biotech else
            ("Extended / Do Not Chase" if entry_context.get("materially_extended") else
             "Technical failure below the active support/pivot; catalyst is optional for non-biotech."))
    forward_catalyst = (catalyst.get("description") if catalyst.get("credible") else
                        "Optional / not verified" if not biotech else
                        f"{catalyst.get('catalyst_status') or catalyst.get('status') or 'NO_COMPANY_CATALYST'}: "
                        f"{catalyst.get('validation_reason') or 'Required biotech company catalyst not verified'}")
    return {
        "company": candidate.get("company") or candidate.get("name") or candidate.get("ticker"),
        "ticker": candidate.get("ticker"), "exchange": candidate.get("exchange", ""),
        "source_sector": candidate.get("sector"), "source_industry": candidate.get("industry"),
        "listing_status": "Public", "domain": "biotech" if biotech else "swing",
        "swing_pool": pool_name, "strategy": assessment["strategy"],
        "strategy_name": assessment["strategy_name"], "classification": "Candidate Pool",
        "strategy_classification": classification["strategy"],
        "entry_classification": classification["entry"],
        "cycle_stage": classification["cycle_stage"],
        "mountain_position": assessment.get("mountain_position") or
                             _swing_mountain_position(snapshot, entry_context.get("base_support"),
                                                      assessment.get("extended")),
        "stage": assessment.get("stage"),
        "pool": "Action Pool" if action == "BUY NOW" else "Candidate Pool",
        "candidate_qualified": True, "actionable": action == "BUY NOW", "action": action,
        "candidate_score": assessment.get("candidate_score"),
        "decision_score": assessment.get("decision_score"),
        "dynamic_final_score": rank_score,
        "selection_score": rank_score, "current_price": snapshot.get("current_price"),
        "limit_buy": limit_buy,
        "fifty_two_week_low": position.get("fifty_two_week_low"),
        "fifty_two_week_high": position.get("fifty_two_week_high"),
        "pct_above_52_week_low": position.get("pct_above_52_week_low"),
        "pct_below_52_week_high": position.get("pct_below_52_week_high"),
        "support_pivot_level": entry_context.get("level"),
        "support_pivot_kind": entry_context.get("level_kind"),
        "pct_above_support_pivot": entry_context.get("distance_pct"),
        "base_support": entry_context.get("base_support"),
        "base_pivot": entry_context.get("base_pivot"),
        "pct_above_base_support": entry_context.get("support_distance_pct"),
        "pct_above_base_pivot": entry_context.get("pivot_distance_pct"),
        "entry_stage": entry_context.get("entry_stage"),
        "near_support_or_pivot": entry_context.get("near_level") is True,
        "support_reversal": entry_context.get("support_reversal") is True,
        "fresh_breakout": entry_context.get("fresh_breakout") is True,
        "breakout_age_sessions": entry_context.get("breakout_age_sessions"),
        "entry_qualification_reason": entry_context.get("qualification_reason"),
        "support_reclaim_evidence": (
            "Pivot cleared with fresh breakout confirmation"
            if entry_context.get("fresh_breakout") else
            "Former breakout support reclaimed and short-term high reclaimed"
            if (assessment.get("signals") or {}).get("breakout_support_reclaimed") else
            "Current support held with confirmed reversal"
            if entry_context.get("support_reversal") else
            "Support/pivot reclaim not confirmed"),
        "volume_confirmation_evidence": {
            "current_rvol": snapshot.get("volume_vs_20d_average"),
            "controlled_pullback": (assessment.get("signals") or {}).get("controlled_pullback"),
            "renewed_price_volume": (assessment.get("signals") or {}).get("renewed_price_volume"),
            "volume_confirmed": (assessment.get("signals") or {}).get("volume_confirmed"),
        },
        "trailing_stop_policy": {
            "initial_stop": "No initial fixed stop",
            "gain_30": "At or above +30%, use a 20% trailing stop.",
            "gain_50": "At or above +50%, tighten to a 15% trailing stop.",
            "acceleration": "Tighten further during sudden 1-month / 5-day acceleration.",
        },
        "exit_policy": "No initial fixed stop; activate profit-protecting trailing stops only after the stated gain thresholds.",
        "pattern": assessment.get("pattern_summary") or assessment.get("pattern"),
        "technical_pattern": assessment.get("technical_pattern"),
        "support_entry_zone": assessment.get("support_entry_zone"),
        "confirmation": assessment.get("confirmation"),
        "trend": assessment.get("trend_summary"), "volume": assessment.get("volume_summary"),
        "entry_status": entry_status, "why_not_now": why_not_now,
        "next_confirmation": next_confirmation,
        "entry_reference": assessment.get("pivot"),
        "major_resistance": assessment.get("major_resistance"),
        "invalidation": assessment.get("invalidation"),
        "reward_risk": assessment.get("reward_risk"),
        "forward_catalyst": forward_catalyst,
        "risk": risk, "technical_assessment": assessment, "catalyst": catalyst,
        "catalyst_validation": {"valid": catalyst.get("credible") is True,
                                "status": catalyst.get("status"),
                                "reason": catalyst.get("validation_reason")},
        "catalyst_status": catalyst.get("catalyst_status") or catalyst.get("status"),
        "market_data": {key: snapshot.get(key) for key in
                        ("current_price", "price_date", "currency", "source", "data_status",
                         "security_type", "domicile_country", "listing_exchange", "security_name")},
        "technical": {"current_price": snapshot.get("current_price"),
                      "resistance": assessment.get("major_resistance") or assessment.get("pivot"),
                      "invalidation_level": assessment.get("invalidation"),
                      "pattern": assessment.get("pattern"), "extended": assessment.get("extended"),
                      "price_date": snapshot.get("price_date")},
        "why_this_swing_trade_opportunity": {
            "summary": f"Independent full-market {assessment['strategy_name']} {action} candidate.",
            "why_chart_selected": assessment.get("pattern"),
            "catalyst_support": forward_catalyst,
            "invalidation": f"Structural invalidation {assessment.get('invalidation') or 'unavailable'}; no initial fixed stop is prescribed.",
        },
        "engine_version": "swing-full-market-v5",
    }


def _primary_swing_strategy(matches):
    """Choose one public strategy while retaining all technical matches internally.

    An actual A launch/retest is the most specific lifecycle event. A distinct
    post-advance re-base is next; otherwise an established Stage 2 continuation
    is primary. Candidate-only matches use the same lifecycle precedence.
    """
    precedence = ("strategy_a", "strategy_c", "strategy_b")
    for key in precedence:
        if key in matches and matches[key]["entry_context"].get("entry_qualified"):
            return key
    for key in precedence:
        if key in matches:
            return key
    return None


def build_swing_trade_engine(candidate_pool, market_data, ai_news_section=None,
                             biotech_news_section=None, limit=SWING_BUY_NOW_LIMIT,
                             previous_section=None, screen_diagnostics=None,
                             strategy_b_catalyst_data=None):
    """Build six technical pools, then apply pool-specific company gates."""
    candidates = list(candidate_pool or [])
    if isinstance(candidate_pool, dict):
        candidates = list(candidate_pool.get("candidates") or [])
    strategy_keys = ("strategy_a", "strategy_b", "strategy_c")
    pools = {name: {"label": label, **{key: [] for key in strategy_keys}}
             for name, label in (("biotech", "Biotech Swing"),
                                 ("non_biotech", "Non-Biotech Swing"))}
    evaluated = 0
    evaluated_by_pool = Counter()
    catalyst_verified = 0
    catalyst_status_counts = Counter()
    funnel_by_group = {
        pool: {strategy: {"technical": 0, "fundamental_catalyst": 0, "entry": 0, "buy_now": 0}
               for strategy in strategy_keys}
        for pool in ("biotech", "non_biotech")
    }
    funnel_tickers = {stage: set() for stage in
                      ("technical", "fundamental_catalyst", "entry", "buy_now")}
    secondary_matches = []
    for candidate in candidates:
        ticker = candidate.get("ticker")
        snapshot = ((market_data or {}).get("securities") or {}).get(ticker)
        if not ticker or not snapshot or snapshot.get("data_status") != "current":
            continue
        evaluated += 1
        # Re-evaluate the shared classification here so stale/fallback pool labels
        # cannot preserve earlier broad-keyword false positives.
        pool_name = "biotech" if is_biotech_company(candidate) else "non_biotech"
        biotech = pool_name == "biotech"
        evaluated_by_pool[pool_name] += 1
        assessments = {
            "strategy_a": assess_long_base_breakout(snapshot, biotech),
            "strategy_b": assess_stage2_continuation(snapshot, biotech),
            "strategy_c": assess_rebase_reacceleration(snapshot, biotech),
        }
        optional_catalyst = _independent_catalyst(ticker, candidate.get("company") or ticker,
                                                  ai_news_section, biotech_news_section)
        # Preserve the gap/date-aligned retrieval as catalyst evidence only. It
        # no longer defines a technical strategy.
        gap_assessment = assess_gap_continuation(snapshot, biotech)
        validated_catalyst = optional_catalyst
        if gap_assessment.get("candidate_qualified"):
            gap_catalyst = resolve_strategy_b_catalyst(
                candidate, gap_assessment,
                (strategy_b_catalyst_data or {}).get(ticker),
                ai_news_section, biotech_news_section)
            catalyst_status_counts[gap_catalyst["catalyst_status"]] += 1
            if gap_catalyst.get("credible"):
                catalyst_verified += 1
                validated_catalyst = gap_catalyst
        matches = {}
        for key, assessment in assessments.items():
            if not assessment.get("candidate_qualified"):
                continue
            catalyst = validated_catalyst
            # Technical definitions are identical across pools. Biotech retains
            # its verified company-catalyst/fundamental gate; non-biotech retains
            # catalyst as optional ranking support.
            company_gate_passed = not biotech or catalyst.get("credible") is True
            position = _swing_position_metrics(snapshot)
            entry_context = _swing_entry_context(assessment, snapshot)
            action = _swing_execution_action(company_gate_passed, assessment, snapshot,
                                             entry_context)
            matches[key] = {"assessment": assessment, "catalyst": catalyst,
                            "position": position, "entry_context": entry_context,
                            "action": action}
            group_funnel = funnel_by_group[pool_name][key]
            group_funnel["technical"] += 1
            funnel_tickers["technical"].add(ticker)
            fundamental_pass = company_gate_passed
            if fundamental_pass:
                group_funnel["fundamental_catalyst"] += 1
                funnel_tickers["fundamental_catalyst"].add(ticker)
            if fundamental_pass and entry_context.get("entry_qualified") is True:
                group_funnel["entry"] += 1
                funnel_tickers["entry"].add(ticker)
        primary_key = _primary_swing_strategy(matches)
        if primary_key is None:
            continue
        secondary_names = [value["assessment"]["strategy_name"]
                           for key, value in matches.items() if key != primary_key]
        for key, values in matches.items():
            row = _candidate_record(candidate, snapshot, values["assessment"],
                                    values["catalyst"], pool_name, values["action"],
                                    values["position"], values["entry_context"])
            row["primary_strategy_key"] = primary_key
            row["primary_strategy"] = matches[primary_key]["assessment"]["strategy_name"]
            row["is_primary_strategy"] = key == primary_key
            row["secondary_strategy_matches"] = secondary_names
            if key == primary_key:
                pools[pool_name][key].append(row)
                if row.get("action") == "BUY NOW":
                    funnel_by_group[pool_name][key]["buy_now"] += 1
                    funnel_tickers["buy_now"].add(ticker)
            else:
                secondary_matches.append(row)
    opportunities, ranked_setups = [], []
    for pool_name in ("biotech", "non_biotech"):
        for key in strategy_keys:
            all_rows = sorted(pools[pool_name][key],
                              key=lambda row: (-(row.get("dynamic_final_score") or -1), row["ticker"]))
            for rank, row in enumerate(all_rows, 1):
                row["candidate_rank"] = rank
                row["rank"] = rank
                row["dynamic_final_rank"] = rank
            buy_now = [row for row in all_rows if row.get("action") == "BUY NOW"][:limit]
            set_limit = [row for row in all_rows
                         if str(row.get("action") or "").startswith("SET LIMIT")][:limit]
            rows = buy_now_first_display(all_rows, limit)
            fallback_labels = {"strategy_a": "Stage 1 → Stage 2 Launch",
                               "strategy_b": "Stage 2 Trend Continuation",
                               "strategy_c": "Re-Base / Re-Acceleration"}
            pools[pool_name][key] = {"label": rows[0]["strategy_name"] if rows else fallback_labels[key],
                                    "candidate_count": len(all_rows), "candidates": rows,
                                    "buy_now": buy_now, "buy_now_count": len(buy_now),
                                    "set_limit": set_limit,
                                    "set_limit_count": sum(
                                        str(row.get("action") or "").startswith("SET LIMIT")
                                        for row in all_rows),
                                    "wait_count": sum(row.get("action") != "BUY NOW" for row in all_rows)}
            opportunities.extend(buy_now)
            ranked_setups.extend(rows)
    for pool_name, strategies in funnel_by_group.items():
        for values in strategies.values():
            values["universe"] = evaluated_by_pool[pool_name]
            values["data_liquidity"] = evaluated_by_pool[pool_name]
    diagnostic_funnel = {
        "overall": {
            "universe": (screen_diagnostics or {}).get("total_stocks_scanned", evaluated),
            "data_liquidity": (screen_diagnostics or {}).get("initial_screen_pass", evaluated),
            **{stage: len(tickers) for stage, tickers in funnel_tickers.items()},
        },
        "by_pool_strategy": funnel_by_group,
        "definitions": {
            "technical": "Unique stocks qualifying for Strategy A, B, and/or C technical Candidate Pool.",
            "fundamental_catalyst": "Biotech requires verified company-specific catalyst/fundamental support; non-biotech catalyst is optional for every technical strategy.",
            "entry": "Technical entry confirmation after the applicable fundamental/catalyst gate.",
            "buy_now": "All existing gates pass, the setup is a fresh confirmed reversal near current base support or a fresh confirmed breakout near the current base pivot, it is not extended, and its entry limit is no more than 1% below market.",
        },
    }
    coverage = {**(screen_diagnostics or {}), "market_history_evaluated": evaluated,
                "verified_company_catalysts": catalyst_verified,
                "strategy_b_verified_gap_aligned_catalysts": catalyst_verified,
                "strategy_b_catalyst_status_counts": dict(catalyst_status_counts),
                "secondary_strategy_match_count": len(secondary_matches),
                "unique_primary_candidates": sum(
                    pools[pool][key]["candidate_count"]
                    for pool in ("biotech", "non_biotech") for key in strategy_keys),
                "buy_now_total": len(opportunities),
                "biotech_strategy_a_candidates": pools["biotech"]["strategy_a"]["candidate_count"],
                "biotech_strategy_b_candidates": pools["biotech"]["strategy_b"]["candidate_count"],
                "biotech_strategy_c_candidates": pools["biotech"]["strategy_c"]["candidate_count"],
                "non_biotech_strategy_a_candidates": pools["non_biotech"]["strategy_a"]["candidate_count"],
                "non_biotech_strategy_b_candidates": pools["non_biotech"]["strategy_b"]["candidate_count"],
                "non_biotech_strategy_c_candidates": pools["non_biotech"]["strategy_c"]["candidate_count"],
                "biotech_strategy_a_buy_now": len(pools["biotech"]["strategy_a"]["buy_now"]),
                "biotech_strategy_b_buy_now": len(pools["biotech"]["strategy_b"]["buy_now"]),
                "biotech_strategy_c_buy_now": len(pools["biotech"]["strategy_c"]["buy_now"]),
                "non_biotech_strategy_a_buy_now": len(pools["non_biotech"]["strategy_a"]["buy_now"]),
                "non_biotech_strategy_b_buy_now": len(pools["non_biotech"]["strategy_b"]["buy_now"]),
                "non_biotech_strategy_c_buy_now": len(pools["non_biotech"]["strategy_c"]["buy_now"]),
                "diagnostic_funnel": diagnostic_funnel}
    return {
        "methodology": {
            "engine_version": "swing-full-market-v5",
            "architecture": "Independent full-market short-term execution; never sourced from Radar or High Conviction.",
            "primary_screen": "Pattern → Trend → Volume creates the ranked Candidate Pool before confirmation or execution gates.",
            "primary_strategy_policy": "Each ticker has one public Primary Strategy. A confirmed Stage 1 launch/first retest takes precedence, then a distinct post-advance re-base, then established Stage 2 continuation. Other technical matches remain in secondary_strategy_matches and cannot create duplicate public actions.",
            "strategy_a": "Stage 1 → Stage 2 Launch requires a genuine 42/63-session mature base. Entry 1 is a fresh volume-confirmed initial breakout near the base pivot; Entry 2 is the first confirmed pullback/retest of that pivot as support.",
            "strategy_b": "Stage 2 Trend Continuation requires an established rising Stage 2 structure, then a healthy pullback/tight consolidation near rising support and renewed price/volume confirmation. It does not require a long Stage 1 base.",
            "strategy_c": "Re-Base / Re-Acceleration requires a prior advance followed by a shorter, contracting new base. Entry is a fresh confirmed breakout near the new pivot or a confirmed retest/reversal near new support.",
            "catalyst_policy": "Catalyst does not define A/B/C. Biotech retains a verified company-specific catalyst/fundamental BUY gate across all three; non-biotech catalyst support remains optional.",
            "buy_now_policy": "BUY NOW requires either a fresh confirmed reversal near the current valid base support or a fresh confirmed breakout near the current base pivot. A valid entry more than 1% below market is SET LIMIT; an entry extended more than the existing 5% boundary from its active support/pivot is DO NOT CHASE. 52-week position is context only.",
            "entry_2_policy": "A first pullback/retest requires a recent breakout attempt, controlled lower-volume pullback, higher-low support hold, reclaim of the former breakout level and short-term high, plus a positive reversal day with current volume at least 1.0x and improving momentum.",
            "execution_policy": "No initial fixed stop. At +30% activate a 20% trailing stop; at +50% tighten it to 15%; tighten further during sudden 1-month / 5-day acceleration.",
            "missing_data_policy": "Missing measurements fail the relevant gate and never create an entry price.",
        },
        "pools": pools, "opportunities": opportunities, "ranked_setups": ranked_setups,
        "secondary_strategy_matches": secondary_matches,
        "unverified_setups": [], "watch_setups": [], "stage_tracking": [],
        "coverage": coverage,
        "take_home_messages": [
            f"{evaluated} independently sourced full-market candidates had current price history.",
            f"{len(ranked_setups)} top-ranked candidates are displayed across six independent pools; {len(opportunities)} are BUY NOW.",
            "A/B/C share technical definitions across pools; Biotech and Non-Biotech retain separate company-validation rules.",
            "WAIT candidates remain visible with the exact missing confirmation; pullback entries are labeled SET LIMIT rather than BUY NOW.",
        ],
    }
