"""Options Strategy layer that consumes existing directional theses only."""

from __future__ import annotations

import math


ACTION_LABELS = {"BUY", "SCALE IN", "ACTION", "ACTIONABLE REVIEW", "ENTER"}
PUBLIC_OPTION_EXCLUSIONS = {"Private", "N/A", ""}


def _number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def _bounded(value):
    return None if value is None else max(0, min(100, round(value)))


def _ticker(value):
    return str(value or "").strip().upper()


def _is_public_equity(ticker, row):
    return bool(ticker and ticker not in PUBLIC_OPTION_EXCLUSIONS and
                not ticker.endswith("-USD") and ":" not in ticker and
                row.get("listing_status", "Public") == "Public")


def _source_actionable(row):
    return bool(row.get("actionable") is True or row.get("pool") == "Action Pool" or
                str(row.get("action") or "").upper() in ACTION_LABELS)


def _thesis_record(row, source, score=None, horizon_days=120, rationale=None,
                   catalyst=None, catalyst_days=None):
    ticker = _ticker(row.get("ticker"))
    if not _is_public_equity(ticker, row):
        return None
    market = row.get("market_data") or {}
    return {
        "ticker": ticker,
        "company": row.get("company") or ticker,
        "direction": "Bullish",
        "horizon_days": horizon_days,
        "directional_score": _number(score),
        "thesis_confirmed": _source_actionable(row),
        "timing_confirmed": _source_actionable(row),
        "source": source,
        "sources": [source],
        "rationale": rationale or row.get("why_selected") or row.get("thesis") or
                     row.get("why_important") or "Existing directional thesis; detail unavailable.",
        "catalyst": catalyst or row.get("catalyst") or row.get("company_specific_catalyst"),
        "catalyst_days": _number(catalyst_days),
        "market_data": market,
        "risk_objective": "Defined-risk directional exposure",
    }


def collect_directional_theses(ai_radar=None, growth_radar=None, biotech_radar=None,
                               crypto_radar=None, high_conviction=None, swing_section=None):
    """Deduplicate existing strategy output; never discover or select a new stock."""
    records = []
    for trend in ai_radar or []:
        for row in trend.get("beneficiary_records") or []:
            records.append(_thesis_record(
                row, "AI / Technology Radar",
                row.get("dynamic_final_score") or row.get("bottleneck_opportunity_score"), 180,
                row.get("why_selected") or row.get("why_this_company"),
                row.get("company_specific_catalyst")))
    for row in growth_radar or []:
        records.append(_thesis_record(
            row, "Growth Opportunities", row.get("dynamic_final_score"), 120,
            row.get("why_selected"), row.get("catalyst_inputs")))
    for row in biotech_radar or []:
        records.append(_thesis_record(
            row, "Biotech Radar", row.get("dynamic_final_score"), 120,
            row.get("why_important"), row.get("company_specific_catalyst") or row.get("catalyst")))
    for row in crypto_radar or []:
        if str(row.get("asset_type") or "").lower() in ("native crypto", "crypto asset"):
            continue
        records.append(_thesis_record(
            row, "Crypto / Stablecoin Radar", row.get("dynamic_final_score"), 90,
            row.get("thesis"), row.get("catalysts")))
    qualified = (high_conviction or {}).get("qualified") or high_conviction or {}
    if isinstance(qualified, dict):
        for rows in qualified.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                records.append(_thesis_record(
                    row, "High Conviction", row.get("dynamic_final_score") or row.get("final_score"),
                    365, row.get("why_high_conviction") or row.get("why_selected"),
                    row.get("company_specific_catalyst") or row.get("catalyst")))
    for row in (swing_section or {}).get("ranked_setups") or []:
        why = row.get("why_this_swing_trade_opportunity") or {}
        records.append(_thesis_record(
            row, "Swing Trade", row.get("dynamic_final_score"), 45,
            why.get("why_chart_selected"), (row.get("catalyst") or {}).get("description")))

    merged = {}
    for record in (item for item in records if item):
        ticker = record["ticker"]
        old = merged.get(ticker)
        if old is None:
            merged[ticker] = record
            continue
        old["sources"] = list(dict.fromkeys(old["sources"] + record["sources"]))
        old["thesis_confirmed"] = old["thesis_confirmed"] or record["thesis_confirmed"]
        old["timing_confirmed"] = old["timing_confirmed"] or record["timing_confirmed"]
        old_score = old.get("directional_score") or -1
        new_score = record.get("directional_score") or -1
        if new_score > old_score:
            preserved_sources = old["sources"]
            preserved_confirmed = old["thesis_confirmed"]
            preserved_timing = old["timing_confirmed"]
            merged[ticker] = {**record, "sources": preserved_sources,
                              "thesis_confirmed": preserved_confirmed,
                              "timing_confirmed": preserved_timing}
    return sorted(merged.values(), key=lambda row: (
        not row["thesis_confirmed"], -(row.get("directional_score") or -1), row["ticker"]))


