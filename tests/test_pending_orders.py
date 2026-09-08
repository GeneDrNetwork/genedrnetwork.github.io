import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PendingOrderWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "programs" / "genedrnews.html").read_text()
        cls.script = (ROOT / "assets" / "news-dashboard.js").read_text()

    def test_section_sits_between_watchlist_and_my_stock(self):
        self.assertIn('href="#pending-orders">Pending Orders</a>', self.page)
        self.assertIn('id="pending-orders"', self.page)
        self.assertLess(self.page.index('id="my-stocks"'), self.page.index('id="pending-orders"'))
        self.assertLess(self.page.index('id="pending-orders"'), self.page.index('id="owned-stocks"'))

    def test_form_collects_only_order_inputs(self):
        for field in ("pending-order-ticker", "pending-order-limit-price", "pending-order-shares"):
            self.assertIn(f'id="{field}"', self.page)
        form = self.page.split('id="pending-order-form"', 1)[1].split('</form>', 1)[0]
        self.assertNotIn("purchase-date", form)
        self.assertNotIn("target-1", form)

    def test_orders_are_persistent_and_refresh_from_shared_market_data(self):
        self.assertIn("PENDING_ORDER_STORAGE_KEY", self.script)
        self.assertIn("initializePendingOrderState", self.script)
        self.assertIn("writePendingOrderState", self.script)
        self.assertIn("sharedMarketSecurities[order.ticker]", self.script)
        self.assertIn('renderSafely(() => renderPendingOrders(), "pending-order-cards")', self.script)
        self.assertNotIn('fetch("https://query', self.script)

    def test_risk_levels_use_existing_technical_inputs(self):
        for value in ("invalidation_level", "base_low", "recent_low_63d", "resistance_level", "atr_14"):
            self.assertIn(value, self.script)
        self.assertIn("max_loss", self.script)
        self.assertIn("potential_profit_1", self.script)
        self.assertIn("potential_profit_2", self.script)
        self.assertIn("risk_reward", self.script)

    def test_edit_delete_and_fill_handoff_are_wired(self):
        for action in ("data-pending-order-edit", "data-pending-order-remove", "data-pending-order-fill"):
            self.assertIn(action, self.script)
        self.assertIn("Filled — Move to My Stock", self.script)
        self.assertIn("pendingOrderTicker", self.script)
        self.assertIn("removePendingOrder(pendingOrderTicker, false)", self.script)
        self.assertIn("data-pending-order-prefill", self.script)


if __name__ == "__main__":
    unittest.main()
