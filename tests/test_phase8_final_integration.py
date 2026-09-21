import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase8FinalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / "assets" / "news-dashboard.js").read_text()
        cls.page = (ROOT / "programs" / "genedrnews.html").read_text()
        cls.data = json.loads((ROOT / "data" / "news-dashboard.json").read_text())

    def test_seven_strategy_surfaces_remain_independent(self):
        for section_id in (
            "ai-radar", "growth-radar", "biotech-radar", "crypto-radar",
            "opportunities", "swing-trades", "options-strategy",
        ):
            self.assertIn(f'id="{section_id}"', self.page)
        for renderer in (
            "renderAiRadar", "renderGrowthRadar", "renderBiotechRadar",
            "renderCryptoRadar", "renderOpportunities", "renderSwingTrades",
            "renderOptionsStrategy",
        ):
            self.assertIn(f"function {renderer}", self.script)

    def test_entry_ui_is_shared_without_inventing_missing_prices(self):
        helper = self.script.split("function entryIntegrationFields", 1)[1].split(
            "function renderAiRadar", 1)[0]
        for label in (
            "Entry Path", "Current Price", "Breakout Entry", "Pullback Entry",
            "Suggested Entry", "Invalidation", "Why Not Now", "Next Confirmation",
        ):
            self.assertIn(label, helper)
        self.assertIn("N/A / WAIT", helper)
        self.assertIn('entryIntegrationFields(beneficiary, "ai", action)', self.script)
        self.assertIn('entryIntegrationFields(row, "growth", row.action', self.script)
        self.assertIn('entryIntegrationFields(row, "biotech", action)', self.script)
        self.assertIn('entryIntegrationFields(row, "crypto", action)', self.script)

    def test_high_conviction_decision_overlay_preserves_rank_action_separation(self):
        body = self.script.split("function renderHighConvictionDecision", 1)[1].split(
            "function qualifiedHighConvictionRows", 1)[0]
        for label in (
            "Why High Conviction", "Why Now", "Market Confirmation",
            "Mountain Position", "Entry Quality", "Current Price", "Suggested Entry",
            "Remaining Upside", "Stop / Invalidation", "T1 / T2", "Action",
            "Entry Path", "Breakout Entry", "Pullback Entry", "Why Not Now",
            "Next Confirmation",
        ):
            self.assertIn(label, body)
        self.assertIn("Rank ≠ Action", body)
        action_body = self.script.split("function highConvictionAction", 1)[1].split(
            "function renderHighConvictionDecision", 1)[0]
        self.assertIn("row.action", action_body)
        self.assertNotIn("conviction_score", action_body)

    def test_options_without_verified_market_inputs_fail_closed(self):
        assessments = self.data["options_strategy"]["assessments"]
        checked = 0
        for row in assessments:
            if row.get("missing_requirements"):
                checked += 1
                self.assertEqual(row.get("action"), "WAIT")
                self.assertEqual(row.get("strategy"), "No recommendation")
                self.assertIsNone(row.get("options_final_score"))
                self.assertIsNone(row.get("options_final_rank"))
        self.assertGreater(checked, 0)

    def test_workflow_integrations_and_persistence_remain_present(self):
        for marker in (
            'id="watchlist-add-form"', 'id="pending-order-form"',
            'id="position-form"', 'id="radar-analyze-form"',
        ):
            self.assertIn(marker, self.page)
        for marker in (
            "localStorage", "tickerLink", "data-high-conviction-analysis-card",
            "renderPendingOrders", "renderPositions", "renderWatchlist",
        ):
            self.assertIn(marker, self.script)


if __name__ == "__main__":
    unittest.main()
