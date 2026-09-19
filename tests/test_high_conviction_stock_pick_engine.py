import unittest
from datetime import date

from scripts.update_news_dashboard import (
    BIOTECH_CATALYSTS,
    HIGH_CONVICTION_FACTOR_WEIGHTS,
    attach_high_conviction_dynamic_score,
    build_ai_stock_picks,
    build_biotech_stock_picks,
    build_high_conviction_candidate_universe,
    high_conviction_rank_eligible,
    high_conviction_market_confirmation,
    proven_quality_factors,
    proven_quality_sort_key,
    stock_pick_factor,
    weighted_stock_pick_score,
)


def market_record(ticker, crowded=False):
    expectation = {
        "ticker": ticker, "data_status": "current", "available_input_groups": [
            "valuation", "price_run_up", "analyst_consensus", "positioning"],
        "valuation": {"target_upside_pct": -10 if crowded else 30, "forward_pe": 70 if crowded else 20},
        "price_run_up": {"three_month_pct": 40 if crowded else 5},
        "analyst_consensus": {"net_revisions_4w": -3 if crowded else 3},
        "short_interest": {"days_to_cover": 2, "change_from_prior_pct": 0}, "sources": [],
    }
    return {
        "ticker": ticker, "data_status": "current", "current_price": 100,
        "moving_averages": {"ma50": 90, "ma200": 80}, "macd": {"histogram": 1},
        "returns": {"three_month": 10}, "relative_strength": {
            "qqq": {"three_month": 5}, "xbi": {"three_month": 5}},
        "rsi_14": 60, "expectation_data": expectation,
    }


def market_layer(ticker, crowded=False):
    return {"securities": {ticker: market_record(ticker, crowded)}}


def quality_layer(domain, ticker):
    return {"records": {f"{domain}:{ticker}": {
        "company_quality_score": 90, "data_completeness": 100,
        "confidence": "High", "data_status": "current", "qualified": True, "sources": [],
        "metrics": {
            "revenue_growth": {"value": 20, "observations": [{"value": 120}, {"value": 100}]},
            "earnings_growth": {"value": 15, "observations": [{"value": 23}, {"value": 20}]},
            "margin_trend": {"value": 2, "observations": []},
            "net_income": {"value": 23, "observations": [{"value": 23}]},
            "free_cash_flow": {"value": 25, "observations": [{"value": 25}]},
        },
        "components": [
            {"key": "revenue_growth", "weight": 15, "available_weight": 15, "score": 90},
            {"key": "earnings_growth", "weight": 15, "available_weight": 15, "score": 85},
            {"key": "margin_trend", "weight": 15, "available_weight": 15, "score": 80},
            {"key": "free_cash_flow", "weight": 15, "available_weight": 15, "score": 90},
            {"key": "balance_sheet", "weight": 20, "available_weight": 20, "score": 90,
             "rationale": "Strong reported liquidity and net-cash position."},
        ],
    }}}


def ai_radar(ticker="NVDA"):
    event = {"event_id": "event-1", "event_date": "2026-08-28T12:00:00+00:00", "age_band": "fresh",
             "ticker": ticker, "company": "NVIDIA" if ticker == "NVDA" else ticker,
             "news_importance_score": 95, "new_information": "Company raised current AI infrastructure guidance.",
             "event_type": "Financial Results", "source_link": "https://example.com/source"}
    return [{"trend": "Compute", "trend_strength": 90, "confidence": "High", "data_completeness": 100,
             "evidence_count": 3,
             "risks": "A source-backed demand reversal would invalidate the thesis.",
             "confirming_evidence": [event], "mixed_evidence": [],
             "beneficiary_records": [{"company": "NVIDIA", "ticker": ticker, "exchange": "",
                 "listing_status": "Public", "category": "Bottleneck/Picks-and-Shovels",
                 "beneficiary_relevance": 90, "data_completeness": 100, "evidence_ids": ["event-1"],
                 "score_components": [{"label": "Competitive Moat", "weight": 15, "score": 12}]}]}]


