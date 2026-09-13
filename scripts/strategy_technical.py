"""Strategy-specific technical setups built from the shared market-data layer."""

from __future__ import annotations


def _number(value):
    return value if isinstance(value, (int, float)) else None


def _distance(price, reference):
    return round((price / reference - 1) * 100, 2) if price and reference else None


def _average(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values)) if values else None


def _bounded(value):
    return None if value is None else max(0, min(100, round(value)))


def radar_base_breakout_setup(snapshot):
    """Radar: require the complete base-to-breakout sequence before action."""
    snapshot = snapshot or {}
    price = _number(snapshot.get("current_price"))
    mas = snapshot.get("moving_averages") or {}
    inputs = snapshot.get("entry_inputs") or {}
    macd = snapshot.get("macd") or {}
    returns = snapshot.get("returns") or {}
    base_sessions = inputs.get("base_duration_sessions")
    base_range = _number(inputs.get("base_range_pct"))
    mature_base = bool(base_sessions in (42, 63) and base_range is not None and
                       base_range <= (20 if base_sessions == 42 else 25))
    tight_range = _number(inputs.get("tight_range_20d_pct"))
    contraction = _number(inputs.get("volume_contraction_ratio"))
    accumulation = _number(inputs.get("up_down_volume_ratio_20d"))
    volatility_contracted = bool(
        mature_base and tight_range is not None and base_range is not None and
        tight_range <= min(15, base_range * .75) and
        ((contraction is not None and contraction <= .95) or
         (accumulation is not None and accumulation >= 1)))
    higher_low = inputs.get("higher_low_confirmed") is True
    ma20_slope = _number(inputs.get("ma20_slope_10d_pct"))
    proximity = _number(inputs.get("breakout_proximity_pct"))
    volume = _number(inputs.get("breakout_volume_ratio"))
    distance20 = _distance(price, _number(mas.get("ma20")))
    distance50 = _distance(price, _number(mas.get("ma50")))
    unavailable = price is None or _number(mas.get("ma20")) is None or _number(mas.get("ma50")) is None
    falling = bool(price and mas.get("ma50") and mas.get("ma20") and
                   price < mas["ma50"] and mas["ma20"] < mas["ma50"] and
                   _number(macd.get("histogram")) is not None and macd["histogram"] < 0)
    extended = any((distance20 is not None and distance20 > 12,
                    distance50 is not None and distance50 > 18,
                    _number(returns.get("three_month")) is not None and returns["three_month"] > 40,
                    proximity is not None and proximity > 8))
    momentum_confirmed = bool(macd.get("crossover") == "bullish" or
                              (macd.get("improving") is True and
                               _number(macd.get("histogram")) is not None and macd["histogram"] >= 0))
    primary_trend = bool(price and mas.get("ma20") and mas.get("ma50") and
                         price >= mas["ma20"] >= mas["ma50"] and
                         ma20_slope is not None and ma20_slope > 0)
    confirmed_reversal = bool(mature_base and volatility_contracted and higher_low and
                              primary_trend and momentum_confirmed)
    breakout = bool(confirmed_reversal and proximity is not None and 0 <= proximity <= 5 and
                    volume is not None and volume >= 1.2)
    failed_reversal = bool(inputs.get("failed_breakout") is True or
                           (not unavailable and mature_base and price < mas["ma20"] and
                           _number(macd.get("histogram")) is not None and macd["histogram"] < 0 and
                           macd.get("improving") is not True))
    if unavailable:
        stage = "Unavailable"
    elif falling:
        stage = "Falling"
    elif failed_reversal:
        stage = "Failed Reversal"
    elif extended:
        stage = "Extended"
    elif breakout:
        stage = "Early Uptrend / Breakout"
    elif confirmed_reversal:
        stage = "Confirmed Reversal"
    elif mature_base:
        stage = "Mature Base"
    else:
        stage = "Volatile Bottom / First Bounce"
    base_score = 90 if base_sessions == 63 else 75 if base_sessions == 42 else 30
    contraction_score = 90 if volatility_contracted else 45 if mature_base else 20
    structure_score = 90 if higher_low else 35
    momentum_score = 90 if momentum_confirmed else 55 if macd.get("improving") else 25
    breakout_score = 95 if breakout else 75 if proximity is not None and -5 <= proximity < 0 else 40
    trend_score = (90 if primary_trend else 55 if price and mas.get("ma50") and price >= mas["ma50"]
                   else 30 if price and mas.get("ma50") else None)
    score = _average([base_score, contraction_score, structure_score, momentum_score,
                      breakout_score, trend_score])
    if stage == "Unavailable":
        score = 0
    elif stage in ("Falling", "Failed Reversal"):
        score = min(score or 0, 25)
    elif stage == "Extended":
        score = min(score or 0, 35)
    return {
        "engine": "Radar = Base / Breakout", "stage": stage, "score": _bounded(score),
        "actionable": stage == "Early Uptrend / Breakout",
        "mature_base": mature_base, "confirmed_reversal": confirmed_reversal,
        "volatility_contracted": volatility_contracted, "higher_low_confirmed": higher_low,
        "primary_trend_confirmed": primary_trend,
        "breakout_confirmed": breakout, "extended": extended, "falling": falling,
        "failed_reversal": failed_reversal, "unavailable": unavailable,
        "entry_quality": ("Strong" if breakout else "Constructive / Await Pivot" if confirmed_reversal else
                          "Unavailable" if unavailable else "Wait" if mature_base else "Unconfirmed"),
        "invalidation_level": inputs.get("invalidation_level"),
        "rationale": (f"{stage}. Action requires a 42/63-session mature base, contracting volatility/selling pressure, "
                      "a higher low, rising short-term trend, and a resistance break on at least 1.2x average volume."),
    }


