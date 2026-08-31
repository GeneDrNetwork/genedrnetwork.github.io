import unittest
from pathlib import Path

from scripts.update_news_dashboard import build_strategy_watchlists, watch_rows


ROOT = Path(__file__).resolve().parents[1]


class WatchlistWorkflowTests(unittest.TestCase):
    def test_legacy_static_rows_are_not_marked_manual(self):
        rows = watch_rows([
            ("Example Co", "TEST", "Technology", "Selected reason", "Catalyst", "Mid Cap", "High", "Medium")
        ])
        self.assertNotIn("watchlist_source", rows[0])

    def test_strategy_watchlist_deduplicates_and_combines_sources(self):
        ai_radar = [{"trend": "Compute", "what_it_means": "Compute demand is expanding.",
                     "beneficiary_records": [{"company": "Example Co", "ticker": "TEST", "thesis_evidence": []}]}]
        biotech_radar = [{"company": "Bio Co", "ticker": "BIO", "program": "Drug A", "catalyst": "Readout",
                          "clinical_evidence": "Phase 2", "why_important": "Potentially material."}]
        monthly = {"ai": [{"company": "Example Co", "ticker": "TEST", "why_selected": "Quality company."}], "biotech": []}
        swing = {"opportunities": [{"company": "Example Co", "ticker": "TEST", "domain": "ai", "classification": "Entry Zone",
                                    "why_this_swing_trade_opportunity": {"why_chart_selected": "Early reversal.", "bottom_reversal_stage": "Entry Zone", "invalidation": "Lose support."},
                                    "catalyst": {"description": "Product event", "timing": "Soon"}}]}
        result = build_strategy_watchlists(ai_radar, biotech_radar, monthly, swing, {"securities": {}})
        test_rows = [row for row in result["ai"] if row["ticker"] == "TEST"]
        self.assertEqual(len(test_rows), 1)
        self.assertEqual(test_rows[0]["watchlist_sources"], ["Radar", "High Conviction", "Swing Trade"])
        self.assertEqual([row["ticker"] for row in result["biotech"]], ["BIO"])

    def test_updater_declares_persistent_user_selection_policy(self):
        updater = (ROOT / "scripts" / "update_news_dashboard.py").read_text()
        self.assertIn('"watchlist_policy"', updater)
        self.assertIn("Only genuine Manual Add entries persist", updater)
        self.assertIn("Strategy-derived membership is added, combined, and removed automatically", updater)

    def test_frontend_has_all_four_sources_and_no_duplicate_quote_provider(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        for source in ("Radar", "High Conviction", "Swing Trade", "Manual"):
            self.assertIn(source, script)
        self.assertIn("WATCHLIST_STORAGE_KEY", script)
        self.assertIn("LEGACY_WATCHLIST_STORAGE_KEY", script)
        self.assertIn("automaticWatchlistSelections", script)
        self.assertIn("manual_items", script)
        self.assertIn("sharedMarketSecurities", script)
        self.assertNotIn("fetch(\"https://query", script)


if __name__ == "__main__":
    unittest.main()
