import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AiRadarStockLayoutTests(unittest.TestCase):
    def test_ai_radar_headers_follow_stock_first_reading_order(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        labels = ["Stock / Price", "Category", "Strength", "Opportunity Stage",
                  "Why Selected", "Risk / Unproven"]
        positions = [page.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))

    def test_frontend_flattens_existing_public_beneficiaries_without_rescoring(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("function aiStockRadarRows", script)
        self.assertIn("strength: trend.trend_strength", script)
        self.assertIn('beneficiary.listing_status !== "Public"', script)
        self.assertIn("beneficiary.opportunity_stage", script)
        self.assertIn("beneficiary.thesis_evidence", script)
        self.assertIn("beneficiary.confirmation_evidence", script)

    def test_biotech_renderer_remains_separate(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("function renderBiotechRadar(rows)", script)
        self.assertIn('class="radar-item biotech-radar-item"', script)


if __name__ == "__main__":
    unittest.main()