def biotech_radar(binary_risk="High", status="Speculative Binary", integrity=False):
    source = next(item for item in BIOTECH_CATALYSTS if item["ticker"] == "BEAM")
    return {"company": source["company"], "ticker": source["ticker"], "program": source["program"],
            "indication": source["indication"], "catalyst": source["catalyst"],
            "expected_timing": source["expected_timing"], "scientific_evidence_score": 24,
            "confidence": "High", "opportunity_score": 88, "binary_risk": binary_risk,
            "opportunity_status": status, "risks": "Failure to reproduce the clinical signal invalidates the thesis.",
            "evidence_gate": {"passed": True},
            "evidence_integrity_gate": {"concern_identified": integrity},
            "confirming_evidence": [{"event_id": "bio-1"}],
            "score_components": [{"key": "catalyst_impact_company_sensitivity", "score": 14,
                                  "available_weight": 15}]}


class HighConvictionStockPickEngineTests(unittest.TestCase):
    def test_one_day_spike_alone_cannot_confirm_market_thesis(self):
        record = market_record("TEST")
        record["returns"] = {"daily": 25, "one_month": -8, "three_month": -12}
        record["macd"] = {"histogram": -1, "improving": False}
        record["relative_strength"]["qqq"] = {"one_month": -5, "three_month": -7}
        result = high_conviction_market_confirmation(record, "ai")
        self.assertFalse(result["confirmed"])
        self.assertNotIn("Daily", " ".join(result["evidence"]))

    def test_market_confirmation_controls_action_not_quality_rank(self):
        layer = market_layer("NVDA")
        record = layer["securities"]["NVDA"]
        record["current_price"] = 70
        record["moving_averages"] = {"ma20": 80, "ma50": 90, "ma200": 85}
        record["returns"] = {"daily": 15, "one_month": -8, "three_month": -12}
        record["macd"] = {"histogram": -1, "improving": False}
        record["relative_strength"]["qqq"] = {"one_month": -5, "three_month": -7}
        row = build_ai_stock_picks(ai_radar(), layer, [],
                                   quality_layer=quality_layer("ai", "NVDA"))[0]
        gate = next(gate for gate in row["gates"] if gate["key"] == "market_confirmation")
        self.assertFalse(gate["passed"])
        self.assertEqual(row["classification_key"], "high-conviction")
        self.assertFalse(row["actionable"])
        self.assertEqual(row["action"], "WAIT")

    def test_watch_setup_remains_ranked_without_becoming_actionable(self):
        self.assertTrue(high_conviction_rank_eligible("high-conviction"))
        self.assertTrue(high_conviction_rank_eligible("watch-setup"))
        for classification in ("too-early", "priced-in", "speculative-binary", "avoid"):
            self.assertFalse(high_conviction_rank_eligible(classification))

    def test_long_term_quality_rank_is_not_reordered_by_entry_position(self):
        base = {"classification_key": "high-conviction", "gates": [], "company_quality": {},
                "data_completeness": 100, "company": "Test", "market_confirmation": {"confirmed": True}}
        early = {**base, "final_score": 82, "dynamic_final_score": 82,
                 "market_confirmation": {"confirmed": True, "newly_confirmed": True},
                 "high_conviction_entry": {"mountain_position": "Confirmed Early", "entry_quality": "BEST ENTRY",
                                           "remaining_upside": {"percent": 30}}}
        extended = {**base, "final_score": 99, "dynamic_final_score": 99,
                    "high_conviction_entry": {"mountain_position": "Extended", "entry_quality": "DO NOT CHASE",
                                              "remaining_upside": {"percent": 50}}}
        self.assertLess(proven_quality_sort_key(extended), proven_quality_sort_key(early))

    def test_broad_market_candidate_can_enter_review_without_radar_membership(self):
        record = market_record("NEWC")
        record["domains"] = ["ai"]
        universe = build_high_conviction_candidate_universe(
            {"candidates": []}, {"securities": {"NEWC": record}}, [], [])
        candidate = next(row for row in universe if row["ticker"] == "NEWC")
        self.assertIn("Broad Market Confirmation Screen", candidate["high_conviction_sources"])

    def test_ai_pick_passes_all_gates_for_high_conviction(self):
        row = build_ai_stock_picks(ai_radar(), market_layer("NVDA"), [],
                                   quality_layer=quality_layer("ai", "NVDA"))[0]
        self.assertEqual(row["classification_key"], "high-conviction")
        self.assertGreaterEqual(row["final_score"], 80)
        self.assertEqual(row["data_completeness"], 80)
        self.assertTrue(all(gate["passed"] for gate in row["gates"]))
        self.assertEqual(row["strategy_technical_setup"]["engine"],
                         "High Conviction = Uptrend / Pullback / Continuation")
        self.assertEqual(row["dynamic_final_score"], row["final_score"])
        self.assertEqual(row["dynamic_final_rank"], 1)

    def test_total_score_cannot_override_expectation_gate(self):
        row = build_ai_stock_picks(ai_radar(), market_layer("NVDA", crowded=True), [],
                                   quality_layer=quality_layer("ai", "NVDA"))[0]
        self.assertGreaterEqual(row["final_score"], 70)
        self.assertFalse(next(gate for gate in row["gates"] if gate["key"] == "valuation")["passed"])
        self.assertEqual(row["classification_key"], "priced-in")

    def test_discovery_and_radar_proof_cannot_replace_company_quality_gate(self):
        row = build_ai_stock_picks(ai_radar(), market_layer("NVDA"), [])[0]
        gate = next(gate for gate in row["gates"] if gate["key"] == "proven_business")
        self.assertFalse(gate["passed"])
        self.assertEqual(row["classification_key"], "too-early")

    def test_radar_strength_does_not_replace_profitability(self):
        weak = quality_layer("ai", "NVDA")
        weak["records"]["ai:NVDA"]["metrics"]["net_income"]["value"] = -10
        weak["records"]["ai:NVDA"]["metrics"]["free_cash_flow"]["value"] = -5
        row = build_ai_stock_picks(ai_radar(), market_layer("NVDA"), [], quality_layer=weak)[0]
        self.assertEqual(ai_radar()[0]["trend_strength"], 90)
        self.assertFalse(next(gate for gate in row["gates"] if gate["key"] == "profitability")["passed"])
        self.assertEqual(row["classification_key"], "too-early")

    def test_radar_is_context_only_and_curated_companies_remain_independent_candidates(self):
        pool = {"candidates": [{"domain": "ai", "company": "NVIDIA", "ticker": "NVDA"}]}
        rows = build_ai_stock_picks(
            ai_radar(), market_layer("NVDA"), [{"company": "Broadcom"}],
            candidate_pool=pool, quality_layer=quality_layer("ai", "NVDA"))
        nvda = next(row for row in rows if row["ticker"] == "NVDA")
        self.assertEqual(next(factor for factor in nvda["factor_scores"]
                              if factor["key"] == "growth_runway")["weight"], 15)
        self.assertNotIn("radar_conviction", {factor["key"] for factor in nvda["factor_scores"]})
        self.assertNotIn("business_quality", {factor["key"] for factor in nvda["factor_scores"]})
        self.assertIn("AVGO", {row["ticker"] for row in rows})

    def test_news_importance_does_not_directly_set_catalyst_score(self):
        radar = ai_radar()
        radar[0]["confirming_evidence"][0]["news_importance_score"] = 1
        row = build_ai_stock_picks(radar, market_layer("NVDA"), [],
                                   quality_layer=quality_layer("ai", "NVDA"))[0]
        self.assertEqual(row["catalyst_evidence"]["score"], 95)
        self.assertIn("News Importance is not used", row["catalyst_evidence"]["score_basis"])

    def test_biotech_binary_gate_forces_speculative_classification(self):
        row = build_biotech_stock_picks([biotech_radar()], market_layer("BEAM"), [], date(2026, 8, 29))[0]
        self.assertEqual(row["classification_key"], "speculative-binary")
        self.assertFalse(next(gate for gate in row["gates"] if gate["key"] == "binary_integrity")["passed"])

    def test_integrity_or_broken_thesis_forces_avoid(self):
        row = build_biotech_stock_picks(
            [biotech_radar(binary_risk="Moderate", status="Thesis Broken", integrity=True)],
            market_layer("BEAM"), [], date(2026, 8, 29))[0]
        self.assertEqual(row["classification_key"], "avoid")

    def test_missing_factor_is_excluded_not_scored_as_zero(self):
        factors = [
            stock_pick_factor("moat_competitive_advantage", 80, "available"),
            stock_pick_factor("management_capital_allocation", None, "missing"),
            stock_pick_factor("earnings_cash_flow_quality", 80, "available"),
            stock_pick_factor("balance_sheet_strength", 80, "available"),
            stock_pick_factor("return_on_invested_capital", None, "missing"),
            stock_pick_factor("growth_runway", 80, "available"),
            stock_pick_factor("valuation_margin_of_safety", 80, "available"),
            stock_pick_factor("compounding_potential", None, "missing"),
            stock_pick_factor("downside_risk", None, "missing"),
        ]
        score, completeness = weighted_stock_pick_score(factors)
        self.assertEqual(score, 80)
        self.assertEqual(completeness, 80)

    def test_factor_model_has_distinct_domains_and_missing_inputs_stay_missing(self):
        self.assertEqual(sum(HIGH_CONVICTION_FACTOR_WEIGHTS.values()), 100)
        factors = proven_quality_factors(
            quality_layer("ai", "NVDA")["records"]["ai:NVDA"],
            90, 15, "Documented moat.", ["https://example.com/moat"],
            85, 5, "Documented runway.", ["https://example.com/runway"],
            {"score": 80, "maximum": 100, "coverage": 4,
             "rationale": "Fair value.", "sources": []})
        by_key = {factor["key"]: factor for factor in factors}
        for key in ("management_capital_allocation", "return_on_invested_capital",
                    "compounding_potential", "downside_risk"):
            self.assertTrue(by_key[key]["missing"])
            self.assertIsNone(by_key[key]["score"])
        self.assertNotIn("business_quality", by_key)

    def test_technical_setup_changes_action_but_not_dynamic_quality_score(self):
        base = {
            "classification_key": "high-conviction", "final_score": 91,
            "market_confirmation": {"confirmed": True},
            "catalyst_validation": {"valid": True}, "stop_invalidation": 80,
            "remaining_upside": {"percent": 20},
            "high_conviction_entry": {"mountain_position": "Confirmed Early"},
        }
        constructive = market_record("GOOD")
        constructive.update({
            "moving_averages": {"ma20": 99, "ma50": 95, "ma200": 85},
            "entry_inputs": {"ma50_slope_20d_pct": 3,
                             "higher_low_confirmed": True,
                             "short_term_high_reclaimed": True},
            "returns": {"one_month": 5, "three_month": 15},
        })
        weak = {**constructive, "current_price": 70,
                "moving_averages": {"ma20": 80, "ma50": 90, "ma200": 95}}
        good_row, weak_row = dict(base), dict(base)
        attach_high_conviction_dynamic_score(good_row, constructive)
        attach_high_conviction_dynamic_score(weak_row, weak)
        self.assertEqual(good_row["dynamic_final_score"], weak_row["dynamic_final_score"])
        self.assertNotEqual(good_row["actionable"], weak_row["actionable"])

    def test_frontend_exposes_confirmation_and_mountain_fields(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parents[1] / "assets" / "news-dashboard.js").read_text()
        self.assertIn("Market Confirmation", script)
        self.assertIn("Mountain Position", script)
        self.assertIn("Suggested Entry", script)

    def test_frontend_uses_canonical_ranked_output_and_backend_action(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parents[1] / "assets" / "news-dashboard.js").read_text()
        self.assertIn("function qualifiedHighConvictionRows(data, domain)", script)
        self.assertIn("data.high_conviction_engine?.qualified?.[domain]", script)
        self.assertIn("row.high_conviction_rank_eligible === true", script)
        self.assertNotIn("(row.gates || []).every((gate) => gate.passed === true)", script)
        self.assertIn("row.actionable === true", script)
        self.assertIn('qualifiedHighConvictionRows(data, "ai")', script)
        self.assertIn('qualifiedHighConvictionRows(data, "biotech")', script)

    def test_page_discloses_references_and_rank_action_separation(self):
        from pathlib import Path
        page = (Path(__file__).resolve().parents[1] / "programs" / "genedrnews.html").read_text()
        block = page.split('aria-label="High Conviction references and strategy logic"', 1)[1]
        for name in ("Warren Buffett", "Charlie Munger", "Benjamin Graham", "Peter Lynch",
                     "Philip Fisher", "Howard Marks"):
            self.assertIn(name, block)
        self.assertIn("Rank #1 may remain WAIT", block)


if __name__ == "__main__":
    unittest.main()
