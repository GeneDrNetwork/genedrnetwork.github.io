"""Broad-universe Growth Opportunities Radar built on existing dashboard data sources."""

from __future__ import annotations

import math

try:
    from .strategy_technical import dynamic_alignment_score, radar_base_breakout_setup
except ImportError:
    from strategy_technical import dynamic_alignment_score, radar_base_breakout_setup


GROWTH_TECHNICAL_SCAN_LIMIT = 360
GROWTH_DEEP_ANALYSIS_LIMIT = 120
GROWTH_DISPLAY_LIMIT = 12


def _number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def _bounded(value):
    return None if value is None else max(0, min(100, round(value)))


def _band(value, bands):
    if value is None:
        return None
    return next(score for minimum, score in bands if value >= minimum)


def select_growth_market_universe(listed_companies, excluded_tickers=None,
                                  limit=GROWTH_TECHNICAL_SCAN_LIMIT, fallback_rows=None):
    """Apply the inexpensive investability screen and bound price-history requests."""
    excluded = {str(ticker or "").upper() for ticker in (excluded_tickers or [])}
    eligible = []
    rejection_counts = {"specialized_group": 0, "price": 0, "market_cap": 0,
                        "liquidity": 0, "classification": 0}
    for company in listed_companies or []:
        ticker = str(company.get("ticker") or "").upper()
        if ticker in excluded:
            rejection_counts["specialized_group"] += 1
            continue
        price = _number(company.get("last_price"))
        market_cap = _number(company.get("market_cap"))
        volume = _number(company.get("daily_volume"))
        if price is None or price < 3:
            rejection_counts["price"] += 1
            continue
        if market_cap is None or market_cap < 300_000_000:
            rejection_counts["market_cap"] += 1
            continue
        if volume is None or volume < 100_000 or price * volume < 2_000_000:
            rejection_counts["liquidity"] += 1
            continue
        if not company.get("sector") or not company.get("industry"):
            rejection_counts["classification"] += 1
            continue
        eligible.append({**company, "domain": "growth", "listing_status": "Public",
                         "dollar_volume_proxy": round(price * volume, 2)})

    # Keep deeper requests bounded while sampling liquid candidates across sectors.
    by_sector = {}
    for row in sorted(eligible, key=lambda item: (-item["dollar_volume_proxy"],
                                                  -(item.get("market_cap") or 0), item["ticker"])):
        by_sector.setdefault(row.get("sector") or "Unclassified", []).append(row)
    selected = []
    sector_index = 0
    sectors = sorted(by_sector)
    while len(selected) < limit and sectors:
        sector = sectors[sector_index % len(sectors)]
        rows = by_sector[sector]
        if rows:
            selected.append(rows.pop(0))
        sectors = [name for name in sectors if by_sector[name]]
        sector_index += 1

    if not selected and fallback_rows:
        selected = [{key: row.get(key) for key in
                     ("company", "ticker", "exchange", "listing_status", "sector", "industry",
                      "market_cap", "last_price", "daily_volume")}
                    | {"domain": "growth", "fallback_from_previous": True}
                    for row in fallback_rows if str(row.get("ticker") or "").upper() not in excluded][:limit]
    return selected, {
        "total_stocks_scanned": len(listed_companies or []),
        "initial_screen_pass": len(eligible),
        "technical_scan_candidates": len(selected),
        "initial_screen": "Operating U.S.-listed common stock; price >= $3; market cap >= $300M; daily volume >= 100K; dollar-volume proxy >= $2M; sector and industry present.",
        "technical_scan_sampling": "Up to 360 liquid names are sampled round-robin by sector and ordered within each sector by dollar-volume proxy; only price/volume history is requested at this stage.",
        "rejection_counts": rejection_counts,
    }


def _technical_pattern_score(snapshot):
    """Rank auditable Radar-pattern domains without using company fundamentals."""
    setup = radar_base_breakout_setup(snapshot)
    inputs = (snapshot or {}).get("entry_inputs") or {}
    relative = _relative_strength_score(snapshot)
    proximity = _number(inputs.get("breakout_proximity_pct"))
    domains = [
        90 if setup.get("mature_base") else 25,
        90 if setup.get("volatility_contracted") else 45,
        90 if setup.get("higher_low_confirmed") else 35,
        90 if setup.get("primary_trend_confirmed") else 40,
        90 if proximity is not None and -10 <= proximity <= 5 else 45 if proximity is not None else None,
        relative,
    ]
    values = [value for value in domains if value is not None]
    return (round(sum(values) / len(values)) if values else None), setup


