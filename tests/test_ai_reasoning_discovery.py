import unittest
from datetime import datetime, timezone

from scripts.ai_reasoning_discovery import build_ai_reasoning_discovery
from scripts.update_news_dashboard import (
    COMPANY_TICKER_INDEX,
    build_ai_radar,
    discover_candidate_pool,
)


RUN_AT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def news_section():
    event = {
        "event_id": "optical-1", "event_date": "2026-08-29T12:00+00:00",
        "headline": "Lumentum expands optical interconnect production for AI scale-out networks",
        "company": "NVIDIA", "ticker": "NVDA", "exchange": "", "listing_status": "Public",
        "company_identities": [{"company": "NVIDIA", "ticker": "NVDA", "exchange": "",
                                "listing_status": "Public"}],
        "event_type": "Capacity / Contract", "direction": "Expanding",
        "confirmation_status": "NEW", "news_importance_score": 88,
        "new_information": "Lumentum Holdings is increasing optical interconnect capacity for scale-out AI networking.",
        "affected_trends": ["Networking/Optical"], "direct_effects": ["Networking/Optical"],
        "second_order_effects": ["Data Centers"], "evidence_sources": [], "archived": False,
    }
    return {"radar_evidence_interface": {"events": [event]}}


class AiReasoningDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.listed = [{"company": "Lumentum Holdings Inc.", "ticker": "LITE", "exchange": "",
                        "listing_status": "Public", "resolution": "test listed-company universe"},
                       {"company": "Bandwidth Inc.", "ticker": "BAND", "exchange": "",
                        "listing_status": "Public", "resolution": "test listed-company universe"}]

    def test_discovers_theme_and_stock_without_manual_ticker_map(self):
        self.assertNotIn("LITE", COMPANY_TICKER_INDEX)
        discovery = build_ai_reasoning_discovery(news_section(), self.listed,
                                                  {"status": "test", "records_loaded": 1})
        themes = {row["theme"] for row in discovery["theme_signals"]}
        self.assertIn("Optical and scale-out AI networking", themes)
        lumentum = next(row for row in discovery["stock_candidates"] if row["ticker"] == "LITE")
        self.assertIn("First-Order", lumentum["beneficiary_roles"])
        self.assertIn("Networking/Optical", lumentum["parent_tracks"])
        self.assertEqual(lumentum["evidence_ids"], ["optical-1"])
        self.assertNotIn("BAND", {row["ticker"] for row in discovery["stock_candidates"]})

    def test_discovered_stock_flows_to_candidate_pool_and_radar(self):
        discovery = build_ai_reasoning_discovery(news_section(), self.listed)
        pool = discover_candidate_pool([], [], discovery)
        candidate = next(row for row in pool["candidates"] if row["ticker"] == "LITE")
        self.assertIn("Direct", candidate["categories"])
        self.assertTrue(any(link.get("reasoning_discovery") for link in candidate["radar_links"]))

        baseline = build_ai_radar(news_section(), [], RUN_AT)
        augmented = build_ai_radar(news_section(), [], RUN_AT, ai_reasoning_discovery=discovery)
        baseline_network = next(row for row in baseline if row["trend"] == "Networking/Optical")
        augmented_network = next(row for row in augmented if row["trend"] == "Networking/Optical")
        self.assertEqual(baseline_network["trend_strength"], augmented_network["trend_strength"])
        self.assertIn("LITE", {row["ticker"] for row in augmented_network["beneficiary_records"]})
        self.assertTrue(augmented_network["discovered_themes"])

    def test_missing_identity_is_not_fabricated(self):
        discovery = build_ai_reasoning_discovery(news_section(), [])
        self.assertNotIn("LITE", {row["ticker"] for row in discovery["stock_candidates"]})
        self.assertEqual(discovery["policy"]["missing_data"],
                         "Unresolved company identity remains unresolved and is not converted into a ticker.")


if __name__ == "__main__":
    unittest.main()
