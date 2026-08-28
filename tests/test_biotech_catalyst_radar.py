import unittest
from datetime import date

from scripts.update_news_dashboard import (
    CATALYST_WEIGHTS,
    MRNA_VALIDATION_CASE,
    build_biotech_radar,
    catalyst_classification,
    score_biotech_catalyst,
)


class BiotechCatalystRadarTests(unittest.TestCase):
    def test_weights_total_100(self):
        self.assertEqual(sum(CATALYST_WEIGHTS.values()), 100)

    def test_classification_boundaries(self):
        self.assertEqual(catalyst_classification(85), "High Priority")
        self.assertEqual(catalyst_classification(70), "Priority Watch")
        self.assertEqual(catalyst_classification(55), "Monitoring")
        self.assertEqual(catalyst_classification(54), "Low Priority")

    def test_live_radar_is_sorted_and_contains_no_placeholders(self):
        rows = build_biotech_radar(date(2026, 8, 27))
        self.assertEqual([row["catalyst_score"] for row in rows], sorted(
            (row["catalyst_score"] for row in rows), reverse=True))
        self.assertTrue(all(row["engine_version"] == "biotech-catalyst-radar-v1" for row in rows))
        self.assertTrue(all(len(row["score_components"]) == 6 for row in rows))

    def test_missing_inputs_score_zero(self):
        beam = next(row for row in build_biotech_radar(date(2026, 8, 27)) if row["ticker"] == "BEAM")
        missing = {part["key"]: part for part in beam["score_components"] if part["missing"]}
        self.assertEqual(missing["expectation_gap"]["score"], 0)
        self.assertEqual(missing["positioning"]["score"], 0)

    def test_mrna_backtest_is_frozen_at_cutoff(self):
        result = score_biotech_catalyst(MRNA_VALIDATION_CASE, date(2026, 7, 31))
        self.assertEqual(result["catalyst_score"], 70)
        self.assertEqual(result["opportunity_status"], "Priority Watch")
        self.assertEqual(result["score_as_of"], "2026-07-31")
        self.assertTrue(all(source["date"] <= "2026-07-31" for source in result["sources"]))


if __name__ == "__main__":
    unittest.main()
