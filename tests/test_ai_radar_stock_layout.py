import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AiRadarStockLayoutTests(unittest.TestCase):
    def test_ai_radar_headers_show_compact_early_opportunity_fields(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        labels = ["Ticker", "Opportunity Score", "Multibagger Potential", "Price Discovery Stage",
                  "Already Priced In", "Entry Stage"]
        positions = [page.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("<span>Price</span>", page)

    def test_frontend_flattens_existing_public_beneficiaries_without_rescoring(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("function aiStockRadarRows", script)
        self.assertIn("opportunity_score: beneficiary.bottleneck_opportunity_score", script)
        self.assertIn("multibagger_score: beneficiary.multibagger_potential_score", script)
        self.assertIn("beneficiary.radar_rank_score", script)
        self.assertIn('beneficiary.listing_status !== "Public"', script)
        self.assertIn("beneficiary.opportunity_stage", script)
        self.assertIn("beneficiary.thesis_evidence", script)
        self.assertIn("beneficiary.confirmation_evidence", script)
        company_start = script.index('<span class="ai-stock-identity">')
        price_start = script.index("currentPriceLabel(ticker, beneficiary.market_data)")
        self.assertLess(company_start, price_start)

    def test_biotech_renderer_remains_separate(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("function renderBiotechRadar(rows, targetId", script)
        self.assertIn('class="radar-item biotech-radar-item"', script)

    def test_manual_analysis_and_separate_radar_commentary_are_present(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn('id="radar-analyze-form"', page)
        self.assertIn('id="ai-radar-summary-copy"', page)
        self.assertIn('id="biotech-radar-summary-copy"', page)
        self.assertNotIn('id="radar-reasoning"', page)
        self.assertNotIn('id="radar-takeaways"', page)
        self.assertIn("function renderRadarAnalysis", script)
        self.assertIn("ai_manual_analysis_candidates", script)
        self.assertIn("manual_market_context", script)
        self.assertIn("does not alter automatic Radar ranking", script)


if __name__ == "__main__":
    unittest.main()
