import unittest
from pathlib import Path

from scripts.update_news_dashboard import watch_rows


ROOT = Path(__file__).resolve().parents[1]


class WatchlistWorkflowTests(unittest.TestCase):
    def test_curated_watchlist_rows_are_explicit_manual_selections(self):
        rows = watch_rows([
            ("Example Co", "TEST", "Technology", "Selected reason", "Catalyst", "Mid Cap", "High", "Medium")
        ])
        self.assertEqual(rows[0]["watchlist_source"], "Manual")

    def test_updater_declares_persistent_user_selection_policy(self):
        updater = (ROOT / "scripts" / "update_news_dashboard.py").read_text()
        self.assertIn('"watchlist_policy"', updater)
        self.assertIn("persist independently of daily JSON refreshes", updater)
        self.assertIn("Radar membership alone never automatically adds", updater)

    def test_frontend_has_all_four_sources_and_no_duplicate_quote_provider(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        for source in ("Radar", "High Conviction", "Swing Trade", "Manual"):
            self.assertIn(source, script)
        self.assertIn("WATCHLIST_STORAGE_KEY", script)
        self.assertIn("sharedMarketSecurities", script)
        self.assertNotIn("fetch(\"https://query", script)


if __name__ == "__main__":
    unittest.main()
