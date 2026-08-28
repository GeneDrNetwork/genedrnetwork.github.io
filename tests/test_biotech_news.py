import unittest
from datetime import datetime, timezone

from scripts.update_news_dashboard import (
    build_biotech_news_section,
    cluster_biotech_news_items,
    score_biotech_news_item,
)


RUN_AT = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def feed_item(title, source="Moderna Investor Relations", description="", primary=True):
    return {
        "title": f"{title} - {source}",
        "source": source,
        "date": "Fri, 28 Aug 2026 10:00:00 GMT",
        "url": "https://example.com/" + title.lower().replace(" ", "-")[:60],
        "publisher_url": "https://example.com/",
        "description": description,
        "is_primary": primary,
    }


class BiotechNewsTests(unittest.TestCase):
    def test_scores_requested_news_components_only(self):
        story = score_biotech_news_item(feed_item(
            "Moderna reports positive Phase 3 mRNA-1010 influenza trial met primary endpoint",
            description="The Phase 3 study met its primary endpoint with 72% efficacy."), RUN_AT, set())
        self.assertIsNotNone(story)
        self.assertGreaterEqual(story["news_importance_score"], 80)
        self.assertEqual(story["company"], "Moderna")
        self.assertEqual(story["ticker"], "MRNA")
        self.assertEqual(story["drug_program"], "mRNA-1010")
        self.assertEqual(story["event_type"], "Clinical Results")
        components = story["score_evidence"]
        self.assertEqual({key: value["weight"] for key, value in components.items()}, {
            "event_significance": 30, "company_sector_impact": 25, "novelty": 20,
            "evidence_authority": 15, "immediacy": 10,
        })
        self.assertEqual(sum(value["score"] for value in components.values()), story["news_importance_score"])
        for forbidden in ("scientific_evidence", "catalyst_impact", "expectation_gap", "sector_trend", "opportunity_score"):
            self.assertNotIn(forbidden, story)
            self.assertNotIn(forbidden, components)

    def test_rejects_unconfigured_source(self):
        story = score_biotech_news_item(feed_item(
            "Moderna reports positive Phase 3 mRNA-1010 results", source="Unknown Blog", primary=False),
            RUN_AT, set())
        self.assertIsNone(story)

    def test_deduplicates_reports_of_same_event(self):
        title = "Moderna reports positive Phase 3 mRNA-1010 influenza trial results"
        items = [feed_item(title), feed_item(title, source="Reuters", primary=False)]
        clusters = cluster_biotech_news_items(items)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]["evidence_sources"]), 2)

    def test_prominent_and_archive_thresholds(self):
        strong = feed_item("Moderna reports positive Phase 3 mRNA-1010 influenza trial met primary endpoint")
        moderate = feed_item("Moderna publishes mRNA platform update")
        section = build_biotech_news_section([strong, moderate], {}, RUN_AT)
        self.assertEqual(len(section["stories"]), 1)
        self.assertGreaterEqual(section["stories"][0]["news_importance_score"], 80)
        self.assertEqual(len(section["important_news_archive"]), 1)
        self.assertGreaterEqual(section["important_news_archive"][0]["news_importance_score"], 65)
        self.assertLess(section["important_news_archive"][0]["news_importance_score"], 80)
        interface = section["radar_evidence_interface"]
        self.assertEqual(interface["schema_version"], "biotech-news-to-radar-evidence-v1")
        self.assertEqual(len(interface["events"]), 2)

    def test_offline_run_preserves_prior_events(self):
        story = score_biotech_news_item(feed_item(
            "Moderna reports positive Phase 3 mRNA-1010 influenza trial met primary endpoint"), RUN_AT, set())
        prior = {"stories": [story], "important_news_archive": []}
        section = build_biotech_news_section([], prior, RUN_AT)
        self.assertEqual(section["stories"][0]["id"], story["id"])
        self.assertEqual(len(section["radar_evidence_interface"]["events"]), 1)

    def test_current_event_removes_legacy_archive_duplicate(self):
        item = feed_item("Moderna reports positive Phase 3 mRNA-1010 influenza trial met primary endpoint")
        legacy = score_biotech_news_item(item, RUN_AT, set())
        legacy["id"] = "legacy-id"
        section = build_biotech_news_section([item], {"stories": [], "important_news_archive": [legacy]}, RUN_AT)
        self.assertEqual(len(section["stories"]), 1)
        self.assertEqual(section["important_news_archive"], [])


if __name__ == "__main__":
    unittest.main()
