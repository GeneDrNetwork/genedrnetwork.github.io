import unittest

from scripts.options_strategy import (
    assess_options_candidate,
    build_options_strategy,
    collect_directional_theses,
)


def thesis(**overrides):
    row = {
        "ticker": "TEST", "company": "Test Company", "direction": "Bullish",
        "horizon_days": 120, "directional_score": 82,
        "thesis_confirmed": True, "timing_confirmed": True,
        "source": "Growth Opportunities", "sources": ["Growth Opportunities"],
        "rationale": "Existing confirmed thesis.", "catalyst": None,
        "catalyst_days": None, "market_data": {},
        "risk_objective": "Defined-risk directional exposure",
    }
    row.update(overrides)
    return row


def option_data(**overrides):
    row = {
        "underlying_price": 100, "iv_rank": 30, "expected_move_pct": 20,
        "bid": 5, "ask": 5.4, "open_interest": 800, "contract_volume": 60,
        "expiration": "2026-12-18", "expiration_days": 90,
        "long_strike": 100, "premium_debit": 5,
        "as_of": "2026-09-20",
    }
    row.update(overrides)
    return row


class OptionsStrategyTests(unittest.TestCase):
    def test_missing_option_market_data_fails_closed(self):
        result = assess_options_candidate(thesis(), {})
        self.assertEqual(result["action"], "WAIT")
        self.assertEqual(result["strategy"], "No recommendation")
        self.assertIsNone(result["options_final_score"])
        self.assertIn("iv_available", result["missing_requirements"])
        self.assertIn("liquidity_spread", result["missing_requirements"])

    def test_low_iv_bullish_thesis_can_use_defined_risk_long_call(self):
        result = assess_options_candidate(thesis(), option_data())
        self.assertEqual(result["candidate_structure"], "Long Call")
        self.assertEqual(result["strategy"], "Long Call")
        self.assertEqual(result["action"], "ACTION")
        self.assertEqual(result["max_risk"], 500)
        self.assertEqual(result["breakeven"], 105)
        self.assertEqual(result["estimated_reward_risk_ratio"], 3)

    def test_high_iv_uses_bull_call_vertical(self):
        result = assess_options_candidate(thesis(), option_data(
            iv_rank=70, long_strike=100, short_strike=115, premium_debit=5))
        self.assertEqual(result["strategy"], "Bull Call Spread")
        self.assertEqual(result["max_risk"], 500)
        self.assertEqual(result["max_reward"], 1000)
        self.assertEqual(result["breakeven"], 105)

    def test_bearish_thesis_supports_put_vertical(self):
        result = assess_options_candidate(thesis(direction="Bearish"), option_data(
            iv_rank=65, long_strike=100, short_strike=85, premium_debit=5))
        self.assertEqual(result["strategy"], "Bear Put Spread")
        self.assertEqual(result["max_reward"], 1000)
        self.assertEqual(result["breakeven"], 95)

    def test_illiquid_contract_never_receives_action(self):
        result = assess_options_candidate(thesis(), option_data(
            bid=1, ask=2, open_interest=20, contract_volume=1))
        self.assertEqual(result["action"], "WAIT")
        self.assertEqual(result["strategy"], "No recommendation")
        self.assertIn("liquidity_spread", result["missing_requirements"])

    def test_unconfirmed_stock_timing_never_becomes_options_action(self):
        result = assess_options_candidate(
            thesis(thesis_confirmed=False, timing_confirmed=False), option_data())
        self.assertEqual(result["action"], "WAIT")
        self.assertIn("directional_thesis", result["missing_requirements"])
        self.assertIn("technical_timing", result["missing_requirements"])

    def test_ownership_routes_protective_put_and_covered_call(self):
        protective = assess_options_candidate(
            thesis(), option_data(iv_rank=50, long_strike=95, premium_debit=2,
                                  estimated_reward_risk_ratio=2),
            {"shares": 100, "cost_basis": 100, "risk_objective": "Protect downside"})
        self.assertEqual(protective["strategy"], "Protective Put")
        self.assertEqual(protective["max_risk"], 700)

        covered = assess_options_candidate(
            thesis(), option_data(iv_rank=50, long_strike=None, short_strike=110,
                                  premium_debit=None, premium_credit=3,
                                  estimated_reward_risk_ratio=1.2),
            {"shares": 100, "cost_basis": 100, "risk_objective": "Income"})
        self.assertEqual(covered["strategy"], "Covered Call")
        self.assertEqual(covered["breakeven"], 97)

    def test_front_rich_term_structure_supports_calendar_or_diagonal(self):
        calendar = assess_options_candidate(
            thesis(horizon_days=180), option_data(
                term_structure="front_rich", same_strike_calendar=True,
                expiration=None, expiration_days=None, near_expiration="2026-11-20",
                far_expiration="2027-03-19", far_expiration_days=180,
                premium_debit=3, estimated_reward_risk_ratio=1.5))
        self.assertEqual(calendar["strategy"], "Call Calendar")
        self.assertEqual(calendar["max_risk"], 300)

    def test_collection_only_uses_existing_public_equity_rows(self):
        growth = [{"ticker": "GROW", "company": "Grow", "listing_status": "Public",
                   "dynamic_final_score": 80, "actionable": True, "market_data": {}}]
        crypto = [{"ticker": "BTC-USD", "company": "Bitcoin", "asset_type": "Native Crypto",
                   "dynamic_final_score": 90, "actionable": True}]
        rows = collect_directional_theses(growth_radar=growth, crypto_radar=crypto)
        self.assertEqual([row["ticker"] for row in rows], ["GROW"])

    def test_rank_exists_only_when_option_inputs_are_sufficient(self):
        growth = [{"ticker": "GROW", "company": "Grow", "listing_status": "Public",
                   "dynamic_final_score": 80, "actionable": True, "market_data": {}}]
        section = build_options_strategy(
            growth_radar=growth, option_market_data={"GROW": option_data()})
        self.assertEqual(section["coverage"]["ranked"], 1)
        self.assertEqual(section["assessments"][0]["options_final_rank"], 1)
        self.assertEqual(section["assessments"][0]["action"], "ACTION")

    def test_confirmed_thesis_leads_unranked_wait_assessments(self):
        growth = [
            {"ticker": "WAIT", "company": "Wait", "listing_status": "Public",
             "dynamic_final_score": 95, "actionable": False, "market_data": {}},
            {"ticker": "READY", "company": "Ready", "listing_status": "Public",
             "dynamic_final_score": 70, "actionable": True, "market_data": {}},
        ]
        section = build_options_strategy(growth_radar=growth)
        self.assertEqual(section["assessments"][0]["ticker"], "READY")
        self.assertEqual(section["assessments"][0]["action"], "WAIT")
        self.assertIsNone(section["assessments"][0]["options_final_rank"])

    def test_options_ui_and_references_are_present(self):
        with open("programs/genedrnews.html", encoding="utf-8") as handle:
            page = handle.read()
        with open("assets/news-dashboard.js", encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn('id="options-strategy"', page)
        self.assertIn("Lawrence G. McMillan", page)
        self.assertIn("Brian Overby", page)
        self.assertIn("renderOptionsStrategy", script)
        self.assertIn("data.options_strategy", script)


if __name__ == "__main__":
    unittest.main()
