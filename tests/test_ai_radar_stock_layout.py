import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AiRadarStockLayoutTests(unittest.TestCase):
    def test_ai_radar_headers_follow_category_then_company_reading_order(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        labels = ["Category", "Company / Ticker", "Strength", "Opportunity Stage",
                  "Why Selected", "Risk / Unproven"]
        positions = [page.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("<span>Price</span>", page)

    def test_frontend_flattens_existing_public_beneficiaries_without_rescoring(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("function aiStockRadarRows", script)
        self.assertIn("strength: trend.trend_strength", script)
        self.assertIn('beneficiary.listing_status !== "Public"', script)
        self.assertIn("beneficiary.opportunity_stage", script)
        self.assertIn("beneficiary.thesis_evidence", script)
        self.assertIn("beneficiary.confirmation_evidence", script)
        identity_start = script.index('<span class="ai-stock-category">')
        company_start = script.index('<span class="ai-stock-identity">')
        price_start = script.index("currentPriceLabel(ticker, beneficiary.market_data)")
        self.assertLess(identity_start, company_start)
        self.assertLess(company_start, price_start)

    def test_biotech_renderer_remains_separate(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("function renderBiotechRadar(rows)", script)
        self.assertIn('class="radar-item biotech-radar-item"', script)


if __name__ == "__main__":
    unittest.main()
