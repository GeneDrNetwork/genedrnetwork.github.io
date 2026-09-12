import unittest

from scripts.catalyst_validation import company_catalyst_validation
from scripts.update_news_dashboard import ai_company_catalyst


class CatalystValidationTests(unittest.TestCase):
    def test_company_named_event_is_company_specific(self):
        event = {
            "ticker": "NNE", "company": "Nano Nuclear Energy",
            "headline": "Nano Nuclear Energy announces a reactor project update",
            "new_information": "The company filed a project update.",
        }
        result = company_catalyst_validation(event, "NNE", "Nano Nuclear Energy")
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "COMPANY-SPECIFIC CATALYST")

    def test_nvidia_infrastructure_news_is_not_an_nne_catalyst(self):
        event = {
            "event_id": "nvidia-ai-infrastructure", "age_band": "Fresh",
            "ticker": "NVDA", "company": "NVIDIA",
            "company_identities": [{"company": "NVIDIA", "ticker": "NVDA"}],
            "headline": "NVIDIA expands AI infrastructure capacity in Australia",
            "new_information": "NVIDIA and its cloud partners plan a 2-gigawatt AI factory buildout.",
            "source_link": "https://example.com/nvidia", "event_date": "2026-09-10",
            "news_importance_score": 95,
        }
        validation = company_catalyst_validation(event, "NNE", "Nano Nuclear Energy")
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["status"], "THEME ONLY / UNVERIFIED")

        linked = [({"confirming_evidence": [event], "mixed_evidence": []}, {
            "ticker": "NNE", "company": "Nano Nuclear Energy",
            "evidence_ids": ["nvidia-ai-infrastructure"],
        })]
        catalyst = ai_company_catalyst(linked, "NNE")
        self.assertFalse(catalyst["valid"])
        self.assertEqual(catalyst["description"], "THEME ONLY / UNVERIFIED")
        self.assertIsNone(catalyst["company_specific_catalyst"])
        self.assertIn("NVIDIA", catalyst["industry_theme_catalyst"])

    def test_direct_company_event_remains_valid_through_high_conviction_adapter(self):
        event = {
            "event_id": "company-event", "age_band": "Fresh", "ticker": "TEST",
            "company": "Test Systems", "headline": "Test Systems wins a customer contract",
            "new_information": "Test Systems signed a multi-year commercial agreement.",
            "source_link": "https://example.com/test", "event_date": "2026-09-09",
            "event_type": "Commercial Event", "news_importance_score": 10,
        }
        linked = [({"confirming_evidence": [event], "mixed_evidence": []}, {
            "ticker": "TEST", "company": "Test Systems", "evidence_ids": ["company-event"],
        })]
        catalyst = ai_company_catalyst(linked, "TEST")
        self.assertTrue(catalyst["valid"])
        self.assertEqual(catalyst["status"], "COMPANY-SPECIFIC CATALYST")
        self.assertEqual(catalyst["score"], 95)

    def test_primary_company_evidence_is_preferred_over_generic_coverage(self):
        news = {
            "event_id": "news", "age_band": "Fresh", "ticker": "TEST", "company": "Test Systems",
            "headline": "Test Systems discussed in market coverage", "new_information": "A news report described demand.",
            "source": "Market News", "source_link": "https://example.com/news", "event_date": "2026-09-10",
            "event_type": "Commercial Event", "news_importance_score": 99,
        }
        filing = {
            **news, "event_id": "filing", "headline": "Test Systems files quarterly results",
            "new_information": "Test Systems reported orders and backlog in its quarterly filing.",
            "source": "SEC company filing", "source_link": "https://www.sec.gov/example", "event_date": "2026-09-09",
            "news_importance_score": 70,
        }
        linked = [({"confirming_evidence": [news, filing], "mixed_evidence": []}, {
            "ticker": "TEST", "company": "Test Systems", "evidence_ids": ["news", "filing"],
        })]
        catalyst = ai_company_catalyst(linked, "TEST")
        self.assertEqual(catalyst["evidence_id"], "filing")
        self.assertIn("orders and backlog", catalyst["company_specific_catalyst"])

    def test_frontend_downgrades_unverified_entry_actions(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parents[1] / "assets" / "news-dashboard.js").read_text()
        self.assertIn('WATCH / WAIT FOR VALID CATALYST', script)
        self.assertIn('THEME ONLY / UNVERIFIED', script)
        self.assertIn('Company-Specific Catalyst', script)
        self.assertIn('Industry / Theme Catalyst', script)


if __name__ == "__main__":
    unittest.main()