def _liquidity(option_data):
    bid = _number(option_data.get("bid"))
    ask = _number(option_data.get("ask"))
    spread = _number(option_data.get("bid_ask_spread_pct"))
    if spread is None and bid is not None and ask is not None and ask >= bid and bid + ask > 0:
        spread = round((ask - bid) / ((ask + bid) / 2) * 100, 2)
    open_interest = _number(option_data.get("open_interest"))
    volume = _number(option_data.get("contract_volume"))
    complete = spread is not None and open_interest is not None and volume is not None
    confirmed = bool(complete and spread <= 12 and open_interest >= 100 and volume >= 10)
    spread_score = (95 if spread is not None and spread <= 5 else 80 if spread is not None and spread <= 8
                    else 60 if spread is not None and spread <= 12 else 20 if spread is not None else None)
    interest_score = (95 if open_interest is not None and open_interest >= 1000 else
                      80 if open_interest is not None and open_interest >= 500 else
                      65 if open_interest is not None and open_interest >= 100 else
                      20 if open_interest is not None else None)
    volume_score = (90 if volume is not None and volume >= 100 else
                    75 if volume is not None and volume >= 25 else
                    60 if volume is not None and volume >= 10 else
                    20 if volume is not None else None)
    values = [value for value in (spread_score, interest_score, volume_score) if value is not None]
    return {
        "confirmed": confirmed, "data_complete": complete,
        "bid_ask_spread_pct": spread, "open_interest": open_interest,
        "contract_volume": volume,
        "score": round(sum(values) / len(values)) if len(values) == 3 else None,
        "rule": "Selected legs require spread <=12% of midpoint, open interest >=100, and daily contract volume >=10.",
    }


def _candidate_structure(thesis, option_data, ownership):
    direction = str(thesis.get("direction") or "").title()
    iv_rank = _number(option_data.get("iv_rank"))
    objective = str((ownership or {}).get("risk_objective") or thesis.get("risk_objective") or "").lower()
    shares = _number((ownership or {}).get("shares")) or 0
    term_structure = str(option_data.get("term_structure") or "").lower()
    catalyst_days = _number(thesis.get("catalyst_days"))
    horizon = _number(thesis.get("horizon_days")) or 0
    if shares >= 100 and "protect" in objective:
        return "Protective Put"
    if shares >= 100 and "income" in objective and (catalyst_days is None or catalyst_days > 30):
        return "Covered Call"
    if term_structure == "front_rich" and horizon >= 90 and catalyst_days is None:
        return "Call Calendar" if option_data.get("same_strike_calendar") is True else "Call Diagonal"
    if iv_rank is None:
        return None
    if direction == "Bullish":
        return "Long Call" if iv_rank <= 40 else "Bull Call Spread"
    if direction == "Bearish":
        return "Long Put" if iv_rank <= 40 else "Bear Put Spread"
    return None


