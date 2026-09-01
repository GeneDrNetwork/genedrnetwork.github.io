import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PositionManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "programs" / "genedrnews.html").read_text()
        cls.script = (ROOT / "assets" / "news-dashboard.js").read_text()

    def test_my_stock_is_a_separate_top_level_section(self):
        self.assertIn('href="#owned-stocks">My Stock</a>', self.page)
        self.assertIn('id="owned-stocks"', self.page)
        self.assertIn('id="my-stock-positions"', self.page)
        self.assertLess(self.page.index('id="my-stocks"'), self.page.index('id="owned-stocks"'))

    def test_position_form_captures_user_owned_fields_and_custom_targets(self):
        for field in ("position-ticker", "position-buy-price", "position-shares",
                      "position-purchase-date", "position-source", "position-target-1",
                      "position-target-2", "position-target-3"):
            self.assertIn(f'id="{field}"', self.page)
        self.assertIn("POSITION_STORAGE_KEY", self.script)
        self.assertIn("strategy_sources", self.script)
        self.assertIn("custom_targets", self.script)

    def test_watchlist_handoff_and_direct_entry_share_one_workflow(self):
        self.assertIn("data-position-prefill", self.script)
        self.assertIn("Bought / Move to My Stock", self.script)
        self.assertIn('positionForm.addEventListener("submit", savePositionForm)', self.script)
        self.assertIn("sharedMarketSecurities[ticker]", self.script)
        self.assertNotIn('fetch("https://query', self.script)

    def test_status_engine_uses_strategy_and_technical_context(self):
        for status in ("HOLD", "ADD / ADD ON PULLBACK", "TAKE PARTIAL PROFIT",
                       "TAKE PROFIT", "TIGHTEN STOP", "EXIT / THESIS BROKEN"):
            self.assertIn(status, self.script)
        self.assertIn("technical.extended", self.script)
        self.assertIn("evidence.explicit_broken", self.script)
        self.assertIn("up_down_volume_ratio_20d", self.script)

    def test_swing_targets_are_not_applied_to_high_conviction(self):
        self.assertIn("buy * 1.10", self.script)
        self.assertIn("buy * 1.15", self.script)
        self.assertIn("buy * 1.20", self.script)
        self.assertIn('evidence.requested.includes("Swing Trade")', self.script)
        self.assertIn('evidence.requested.includes("High Conviction")', self.script)
        self.assertIn("swing percentages are not applied", self.script)

    def test_stop_and_thesis_invalidation_are_distinct_and_positions_refresh(self):
        self.assertIn("Stop Loss vs Thesis Invalidation", self.script)
        self.assertIn("Technical Stop / Invalidation", self.script)
        self.assertIn("thesis_invalidation", self.script)
        self.assertIn("downside_from_current_pct", self.script)
        self.assertIn("downside_from_buy_pct", self.script)
        self.assertIn("renderPositions(data)", self.script)
        self.assertIn('renderSafely(() => renderPositions(data), "my-stock-positions")', self.script)


if __name__ == "__main__":
    unittest.main()
