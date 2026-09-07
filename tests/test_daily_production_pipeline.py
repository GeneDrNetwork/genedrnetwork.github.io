import json
import tempfile
import unittest
from pathlib import Path

from scripts.update_news_dashboard import (market_data_through, validate_production_data,
                                           write_production_data)


ROOT = Path(__file__).resolve().parents[1]


def valid_payload():
    return {
        "updated_at": "2026-09-01T23:17:00+00:00",
        "market_data_through": "2026-09-01",
        "market_data": {
            "securities": {"TEST": {"current_price": 10, "price_date": "2026-09-01", "data_status": "current"}},
            "indexes": {"^GSPC": {"current_price": 100, "price_date": "2026-09-01", "data_status": "current"}},
        },
        "top_investment_news": {
            "ai_technology": {"stories": [{"headline": "AI event"}], "important_news_archive": []},
            "biotech_healthcare": {"stories": [{"headline": "Biotech event"}], "important_news_archive": []},
        },
        "radar": {"ai": [{"trend": "Compute", "beneficiary_records": []}],
                  "biotech": [{"ticker": "BIO"}]},
        "monthly_picks": {"ai": [], "biotech": []},
        "watchlists": {"ai": [], "biotech": []},
        "swing_trade_opportunities": {"opportunities": []},
        "commentary": {},
    }


class DailyProductionPipelineTests(unittest.TestCase):
    def test_market_data_through_prefers_latest_current_trading_date(self):
        layer = {"securities": {
            "OLD": {"price_date": "2026-08-29", "data_status": "stale"},
            "NEW": {"price_date": "2026-09-01", "data_status": "current"},
        }, "indexes": {"^GSPC": {"price_date": "2026-08-31", "data_status": "current"}}}
        self.assertEqual(market_data_through(layer), "2026-09-01")

    def test_critical_validation_rejects_empty_radar(self):
        payload = valid_payload()
        payload["radar"]["ai"] = []
        self.assertIn("AI/Technology Radar is empty", validate_production_data(payload))

    def test_atomic_writer_preserves_previous_output_on_validation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news-dashboard.json"
            output.write_text('{"previous": true}\n')
            broken = valid_payload()
            broken["market_data"]["securities"] = {}
            with self.assertRaises(RuntimeError):
                write_production_data(broken, output)
            self.assertEqual(json.loads(output.read_text()), {"previous": True})

    def test_atomic_writer_publishes_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news-dashboard.json"
            write_production_data(valid_payload(), output)
            self.assertEqual(json.loads(output.read_text())["market_data_through"], "2026-09-01")

    def test_workflow_runs_tests_and_generator_after_market_close_on_weekdays(self):
        workflow = (ROOT / ".github" / "workflows" / "update-news-dashboard.yml").read_text()
        self.assertIn('cron: "17 23 * * 1-5"', workflow)
        self.assertIn("python -m unittest discover -s tests -p 'test_*.py'", workflow)
        self.assertIn("python scripts/update_news_dashboard.py", workflow)
        self.assertIn("git add data/news-dashboard.json", workflow)

    def test_frontend_displays_both_freshness_timestamps_and_keeps_user_storage_separate(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn('id="last-updated"', page)
        self.assertIn('id="market-data-through"', page)
        self.assertIn('setText("market-data-through"', script)
        self.assertIn("WATCHLIST_STORAGE_KEY", script)
        self.assertIn("POSITION_STORAGE_KEY", script)
        self.assertNotIn("localStorage.clear", script)

    def test_news_ui_keeps_summary_takeaways_and_news_but_omits_reasoning_panels(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        for element_id in ("ai-news-summary-copy", "news-takeaways", "ai-top-news",
                           "biotech-news-summary-copy", "biotech-news-takeaways", "biotech-top-news"):
            self.assertIn(f'id="{element_id}"', page)
        self.assertNotIn("News Reasoning", page)
        self.assertNotIn('id="news-reasoning"', page)
        self.assertNotIn('id="biotech-news-reasoning"', page)
        self.assertNotIn('renderReasoning("news-reasoning"', script)
        self.assertNotIn('renderReasoning("biotech-news-reasoning"', script)


if __name__ == "__main__":
    unittest.main()