def high_conviction_continuation_setup(snapshot):
    """High Conviction: reward established uptrends and controlled continuations."""
    snapshot = snapshot or {}
    price = _number(snapshot.get("current_price"))
    mas = snapshot.get("moving_averages") or {}
    inputs = snapshot.get("entry_inputs") or {}
    returns = snapshot.get("returns") or {}
    macd = snapshot.get("macd") or {}
    ma20, ma50, ma200 = (_number(mas.get(key)) for key in ("ma20", "ma50", "ma200"))
    distance20, distance50 = _distance(price, ma20), _distance(price, ma50)
    established = bool(price and ma50 and ma200 and price > ma200 and ma50 > ma200 and
                       (_number(returns.get("three_month")) is None or returns["three_month"] > 0))
    higher_low = inputs.get("higher_low_confirmed") is True
    ma50_slope = _number(inputs.get("ma50_slope_20d_pct"))
    support_hold = bool(established and price and ma50 and price >= ma50 and higher_low and
                        ma50_slope is not None and ma50_slope > 0 and
                        (inputs.get("recent_low_20d") is None or inputs["recent_low_20d"] >= ma50 * .97))
    healthy_pullback = bool(established and distance50 is not None and 0 <= distance50 <= 12 and
                            (distance20 is None or -5 <= distance20 <= 6))
    resumption = bool(established and healthy_pullback and support_hold and price and
                      (ma20 is None or price >= ma20) and inputs.get("short_term_high_reclaimed") is True and
                      (_number(macd.get("histogram")) is None or macd["histogram"] >= 0 or macd.get("improving") is True))
    extended = any((distance20 is not None and distance20 > 15,
                    distance50 is not None and distance50 > 25,
                    _number(returns.get("three_month")) is not None and returns["three_month"] > 50,
                    _number(snapshot.get("rsi_14")) is not None and snapshot["rsi_14"] >= 78))
    falling = bool(price and ma200 and price < ma200 and
                   _number(macd.get("histogram")) is not None and macd["histogram"] < 0)
    if falling:
        stage = "Falling / Trend Broken"
    elif extended:
        stage = "Extended"
    elif resumption and healthy_pullback:
        stage = "Trend Resumption"
    elif healthy_pullback and support_hold:
        stage = "Healthy Pullback / Higher Low"
    elif established:
        stage = "Established Uptrend"
    else:
        stage = "Uptrend Unconfirmed"
    trend_score = 95 if established else 20
    pullback_score = 90 if healthy_pullback else 70 if established and not extended else 25
    support_score = 90 if support_hold else 35
    momentum_score = 85 if resumption else 55 if macd.get("improving") else 30
    score = _average([trend_score, pullback_score, support_score, momentum_score])
    if extended:
        score = min(score or 0, 40)
    elif falling:
        score = min(score or 0, 20)
    return {
        "engine": "High Conviction = Uptrend / Pullback / Continuation", "stage": stage,
        "score": _bounded(score), "actionable": stage == "Trend Resumption",
        "established_uptrend": established, "healthy_pullback": healthy_pullback,
        "support_hold": support_hold, "higher_low_confirmed": higher_low,
        "trend_resumption": resumption,
        "extended": extended, "falling": falling,
        "entry_quality": ("Best" if stage == "Trend Resumption" else "Good" if healthy_pullback else
                          "Acceptable" if established and not extended else "Wait"),
        "invalidation_level": inputs.get("invalidation_level") or ma50,
        "rationale": (f"{stage}. Action requires an established long-term uptrend, a normal pullback, a rising MA50, "
                      "a higher-low support hold, and a momentum-backed reclaim of the prior 10-session high."),
    }


def dynamic_alignment_score(story_score, technical_setup, entry_score=None, upside_score=None,
                            risk_score=None, classification_penalty=0):
    """Normalize available strategy inputs, then apply explicit setup/risk gates."""
    inputs = [(story_score, 50), ((technical_setup or {}).get("score"), 25),
              (entry_score, 10), (upside_score, 10), (risk_score, 5)]
    available = [(value, weight) for value, weight in inputs if _number(value) is not None]
    if not available:
        return None
    score = sum(value * weight for value, weight in available) / sum(weight for _, weight in available)
    setup = technical_setup or {}
    if not setup.get("actionable"):
        score -= 12
    if setup.get("falling"):
        score -= 20
    if setup.get("extended"):
        score -= 25
    if setup.get("failed_reversal"):
        score -= 20
    if setup.get("unavailable"):
        score -= 25
    if setup.get("stage") == "Volatile Bottom / First Bounce":
        score -= 8
    return _bounded(score - classification_penalty)