def _economics(strategy, thesis, option_data, ownership):
    price = _number(option_data.get("underlying_price"))
    long_strike = _number(option_data.get("long_strike"))
    short_strike = _number(option_data.get("short_strike"))
    debit = _number(option_data.get("premium_debit"))
    credit = _number(option_data.get("premium_credit"))
    expected_move = _number(option_data.get("expected_move_pct"))
    estimated_rr = _number(option_data.get("estimated_reward_risk_ratio"))
    max_risk = max_reward = breakeven = expected_reward = None
    reward_label = None
    if strategy == "Long Call" and None not in (long_strike, debit):
        max_risk, breakeven, reward_label = debit * 100, long_strike + debit, "Unlimited (theoretical)"
        if price is not None and expected_move is not None:
            expected_reward = max(0, price * (1 + expected_move / 100) - long_strike - debit) * 100
    elif strategy == "Long Put" and None not in (long_strike, debit):
        max_risk, breakeven = debit * 100, long_strike - debit
        max_reward, reward_label = max(0, long_strike - debit) * 100, None
        if price is not None and expected_move is not None:
            expected_reward = max(0, long_strike - price * (1 - expected_move / 100) - debit) * 100
    elif strategy == "Bull Call Spread" and None not in (long_strike, short_strike, debit) and short_strike > long_strike:
        max_risk, max_reward, breakeven = debit * 100, (short_strike - long_strike - debit) * 100, long_strike + debit
    elif strategy == "Bear Put Spread" and None not in (long_strike, short_strike, debit) and long_strike > short_strike:
        max_risk, max_reward, breakeven = debit * 100, (long_strike - short_strike - debit) * 100, long_strike - debit
    elif strategy == "Covered Call" and None not in (short_strike, credit):
        cost = _number((ownership or {}).get("cost_basis")) or price
        if cost is not None:
            max_risk = max(0, cost - credit) * 100
            max_reward = max(0, short_strike - cost + credit) * 100
            breakeven = cost - credit
    elif strategy == "Protective Put" and None not in (long_strike, debit):
        cost = _number((ownership or {}).get("cost_basis")) or price
        if cost is not None:
            max_risk = max(0, cost - long_strike + debit) * 100
            breakeven, reward_label = cost + debit, "Unlimited stock upside less put premium"
    elif strategy in ("Call Calendar", "Call Diagonal") and debit is not None:
        max_risk, reward_label = debit * 100, "Variable; depends on front-expiry value and IV"
    if estimated_rr is None and max_risk is not None and max_risk > 0:
        reward = expected_reward if expected_reward is not None else max_reward
        estimated_rr = round(reward / max_risk, 2) if reward is not None else None
    return {
        "max_risk": round(max_risk, 2) if max_risk is not None else None,
        "max_reward": round(max_reward, 2) if max_reward is not None else reward_label,
        "breakeven": round(breakeven, 4) if breakeven is not None else None,
        "estimated_reward_risk_ratio": estimated_rr,
        "expected_reward_at_implied_move": (round(expected_reward, 2)
                                             if expected_reward is not None else None),
    }


