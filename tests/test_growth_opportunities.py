import unittest

from scripts.growth_opportunities import (
    build_growth_opportunities,
    select_growth_deep_analysis_universe,
    select_growth_market_universe,
)


def listed(ticker, sector="Industrials", **overrides):
    row = {"company": ticker, "ticker": ticker, "exchange": "NASDAQ",
           "listing_status": "Public", "sector": sector, "industry": "Services",
           "last_price": 50, "daily_volume": 500_000, "market_cap": 2_000_000_000}
    row.update(overrides)
    return row


def snapshot(confirmed=True):
    return {
        "current_price": 100, "price_date": "2026-09-11", "data_status": "current",
        "moving_averages": {"ma20": 98, "ma50": 95, "ma200": 80},
        "returns": {"one_month": 6, "three_month": 15, "six_month": 25},
        "relative_strength": {"sp500": {"one_month": 4, "three_month": 8, "six_month": 12}},
        "macd": {"histogram": .3 if confirmed else -.1, "improving": confirmed,
                 "crossover": "bullish" if confirmed else None},
        "entry_inputs": {"base_duration_sessions": 63 if confirmed else None,
                         "base_range_pct": 15 if confirmed else None,
                         "tight_range_20d_pct": 8, "volume_contraction_ratio": .8,
                         "up_down_volume_ratio_20d": 1.2,
                         "higher_low_confirmed": confirmed, "ma20_slope_10d_pct": 2,
                         "breakout_proximity_pct": 2, "breakout_volume_ratio": 1.4,
                         "invalidation_level": 94},
        "expectation_data": {
            "data_status": "current", "available_input_groups": ["valuation", "analyst_consensus"],
            "valuation": {"target_upside_pct": 25},
            "analyst_consensus": {"net_revisions_4w": 3}, "sources": [],
        },
    }


def quality(ticker, score=80):
    return {
        "ticker": ticker, "domain": "growth", "company_quality_score": score,
        "data_completeness": 80, "data_status": "current", "confidence": "High",
        "components": [
            {"key": "revenue_growth", "score": 90},
            {"key": "earnings_growth", "score": 85},
            {"key": "margin_trend", "score": 80},
            {"key": "balance_sheet", "score": 80},
        ],
        "metrics": {
            "revenue_growth": {"value": 25}, "earnings_growth": {"value": 30},
            "margin_trend": {"value": 2}, "free_cash_flow": {"value": 100},
            "net_cash": {"value": 50},
        },
        "sources": [],
    }


