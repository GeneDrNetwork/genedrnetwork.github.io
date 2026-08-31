import unittest
from datetime import datetime, timedelta, timezone

from scripts.ai_reasoning_discovery import build_ai_reasoning_discovery
from scripts.update_news_dashboard import (
    AI_RADAR_FACTOR_WEIGHTS,
    ai_adoption_stage,
    ai_evidence_age,
    build_ai_radar,
    deduplicate_ai_radar_evidence,
)


RUN_AT = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def evidence(event_id="compute-1", trend="Compute", second_order=None, information=None, event_type="Financial Results"):
    return {
        "event_id": event_id, "event_date": "2026-08-27T12:00+00:00", "headline": "NVIDIA reports AI infrastructure update",
        "company": "NVIDIA", "ticker": "NVDA", "exchange": "", "listing_status": "Public",
        "related_companies": [], "related_tickers": [],
        "company_identities": [{"company": "NVIDIA", "ticker": "NVDA", "exchange": "", "listing_status": "Public"}],
        "event_type": event_type, "direction": "Expanding", "confirmation_status": "NEW",
        "news_importance_score": 95,
        "new_information": information or "Revenue increased as customers deployed 2 million additional GPUs.",
        "affected_trends": [trend], "direct_effects": [trend], "second_order_effects": second_order or [],
        "evidence_sources": [], "source_link": "https://example.com/evidence", "archived": False,
    }


def build_with_discovery(section, previous=None, run_at=RUN_AT):
    discovery = build_ai_reasoning_discovery(section, [])
    return build_ai_radar(section, previous or [], run_at, ai_reasoning_discovery=discovery)


class AiTechnologyRadarTests(unittest.TestCase):
    def test_builds_all_tracks_and_keeps_missing_factors_missing(self):
        section = {"radar_evidence_interface": {"events": [evidence(second_order=["Data Centers"])]}}
        rows = build_ai_radar(section, [], RUN_AT)
        self.assertEqual(len(rows), 10)
        self.assertIn("Physical AI / Robotics", {row["trend"] for row in rows})
        compute = next(row for row in rows if row["trend"] == "Compute")
        self.assertIsNotNone(compute["trend_strength"])
        self.assertIsNone(compute["opportunity_score"])
        components = {item["key"]: item for item in compute["score_components"]}
        self.assertEqual({key: component["weight"] for key, component in components.items()}, AI_RADAR_FACTOR_WEIGHTS)
        self.assertIsNone(components["expectation_gap_valuation"]["score"])
        self.assertIsNone(components["market_confirmation"]["score"])
        self.assertLess(compute["data_completeness"], 100)
        self.assertTrue(compute["confirming_evidence"])

    def test_physical_ai_pilots_do_not_become_mass_adoption(self):
        pilot = [evidence(trend="Physical AI / Robotics", event_type="Product / Platform",
                          information="A 100-robot pilot demonstrated a prototype at one customer site.")]
        stage, _ = ai_adoption_stage("Physical AI / Robotics", pilot)
        self.assertEqual(stage, "A2")
        scaled = [evidence(trend="Physical AI / Robotics", event_type="Commercial Event",
                           information="A paid deployment placed 1,000 production units across multiple sites.")]
        scaled_stage, _ = ai_adoption_stage("Physical AI / Robotics", scaled)
        self.assertEqual(scaled_stage, "A4")

    def test_underlying_event_deduplication_and_aging(self):
        first = evidence()
        duplicate = dict(first, news_importance_score=80)
        self.assertEqual(len(deduplicate_ai_radar_evidence([first, duplicate])), 1)
        age = ai_evidence_age(first["event_date"], RUN_AT)
        self.assertEqual(age["age_band"], "Fresh")
        self.assertGreater(age["freshness_multiplier"], 0)

    def test_beneficiary_categories_and_history_are_preserved(self):
        section = {"radar_evidence_interface": {"events": [evidence(second_order=["Data Centers"])]}}
        first = build_with_discovery(section)
        compute = next(row for row in first if row["trend"] == "Compute")
        self.assertTrue(any(item["category"] == "Direct" for item in compute["beneficiary_records"]))
        data_centers = next(row for row in first if row["trend"] == "Data Centers")
        self.assertNotIn("NVDA", {item["ticker"] for item in data_centers["beneficiary_records"]})
        self.assertTrue(all(item["evidence_ids"] for item in compute["beneficiary_records"]))
        same_day = build_with_discovery(section, first)
        same_day_compute = next(row for row in same_day if row["trend"] == "Compute")
        self.assertEqual(len(same_day_compute["score_history"]), 1)
        second = build_with_discovery(section, same_day, RUN_AT + timedelta(days=1))
        second_compute = next(row for row in second if row["trend"] == "Compute")
        self.assertEqual(len(second_compute["score_history"]), 2)
        self.assertIn("evidence", second_compute["why_changed"].lower())


if __name__ == "__main__":
    unittest.main()