def assess_options_candidate(thesis, option_data=None, ownership=None):
    """Assess a supplied thesis; missing option-market evidence fails closed."""
    option_data = option_data or {}
    ownership = ownership or {}
    liquidity = _liquidity(option_data)
    structure = _candidate_structure(thesis, option_data, ownership)
    economics = _economics(structure, thesis, option_data, ownership) if structure else {
        "max_risk": None, "max_reward": None, "breakeven": None,
        "estimated_reward_risk_ratio": None, "expected_reward_at_implied_move": None,
    }
    iv_rank = _number(option_data.get("iv_rank"))
    expected_move = _number(option_data.get("expected_move_pct"))
    expiration = option_data.get("expiration")
    expiration_days = _number(option_data.get("expiration_days"))
    if structure in ("Call Calendar", "Call Diagonal"):
        expiration = option_data.get("near_expiration") and option_data.get("far_expiration")
        expiration_days = _number(option_data.get("far_expiration_days"))
    catalyst_days = _number(thesis.get("catalyst_days"))
    catalyst_aligned = bool(expiration_days is not None and
                              (catalyst_days is None or expiration_days >= catalyst_days + 7))
    contract_defined = bool(structure and expiration and expiration_days is not None and
                            economics["max_risk"] is not None and economics["breakeven"] is not None)
    if structure in ("Call Calendar", "Call Diagonal"):
        contract_defined = bool(structure and expiration and expiration_days is not None and
                                economics["max_risk"] is not None and
                                economics["estimated_reward_risk_ratio"] is not None)
    risk_reward_confirmed = bool(
        economics["estimated_reward_risk_ratio"] is not None and
        economics["estimated_reward_risk_ratio"] >= 1)
    gates = {
        "directional_thesis": thesis.get("thesis_confirmed") is True,
        "technical_timing": thesis.get("timing_confirmed") is True,
        "iv_available": iv_rank is not None,
        "expected_move_available": expected_move is not None,
        "liquidity_spread": liquidity["confirmed"],
        "expiration_catalyst_alignment": catalyst_aligned,
        "contract_terms_defined": contract_defined,
        "reward_risk": risk_reward_confirmed,
    }
    missing = [name for name, passed in gates.items() if not passed]
    action = "ACTION" if all(gates.values()) else "WAIT"
    strategy = structure if action == "ACTION" else "No recommendation"

    option_score = None
    if (iv_rank is not None and expected_move is not None and liquidity["score"] is not None and
            economics["estimated_reward_risk_ratio"] is not None):
        iv_fit = (90 if (structure in ("Bull Call Spread", "Bear Put Spread") and iv_rank > 40) or
                        (structure in ("Long Call", "Long Put") and iv_rank <= 40)
                  else 75 if structure in ("Call Calendar", "Call Diagonal") else 55)
        reward_score = _bounded(45 + economics["estimated_reward_risk_ratio"] * 20)
        timing_score = 90 if thesis.get("timing_confirmed") else 35
        thesis_score = _number(thesis.get("directional_score")) or 50
        option_score = _bounded(liquidity["score"] * .25 + iv_fit * .2 + reward_score * .25 +
                                timing_score * .15 + thesis_score * .15)

    horizon = _number(thesis.get("horizon_days"))
    expiration_logic = (f"Use the verified {expiration} expiry ({expiration_days:g} DTE), extending at least "
                        f"7 days beyond any known catalyst."
                        if expiration and expiration_days is not None else
                        "Missing: select a liquid expiry aligned with the thesis horizon and at least 7 days beyond any known catalyst.")
    long_strike = _number(option_data.get("long_strike"))
    short_strike = _number(option_data.get("short_strike"))
    strike_logic = (f"Verified legs: long {long_strike:g}" +
                    (f" / short {short_strike:g}." if short_strike is not None else ".")
                    if long_strike is not None else
                    "Missing: strikes require verified quotes, liquidity, premium, and payoff calculations.")
    risks = [
        "Options can lose 100% of premium and are sensitive to time decay and implied-volatility changes.",
        "Wide spreads or insufficient open interest/volume can make modeled exits unreliable.",
    ]
    if catalyst_days is not None:
        risks.append("Binary catalyst gaps can exceed the implied move; expiry must extend beyond the event.")
    if action == "WAIT":
        risks.append("No recommendation until every thesis, timing, IV, expected-move, liquidity, contract, and reward/risk gate passes.")
    return {
        **thesis,
        "strategy": strategy,
        "candidate_structure": structure or "Undetermined — IV and contract data required",
        "rationale": (f"{structure} fits the supplied {thesis.get('direction', 'directional').lower()} thesis and risk objective."
                      if structure else
                      "Reliable IV and contract data are required before selecting an options structure."),
        "action": action,
        "options_final_score": option_score,
        "iv_rank": iv_rank,
        "expected_move_pct": expected_move,
        "liquidity": liquidity,
        "expiration_logic": expiration_logic,
        "strike_logic": strike_logic,
        "horizon": f"{horizon:g} days" if horizon is not None else "Missing",
        **economics,
        "gates": gates,
        "missing_requirements": missing,
        "key_risks": risks,
        "data_as_of": option_data.get("as_of"),
    }


