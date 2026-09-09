import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PendingOrderWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "programs" / "genedrnews.html").read_text()
        cls.script = (ROOT / "assets" / "news-dashboard.js").read_text()
        cls.styles = (ROOT / "assets" / "news-dashboard.css").read_text()

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

    def test_suggested_entry_is_independent_and_can_require_waiting(self):
        for value in ("suggested_entry_low", "suggested_entry_high", "limit_difference",
                      "GOOD LIMIT", "LOWER LIMIT", "RAISE LIMIT", "WAIT"):
            self.assertIn(value, self.script)
        self.assertIn("technicallyFalling", self.script)
        self.assertIn("reversalConfirmed", self.script)
        self.assertIn("No technical entry recommended yet", self.script)
        self.assertIn("Limit vs Suggested Entry", self.script)

    def test_compact_summary_and_expanded_otoco_fields_are_present(self):
        for label in ("Current Price", "Your Limit", "Shares", "Entry Stage", "Order Status",
                      "Suggested Entry", "Stop Loss", "Target 1", "Target 2",
                      "Max Loss $", "Potential Profit $", "Risk / Reward",
                      "Entry reason:", "Stop reason:", "Target reason:"):
            self.assertIn(label, self.script)
        self.assertIn("pending-order-workflow", self.script)
        self.assertIn("OTOCO Recommendation", self.script)
        self.assertIn("grid-template-columns: minmax(110px,1fr) repeat(3,minmax(82px,.55fr))", self.styles)
        self.assertIn("word-break: normal", self.styles)
        self.assertIn("overflow-wrap: normal", self.styles)
        self.assertIn("flex-wrap: nowrap", self.styles)

    def test_edit_delete_and_fill_handoff_are_wired(self):
        for action in ("data-pending-order-edit", "data-pending-order-remove", "data-pending-order-fill"):
            self.assertIn(action, self.script)
        self.assertIn("Filled — Move to My Stock", self.script)
        self.assertIn("pendingOrderTicker", self.script)
        self.assertIn("removePendingOrder(pendingOrderTicker, false)", self.script)
        self.assertIn("data-pending-order-prefill", self.script)
        self.assertIn("Delete Pending Order", self.script)
        self.assertIn("window.confirm", self.script)
        self.assertIn("writePendingOrderState(); renderPendingOrders()", self.script)

    def test_remove_is_visible_in_summary_and_isolated_to_pending_storage(self):
        summary = self.script.split('class="pending-order-summary"', 1)[1].split('</summary>', 1)[0]
        self.assertIn("pending-order-summary-remove", summary)
        self.assertIn(">Remove</button>", summary)
        self.assertIn('aria-label="Remove ${escapeHtml(row.ticker)} from Pending Orders"', summary)

        remove_body = self.script.split("function removePendingOrder", 1)[1].split("const POSITION_STATUSES", 1)[0]
        self.assertIn("state.orders = state.orders.filter", remove_body)
        self.assertIn("writePendingOrderState()", remove_body)
        self.assertNotIn("writeWatchlistState", remove_body)
        self.assertNotIn("writePositionState", remove_body)
        self.assertNotIn("watchlistState", remove_body)
        self.assertNotIn("positionState", remove_body)

    def test_otoco_requires_complete_actionable_levels(self):
        self.assertIn("hasSuggestedEntry", self.script)
        self.assertIn("hasStop", self.script)
        self.assertIn("hasTarget", self.script)
        self.assertIn('otocoStatus === "READY"', self.script)
        for status in ("READY", "WAIT", "INCOMPLETE DATA"):
            self.assertIn(status, self.script)
        self.assertIn("Reference Resistance", self.script)
        self.assertIn("Unavailable — OTOCO is not ready", self.script)
        self.assertIn("row.actionable_otoco ? row.target_1 : null", self.script)


if __name__ == "__main__":
    unittest.main()