class GrowthOpportunitiesTests(unittest.TestCase):
    def test_broad_screen_reports_full_scan_and_excludes_specialized_tickers(self):
        rows = [listed("AI"), listed("GROW"), listed("ILLIQ", daily_volume=10)]
        selected, diagnostics = select_growth_market_universe(rows, {"AI"}, limit=10)
        self.assertEqual([row["ticker"] for row in selected], ["GROW"])
        self.assertEqual(diagnostics["total_stocks_scanned"], 3)
        self.assertEqual(diagnostics["initial_screen_pass"], 1)
        self.assertEqual(diagnostics["rejection_counts"]["specialized_group"], 1)

    def test_dynamic_rank_is_independent_of_action_pool_label(self):
        candidates = [listed("ACTION"), listed("WAIT")]
        action_snapshot = snapshot(True)
        action_snapshot["expectation_data"]["valuation"]["target_upside_pct"] = 10
        action_snapshot["expectation_data"]["analyst_consensus"]["net_revisions_4w"] = 0
        action_snapshot["relative_strength"]["sp500"] = {
            "one_month": 0, "three_month": 0, "six_month": 0}
        action_snapshot["entry_inputs"]["up_down_volume_ratio_20d"] = 1
        wait_snapshot = snapshot(True)
        wait_snapshot["entry_inputs"]["breakout_volume_ratio"] = 1.0
        wait_snapshot["expectation_data"]["valuation"]["target_upside_pct"] = 30
        action_quality = quality("ACTION", 65)
        for component in action_quality["components"]:
            if component["key"] in ("revenue_growth", "earnings_growth", "margin_trend"):
                component["score"] = 65
        action_quality["metrics"]["earnings_growth"]["value"] = 5
        market = {"securities": {"ACTION": action_snapshot, "WAIT": wait_snapshot}}
        qualities = {"records": {"growth:ACTION": action_quality,
                                  "growth:WAIT": quality("WAIT", 100)}}
        rows, diagnostics = build_growth_opportunities(candidates, market, qualities)
        self.assertEqual(rows[0]["ticker"], "WAIT")
        self.assertEqual(rows[0]["pool"], "Discovery Pool")
        self.assertEqual(rows[1]["pool"], "Action Pool")
        self.assertGreater(rows[0]["dynamic_final_score"], rows[1]["dynamic_final_score"])
        self.assertEqual(diagnostics["action_pool_count"], 1)
        self.assertEqual([row["dynamic_final_rank"] for row in rows], [1, 2])

    def test_market_screen_reserves_an_emerging_company_lane(self):
        rows = [listed(f"LARGE{i}", market_cap=20_000_000_000,
                       daily_volume=2_000_000 - i * 10_000) for i in range(10)]
        rows += [listed(f"SMALL{i}", market_cap=1_000_000_000,
                        daily_volume=200_000 - i * 1_000) for i in range(5)]
        selected, diagnostics = select_growth_market_universe(rows, limit=8)
        selected_tickers = {row["ticker"] for row in selected}
        self.assertEqual(len(selected), 8)
        self.assertEqual(diagnostics["emerging_lane_target"], 2)
        self.assertEqual(diagnostics["emerging_lane_selected"], 2)
        self.assertTrue({"SMALL0", "SMALL1"}.issubset(selected_tickers))

    def test_deep_analysis_pool_is_selected_from_technical_patterns(self):
        candidates = [listed("GOOD"), listed("FALL")]
        falling = snapshot(False)
        falling.update({"current_price": 70,
                        "moving_averages": {"ma20": 75, "ma50": 80, "ma200": 90},
                        "macd": {"histogram": -.5, "improving": False}})
        selected, diagnostics = select_growth_deep_analysis_universe(
            candidates, {"securities": {"GOOD": snapshot(True), "FALL": falling}}, limit=120)
        self.assertEqual([row["ticker"] for row in selected], ["GOOD"])
        self.assertEqual(diagnostics["market_data_shortlist"], 1)
        self.assertEqual(diagnostics["rejection_counts_technical"]["technical_gate"], 1)

    def test_no_actionable_candidate_is_not_promoted(self):
        candidates = [listed("WAIT")]
        rows, diagnostics = build_growth_opportunities(
            candidates, {"securities": {"WAIT": snapshot(False)}},
            {"records": {"growth:WAIT": quality("WAIT")}})
        self.assertEqual(diagnostics["action_pool_count"], 0)
        self.assertEqual(rows[0]["action"], "WATCH / WAIT FOR CONFIRMATION")

    def test_action_requires_relative_strength_and_favorable_reward_risk(self):
        weak_rs = snapshot(True)
        weak_rs["relative_strength"]["sp500"] = {
            "one_month": -10, "three_month": -8, "six_month": -6}
        poor_reward = snapshot(True)
        poor_reward["expectation_data"]["valuation"]["target_upside_pct"] = 5
        rows, diagnostics = build_growth_opportunities(
            [listed("WEAKRS"), listed("POORRR")],
            {"securities": {"WEAKRS": weak_rs, "POORRR": poor_reward}},
            {"records": {"growth:WEAKRS": quality("WEAKRS"),
                         "growth:POORRR": quality("POORRR")}})
        self.assertEqual(diagnostics["action_pool_count"], 0)
        self.assertTrue(all(row["pool"] == "Discovery Pool" for row in rows))
        by_ticker = {row["ticker"]: row for row in rows}
        self.assertLess(by_ticker["WEAKRS"]["relative_strength_score"], 60)
        self.assertLess(by_ticker["POORRR"]["reward_risk_ratio"], 1.5)

    def test_growth_methodology_is_presented_next_to_growth_section(self):
        with open("programs/genedrnews.html", encoding="utf-8") as handle:
            page = handle.read()
        growth_start = page.index('id="growth-radar-title"')
        biotech_start = page.index('id="biotech-radar-title"')
        growth_section = page[growth_start:biotech_start]
        self.assertIn("Jesse Stine", growth_section)
        self.assertIn("Philip Fisher", growth_section)
        self.assertIn("Dynamic Final Rank", growth_section)


if __name__ == "__main__":
    unittest.main()
