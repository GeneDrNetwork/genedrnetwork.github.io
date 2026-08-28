import unittest
from datetime import datetime, timezone

from scripts.update_news_dashboard import build_ai_news_section, score_ai_news_item


RUN_AT = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def feed_item(title, source="Reuters", date="Fri, 28 Aug 2026 10:00:00 GMT"):
    return {
        "title": f"{title} - {source}",
        "source": source,
        "date": date,
        "url": "https://news.google.com/rss/articles/" + title.lower().replace(" ", "-")[:60],
        "publisher_url": "https://www.reuters.com/",
    }


class AiTechnologyNewsTests(unittest.TestCase):
    def test_selects_reliable_investment_relevant_story(self):
        story = score_ai_news_item(
            feed_item("Nvidia plans $40 billion AI data center capacity investment"), RUN_AT, set(), set())
        self.assertIsNotNone(story)
        self.assertGreaterEqual(story["news_importance_score"], 65)
        self.assertIn("Compute", story["affected_trends"])
        self.assertIn("Data Centers", story["affected_trends"])
        self.assertEqual(story["status"], "NEW")
        self.assertEqual(story["event_type"], "Company Update")
        self.assertEqual(story["direction"], "Expanding")
        self.assertTrue(story["new_information"])
        self.assertNotIn("future_signal_score", story)
        self.assertNotIn("potential_beneficiaries", story)

    def test_rejects_unconfigured_source(self):
        story = score_ai_news_item(
            feed_item("Nvidia plans $40 billion AI data center capacity investment", source="Unknown Blog"),
            RUN_AT, set(), set())
        self.assertIsNone(story)

    def test_does_not_treat_partial_company_name_as_primary_source(self):
        story = score_ai_news_item(
            feed_item("Nvidia reports AI earnings growth", source="Intellectia AI"),
            RUN_AT, set(), set())
        self.assertIsNone(story)

    def test_previous_top_story_moves_to_archive(self):
        old = score_ai_news_item(
            feed_item("Nvidia plans $40 billion AI data center capacity investment"), RUN_AT, set(), set())
        section = build_ai_news_section(
            [feed_item("Microsoft plans $30 billion AI cloud capex investment")],
            {"stories": [old], "important_news_archive": []}, RUN_AT)
        self.assertEqual(len(section["stories"]), 1)
        self.assertEqual(section["important_news_archive"][0]["id"], old["id"])
        interface = section["radar_evidence_interface"]
        self.assertEqual(interface["schema_version"], "news-to-radar-evidence-v1")
        self.assertEqual(len(interface["events"]), 2)
        self.assertNotIn("radar_score", interface["events"][0])
        self.assertNotIn("opportunity_rank", interface["events"][0])

    def test_offline_run_preserves_previous_data(self):
        old = score_ai_news_item(
            feed_item("Nvidia plans $40 billion AI data center capacity investment"), RUN_AT, set(), set())
        prior = {"stories": [old], "important_news_archive": [dict(old, id="archive-id")]}
        section = build_ai_news_section([], prior, RUN_AT)
        self.assertEqual(section["stories"][0]["id"], old["id"])
        self.assertEqual(len(section["important_news_archive"]), 1)
        self.assertNotIn("future_signal_score", section["stories"][0])
        self.assertEqual(len(section["radar_evidence_interface"]["events"]), 2)


if __name__ == "__main__":
    unittest.main()
