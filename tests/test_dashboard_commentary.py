import copy
import json
import unittest
from pathlib import Path

from scripts.dashboard_commentary import (
    annotate_high_conviction,
    annotate_watchlists,
    build_news_commentary,
    build_radar_commentary,
)


DATA = json.loads((Path(__file__).parents[1] / "data" / "news-dashboard.json").read_text())


class DashboardCommentaryTests(unittest.TestCase):
    def test_news_reasoning_and_takeaways_are_evidence_derived(self):
        result = build_news_commentary(
            DATA["top_investment_news"]["ai_technology"],
            DATA["top_investment_news"]["biotech_healthcare"])
        self.assertEqual([item["label"] for item in result["reasoning"]], [
            "What is happening?", "Why does it matter?", "What larger trend is forming?",
            "What could happen next?", "Investment implications"])
        self.assertGreaterEqual(len(result["take_home_messages"]), 3)
        self.assertLessEqual(len(result["take_home_messages"]), 5)
        headlines = {item["headline"] for section in DATA["top_investment_news"].values()
                     for item in section.get("stories", [])}
        self.assertFalse(any(message in headlines for message in result["take_home_messages"]))

    def test_radar_commentary_precedes_stock_level_detail(self):
        result = build_radar_commentary(DATA["radar"]["ai"], DATA["radar"]["biotech"])
        self.assertEqual(len(result["reasoning"]), 5)
        self.assertGreaterEqual(len(result["take_home_messages"]), 3)
        self.assertIn(DATA["radar"]["ai"][0]["trend"], " ".join(item["text"] for item in result["reasoning"]) + " " + " ".join(result["take_home_messages"]))

    def test_high_conviction_commentary_does_not_change_ranking_or_scores(self):
        rows = copy.deepcopy(DATA["monthly_picks"])
        before = {domain: [(row["ticker"], row["rank"], row["final_score"], copy.deepcopy(row["gates"]))
                           for row in domain_rows] for domain, domain_rows in rows.items()}
        group = annotate_high_conviction(rows)
        after = {domain: [(row["ticker"], row["rank"], row["final_score"], row["gates"])
                          for row in domain_rows] for domain, domain_rows in rows.items()}
        self.assertEqual(before, after)
        self.assertGreaterEqual(len(group["reasons"]), 3)
        self.assertTrue(all(row.get("why_this_stock", {}).get("summary")
                            for domain_rows in rows.values() for row in domain_rows))

    def test_watchlist_commentary_uses_existing_technicals_and_biotech_targets_only(self):
        watchlists = copy.deepcopy(DATA["watchlists"])
        annotate_watchlists(watchlists, DATA["radar"]["biotech"])
        ai = watchlists["ai"][0]; biotech = watchlists["biotech"][0]
        self.assertIn("Buy status", ai["watchlist_commentary"]["entry"])
        self.assertIsNone(ai["watchlist_technical"]["targets"])
        self.assertIsNotNone(biotech["watchlist_technical"]["targets"])
        self.assertIn("plus_10", biotech["watchlist_technical"]["targets"])
        self.assertEqual(biotech["watchlist_technical"]["target_basis"], "Planned watchlist entry reference")


if __name__ == "__main__":
    unittest.main()