def select_growth_deep_analysis_universe(candidates, market_data,
                                         limit=GROWTH_DEEP_ANALYSIS_LIMIT):
    """Select the 120-stock fundamental-analysis pool from chart patterns first."""
    qualified = []
    rejection_counts = {"missing_or_stale_history": 0, "technical_gate": 0}
    for candidate in candidates or []:
        ticker = candidate.get("ticker")
        snapshot = ((market_data or {}).get("securities") or {}).get(ticker)
        if not snapshot or snapshot.get("data_status") != "current":
            rejection_counts["missing_or_stale_history"] += 1
            continue
        pattern_score, setup = _technical_pattern_score(snapshot)
        # This is a discovery-friendly gate, not the Action gate: developing bases
        # remain eligible, while broken, failed, unavailable, and extended charts do not.
        pattern_qualified = bool(
            pattern_score is not None and pattern_score >= 45 and
            not setup.get("falling") and not setup.get("failed_reversal") and
            not setup.get("unavailable") and not setup.get("extended") and
            (setup.get("mature_base") or setup.get("primary_trend_confirmed")))
        if not pattern_qualified:
            rejection_counts["technical_gate"] += 1
            continue
        qualified.append({**candidate, "technical_pattern_score": pattern_score,
                          "technical_pattern_stage": setup.get("stage")})
    qualified.sort(key=lambda row: (-row["technical_pattern_score"],
                                    -(_number(row.get("dollar_volume_proxy")) or 0), row["ticker"]))
    selected = qualified[:limit]
    return selected, {
        "technical_history_evaluated": len(candidates or []),
        "technical_pattern_pass": len(qualified),
        "market_data_shortlist": len(selected),
        "technical_pattern_screen": (
            "Requires current price history, no Falling/Failed Reversal/Unavailable/Extended gate, "
            "a mature 42/63-session base or confirmed rising short-term trend, and a >=45/100 "
            "pattern score across base, contraction, higher-low, primary trend/MA structure, pivot "
            "proximity, and S&P 500 relative strength. Fundamentals are not read until after this selection."),
        "rejection_counts_technical": rejection_counts,
    }


def _quality_metric(quality, key):
    return ((quality or {}).get("metrics", {}).get(key) or {}).get("value")


def _quality_component(quality, key):
    return next((item for item in (quality or {}).get("components", []) if item.get("key") == key), {})


def _growth_score(quality):
    values = []
    for key in ("revenue_growth", "earnings_growth", "margin_trend"):
        score = _quality_component(quality, key).get("score")
        if _number(score) is not None:
            values.append(score)
    return round(sum(values) / len(values)) if values else None


def _catalyst_score(snapshot, quality):
    expectation = (snapshot or {}).get("expectation_data") or {}
    revisions = (expectation.get("analyst_consensus") or {}).get("net_revisions_4w")
    revision_score = _band(revisions, [(3, 95), (1, 80), (0, 60), (-2, 35), (-math.inf, 15)])
    earnings_growth = _quality_metric(quality, "earnings_growth")
    earnings_score = _band(earnings_growth, [(30, 95), (15, 80), (5, 70), (0, 55), (-math.inf, 20)])
    values = [value for value in (revision_score, earnings_score) if value is not None]
    return (round(sum(values) / len(values)) if values else None,
            {"net_eps_revisions_4w": revisions, "reported_earnings_growth_pct": earnings_growth})


def _relative_strength_score(snapshot):
    relative = ((snapshot or {}).get("relative_strength") or {}).get("sp500", {})
    values = [relative.get(key) for key in ("one_month", "three_month", "six_month")]
    scores = [_band(value, [(15, 95), (8, 85), (3, 72), (0, 60), (-5, 40), (-math.inf, 15)])
              for value in values]
    scores = [score for score in scores if score is not None]
    return round(sum(scores) / len(scores)) if scores else None


def _upside_score(snapshot):
    target = (((snapshot or {}).get("expectation_data") or {}).get("valuation") or {}).get("target_upside_pct")
    return _band(target, [(30, 95), (20, 85), (10, 70), (0, 50), (-10, 25), (-math.inf, 10)])


def _weighted_score(parts):
    available = [(value, weight) for value, weight in parts if value is not None]
    if not available:
        return None, 0
    return (round(sum(value * weight for value, weight in available) /
                  sum(weight for _, weight in available)),
            round(sum(weight for _, weight in available)))


