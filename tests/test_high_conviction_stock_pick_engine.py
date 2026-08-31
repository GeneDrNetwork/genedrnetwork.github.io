import unittest
from datetime import date

from scripts.update_news_dashboard import (
    BIOTECH_CATALYSTS,
    build_ai_stock_picks,
    build_biotech_stock_picks,
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
    def test_ai_pick_passes_all_gates_for_high_conviction(self):
        row = build_ai_stock_picks(ai_radar(), market_layer("NVDA"), [],
                                   quality_layer=quality_layer("ai", "NVDA"))[0]
        self.assertEqual(row["classification_key"], "high-conviction")
        self.assertGreaterEqual(row["final_score"], 80)
        self.assertEqual(row["data_completeness"], 100)
        self.assertTrue(all(gate["passed"] for gate in row["gates"]))

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
                              if factor["key"] == "long_term_outlook")["weight"], 5)
        self.assertNotIn("radar_conviction", {factor["key"] for factor in nvda["factor_scores"]})
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
            stock_pick_factor("business_quality", 80, "available"),
            stock_pick_factor("sustained_growth", 80, "available"),
            stock_pick_factor("profitability_cash_flow", 80, "available"),
            stock_pick_factor("financial_strength", 80, "available"),
            stock_pick_factor("competitive_advantage", 80, "available"),
            stock_pick_factor("long_term_outlook", 80, "available"),
            stock_pick_factor("valuation", None, "missing"),
        ]
        score, completeness = weighted_stock_pick_score(factors)
        self.assertEqual(score, 80)
        self.assertEqual(completeness, 95)


if __name__ == "__main__":
    unittest.main()
