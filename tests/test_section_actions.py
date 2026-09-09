import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SectionSpecificActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / "assets" / "news-dashboard.js").read_text()
        cls.generator = (ROOT / "scripts" / "update_news_dashboard.py").read_text()
        cls.page = (ROOT / "programs" / "genedrnews.html").read_text()

    def body(self, name, next_name):
        return self.script.split(f"function {name}", 1)[1].split(f"function {next_name}", 1)[0]

    def test_radar_actions_use_distinct_domain_inputs(self):
        self.assertIn("function decisionNumber", self.script)
        self.assertIn('value === null || value === undefined || value === ""', self.script)
        ai = self.body("aiRadarAction", "biotechRadarAction")
        biotech = self.body("biotechRadarAction", "cryptoRadarAction")
        crypto = self.body("cryptoRadarAction", "renderAiRadar")
        for value in ("bottleneck_opportunity_score", "multibagger_potential_score", "already_priced_in", "WAIT FOR PULLBACK", "DO NOT CHASE"):
            self.assertIn(value, ai)
        for value in ("binary_risk", "evidence_gate", "evidence_integrity_gate", "cash_runway_dilution", "probability_of_success", "WAIT FOR CATALYST", "SMALL POSITION"):
            self.assertIn(value, biotech)
        for value in ("crypto_opportunity_score", "relative_strength?.btc", "multibagger_potential_score", "WAIT FOR PULLBACK", "DO NOT CHASE"):
            self.assertIn(value, crypto)

    def test_high_conviction_uses_confirmation_mountain_and_entry_quality(self):
        body = self.body("highConvictionAction", "renderHighConvictionDecision")
        for value in ("market_confirmation", "mountain_position", "entry_quality", "remaining_upside", "Confirmed Early", "Lower Mountain", "Upper Mountain", "Extended"):
            self.assertIn(value, body)
        self.assertIn('mountain === "Lower Mountain"', body)
        self.assertIn('return "SCALE IN"', body)

    def test_reacceleration_retains_its_existing_alert_action(self):
        self.assertIn("alert.action || \"WATCH\"", self.script)
        for value in ('"Bottoming": "WATCH"', '"Entry Zone": "BUY / SCALE IN"', '"Extended": "DO NOT CHASE"'):
            self.assertIn(value, self.generator)

    def test_swing_action_uses_technical_catalyst_and_risk_reward(self):
        body = self.body("swingTradeAction", "renderSwingTrades")
        for value in ("catalyst?.credible", "support", "resistance", "riskReward", "Failed Reversal", "Technical Deterioration", "ENTER ON BREAKOUT", "STOP OUT"):
            self.assertIn(value, body)

    def test_watchlist_action_uses_shared_readiness_not_source(self):
        body = self.body("watchlistDecisionAction", "renderWatchlistCard")
        for value in ("buy_status", "entry_timing_state", "extended", "DATA UNAVAILABLE", "WAIT FOR PULLBACK", "DO NOT CHASE"):
            self.assertIn(value, body)
        self.assertNotIn("Manual", body)

    def test_pending_order_action_uses_order_specific_decision_fields(self):
        body = self.body("pendingOrderAnalysis", "renderPendingOrderCard")
        for value in ("technicallyFalling", "riskReward", "limitRecommendation", "otocoIncomplete", "LOWER LIMIT", "RAISE LIMIT", "CANCEL / REASSESS"):
            self.assertIn(value, body)
        self.assertIn("${escapeHtml(row.action)}", self.body("renderPendingOrderCard", "renderPendingOrders"))

    def test_owned_positions_keep_position_management_vocabulary(self):
        body = self.body("positionStatus", "positionDaysHeld")
        returned = set(re.findall(r'return "([A-Z ]+)"', body))
        self.assertEqual(returned, {"HOLD", "ADD", "TRIM", "TAKE PROFIT", "EXIT"})
        position_render = self.body("renderPositionCard", "renderPositions")
        self.assertIn("<small>Action</small>", position_render)
        self.assertIn("<dt>Action</dt>", position_render)

    def test_action_is_placed_next_to_entry_context(self):
        self.assertEqual(self.page.count("Entry Stage / Action"), 3)
        self.assertGreaterEqual(self.script.count("decision-action-label"), 7)


if __name__ == "__main__":
    unittest.main()