def build_growth_opportunities(candidates, market_data, quality_layer, previous_rows=None,
                               excluded_tickers=None, display_limit=GROWTH_DISPLAY_LIMIT):
    """Create distinct Discovery and Action pools, prioritizing Action in final rank."""
    excluded = {str(ticker or "").upper() for ticker in (excluded_tickers or [])}
    previous = {row.get("ticker"): row for row in (previous_rows or [])}
    evaluated = []
    market_screen_pass = 0
    for candidate in candidates or []:
        ticker = str(candidate.get("ticker") or "").upper()
        if not ticker or ticker in excluded:
            continue
        snapshot = ((market_data or {}).get("securities") or {}).get(ticker)
        quality = ((quality_layer or {}).get("records") or {}).get(f"growth:{ticker}")
        if not snapshot or snapshot.get("data_status") != "current":
            continue
        market_screen_pass += 1
        fundamental = (quality or {}).get("company_quality_score")
        growth = _growth_score(quality)
        catalyst, catalyst_inputs = _catalyst_score(snapshot, quality)
        relative = _relative_strength_score(snapshot)
        upside = _upside_score(snapshot)
        opportunity, completeness = _weighted_score([
            (fundamental, 30), (growth, 30), (catalyst, 15), (relative, 15), (upside, 10),
        ])
        setup = radar_base_breakout_setup(snapshot)
        balance = _quality_component(quality, "balance_sheet").get("score")
        risk_score = round(sum(value for value in (balance, 80 if setup.get("invalidation_level") is not None else 45)
                               if value is not None) /
                           len([value for value in (balance, 80 if setup.get("invalidation_level") is not None else 45)
                                if value is not None]))
        entry_score = (95 if setup.get("breakout_confirmed") else
                       65 if setup.get("confirmed_reversal") else
                       45 if setup.get("mature_base") else 20)
        dynamic = dynamic_alignment_score(opportunity, setup, entry_score, upside, risk_score)
        discovery = bool(
            opportunity is not None and opportunity >= 60 and fundamental is not None and fundamental >= 55 and
            (quality or {}).get("data_status") == "current" and (quality or {}).get("data_completeness", 0) >= 50 and
            ((growth is not None and growth >= 55) or (relative is not None and relative >= 60)))
        action = bool(
            discovery and opportunity >= 65 and fundamental >= 60 and setup.get("actionable") is True and
            not setup.get("falling") and not setup.get("failed_reversal") and not setup.get("extended") and
            ((growth is not None and growth >= 65) or (catalyst is not None and catalyst >= 65)))
        if not discovery:
            continue
        pool = "Action Pool" if action else "Discovery Pool"
        expectation = (snapshot.get("expectation_data") or {})
        risks = []
        if not action:
            risks.append(f"Technical entry is {setup.get('stage')}; confirmation is still required.")
        if catalyst is None or catalyst < 65:
            risks.append("A strong current earnings/revision catalyst is not yet confirmed.")
        if completeness < 100:
            risks.append(f"Growth score completeness is {completeness}%.")
        old = previous.get(ticker, {})
        evaluated.append({
            "company": candidate.get("company") or ticker, "ticker": ticker,
            "exchange": candidate.get("exchange") or "", "listing_status": "Public",
            "sector": candidate.get("sector") or "Missing", "industry": candidate.get("industry") or "Missing",
            "pool": pool, "actionable": action,
            "action": "ACTIONABLE REVIEW" if action else "WATCH / WAIT FOR CONFIRMATION",
            "opportunity_score": opportunity, "fundamental_quality_score": fundamental,
            "growth_acceleration_score": growth, "catalyst_growth_score": catalyst,
            "relative_strength_score": relative, "remaining_upside_score": upside,
            "dynamic_final_score": dynamic, "data_completeness": completeness,
            "strategy_technical_setup": setup,
            "market_data": {key: value for key, value in snapshot.items()
                            if key not in ("expectation_data", "entry_inputs")},
            "expectation": expectation,
            "reported_metrics": {key: _quality_metric(quality, key) for key in
                                 ("revenue_growth", "earnings_growth", "margin_trend", "free_cash_flow", "net_cash")},
            "catalyst_inputs": catalyst_inputs,
            "why_selected": (f"{candidate.get('company') or ticker} passed the broad-universe liquidity/data screen and "
                             f"has {opportunity}/100 combined growth opportunity quality with {relative if relative is not None else 'missing'}/100 relative strength."),
            "risk_unproven": " ".join(risks) or "No defined alignment gate is currently missing; monitor invalidation and new evidence.",
            "sources": [source for source in (quality or {}).get("sources", [])] + expectation.get("sources", []),
            "prior_dynamic_final_rank": old.get("dynamic_final_rank"),
        })
    evaluated.sort(key=lambda row: (not row["actionable"], -(row.get("dynamic_final_score") or -1),
                                    -(row.get("opportunity_score") or -1), row["ticker"]))
    displayed = evaluated[:display_limit]
    for rank, row in enumerate(displayed, 1):
        row["dynamic_final_rank"] = rank
        prior = row.get("prior_dynamic_final_rank")
        row["rank_movement"] = None if not isinstance(prior, int) else prior - rank
    return displayed, {
        "market_screen_pass": market_screen_pass,
        "opportunity_growth_screen_pass": len(evaluated),
        "discovery_pool_count": sum(not row["actionable"] for row in evaluated),
        "action_pool_count": sum(row["actionable"] for row in evaluated),
        "displayed_count": len(displayed),
        "display_limit": display_limit,
        "actionable_tickers": [row["ticker"] for row in evaluated if row["actionable"]],
        "discovery_tickers": [row["ticker"] for row in evaluated if not row["actionable"]],
        "ranking_policy": "Action Pool first, then Dynamic Final Score. Discovery candidates are never promoted into Action by opportunity quality alone.",
        "no_action_policy": "If Action Pool count is zero, the UI states that no current entry passed rather than manufacturing a BUY candidate.",
    }
