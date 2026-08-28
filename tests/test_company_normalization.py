import unittest
from datetime import datetime, timezone

from scripts.update_news_dashboard import (
    company_identity,
    normalize_investment_data,
    score_ai_news_item,
    score_biotech_news_item,
)


RUN_AT = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def news_item(title, source="Reuters"):
    return {
        "title": f"{title} - {source}", "source": source,
        "date": "Fri, 28 Aug 2026 10:00:00 GMT", "url": "https://example.com/story",
        "publisher_url": "https://example.com/",
    }


class CompanyNormalizationTests(unittest.TestCase):
    def test_public_private_foreign_and_non_public_mappings(self):
        self.assertEqual(company_identity("NVIDIA")["ticker"], "NVDA")
        self.assertEqual(company_identity("Roche")["ticker"], "ROP:SIX")
        self.assertEqual(company_identity("Implantica")["ticker"], "IMP A SDB:STO")
        self.assertEqual(company_identity("OpenAI")["ticker"], "Private")
        self.assertEqual(company_identity("FDA")["ticker"], "N/A")
        self.assertEqual(company_identity("Stanford University")["ticker"], "N/A")

    def test_ai_multi_company_event_has_primary_and_related_tickers(self):
        story = score_ai_news_item(news_item(
            "AWS and NVIDIA announce $40 billion AI data center partnership"), RUN_AT, set(), set())
        self.assertEqual(story["company"], "Amazon")
        self.assertEqual(story["ticker"], "AMZN")
        self.assertIn("NVDA", story["related_tickers"])

    def test_biotech_multi_company_event_uses_foreign_primary_listing(self):
        story = score_biotech_news_item(news_item(
            "Roche receives FDA approval for diagnostic tied to Jazz cancer drug", "Fierce Biotech"), RUN_AT, set())
        self.assertEqual(story["company"], "Roche")
        self.assertEqual(story["ticker"], "ROP:SIX")
        self.assertIn("JAZZ", story["related_tickers"])
        self.assertIn("N/A", story["related_tickers"])

    def test_all_dashboard_layers_use_registry(self):
        data = {
            "top_investment_news": {
                "ai_technology": {"stories": [], "important_news_archive": []},
                "biotech_healthcare": {"stories": [], "important_news_archive": []},
            },
            "ai": {
                "infrastructure_leaders": [{"company": "NVIDIA"}],
                "platform_leaders": [{"company": "OpenAI"}], "emerging": [],
                "demand_drivers": [{"public_companies": "NVIDIA, TSMC", "emerging_companies": "Groq"}],
            },
            "biotech": {"leaders": [{"company": "Roche"}], "emerging": []},
            "radar": {"biotech": [{"company": "Implantica"}]},
            "radar_validation": {},
            "monthly_picks": {"ai": [{"company": "NVIDIA"}], "biotech": [{"company": "Roche"}]},
            "watchlists": {"ai": [{"company": "Astera Labs"}], "biotech": [{"company": "Beam Therapeutics"}]},
            "fda": [{"company": "See source"}],
        }
        normalized = normalize_investment_data(data)
        self.assertEqual(normalized["ai"]["infrastructure_leaders"][0]["ticker"], "NVDA")
        self.assertEqual(normalized["ai"]["platform_leaders"][0]["ticker"], "Private")
        self.assertIn("TSMC (TSM)", normalized["ai"]["demand_drivers"][0]["public_companies"])
        self.assertEqual(normalized["radar"]["biotech"][0]["ticker"], "IMP A SDB:STO")
        self.assertEqual(normalized["monthly_picks"]["biotech"][0]["ticker"], "ROP:SIX")
        self.assertEqual(normalized["watchlists"]["ai"][0]["ticker"], "ALAB")
        self.assertEqual(normalized["fda"][0]["ticker"], "N/A")


if __name__ == "__main__":
    unittest.main()