def build_options_strategy(ai_radar=None, growth_radar=None, biotech_radar=None,
                           crypto_radar=None, high_conviction=None, swing_section=None,
                           option_market_data=None, ownership=None, limit=8):
    theses = collect_directional_theses(
        ai_radar, growth_radar, biotech_radar, crypto_radar, high_conviction, swing_section)
    option_market_data = option_market_data or {}
    ownership = ownership or {}
    assessed = [assess_options_candidate(
        thesis, option_market_data.get(thesis["ticker"]), ownership.get(thesis["ticker"]))
                for thesis in theses]
    assessed.sort(key=lambda row: (
        row["options_final_score"] is None,
        -(row.get("options_final_score") or -1),
        row["action"] != "ACTION",
        not row.get("thesis_confirmed"),
        -(row.get("directional_score") or -1), row["ticker"]))
    displayed = assessed[:limit]
    rank = 0
    for row in displayed:
        if row["options_final_score"] is not None:
            rank += 1
            row["options_final_rank"] = rank
        else:
            row["options_final_rank"] = None
    action_count = sum(row["action"] == "ACTION" for row in assessed)
    ranked_count = sum(row["options_final_score"] is not None for row in assessed)
    return {
        "methodology": {
            "engine_version": "options-strategy-v1",
            "primary_references": ["Lawrence G. McMillan — Options as a Strategic Investment",
                                   "Brian Overby — The Options Playbook",
                                   "T. Ayers Pelz — The Biotech Trader Handbook, 2nd Edition"],
            "strategy_logic": "Existing Directional Thesis → Horizon / Catalyst → IV / Expected Move → Liquidity / Spread → Defined Contract → Risk / Reward → Action.",
            "independence": "Options consumes existing strategy theses and never discovers, promotes, or re-ranks stocks in Radar, Growth, Biotech, Crypto, High Conviction, or Swing Trade.",
            "missing_data_policy": "Missing IV, expected move, liquidity/spread, expiry, strikes, premium, timing, or thesis confirmation produces WAIT / No recommendation; missing values never become positive evidence.",
            "ownership_policy": "Covered calls require at least 100 confirmed shares; protective puts require confirmed ownership. Browser-owned positions are not inferred by the server generator.",
            "ranking_policy": "Options Final Rank exists only when reliable option-market inputs support a risk-adjusted score. Unscored directional theses may remain visible as unranked WAIT assessments.",
            "code_attribution": "GeneDr Network implementation informed by common principles in the cited references; strategy routing, thresholds, scores, gates, and calculations are original and are not the authors' formulas.",
        },
        "reasoning": [
            "Options is a downstream risk-structure layer, not a stock-selection engine.",
            "Defined-risk structures require verified IV, expected move, selected-leg liquidity, expiry, strikes, premium, breakeven, and reward/risk.",
            "No contract is recommended from stock direction alone; missing chain data remains missing and forces WAIT.",
        ],
        "take_home_messages": [
            f"{len(theses)} existing public-equity directional theses were evaluated; no new ticker was discovered by Options.",
            f"{ranked_count} have sufficient option-market data for Options Final Rank; {action_count} pass every Action gate.",
            "Covered calls and protective puts require confirmed ownership; browser-only positions are never assumed.",
        ],
        "assessments": displayed,
        "coverage": {"directional_theses": len(theses), "evaluated": len(assessed),
                     "ranked": ranked_count, "actionable": action_count,
                     "displayed": len(displayed), "display_limit": limit},
    }
