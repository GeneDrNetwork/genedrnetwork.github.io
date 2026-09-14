import unittest
from datetime import date, timedelta
from unittest.mock import patch

from scripts.update_news_dashboard import (
    BIOTECH_CATALYSTS,
    BIOTECH_RADAR_WEIGHTS,
    MRNA_VALIDATION_CASE,
    biotech_technical_overlay,
    build_biotech_radar,
    expectation_assessment,
    radar_action_pool_eligible,
    radar_dynamic_final_score,
    score_biotech_catalyst,
)


class BiotechCatalystRadarTests(unittest.TestCase):
    def test_weights_match_phase_four_and_total_100(self):
        self.assertEqual(BIOTECH_RADAR_WEIGHTS, {
            "scientific_evidence": 30,
            "catalyst_impact_company_sensitivity": 25,
            "expectation_gap": 20,
            "sector_trend_capital_flow": 15,
            "timing_technicals": 10,
        })
        self.assertEqual(sum(BIOTECH_RADAR_WEIGHTS.values()), 100)

    def test_live_radar_is_hierarchical_and_keeps_outputs_distinct(self):
        rows = build_biotech_radar(date(2026, 8, 27))
        self.assertEqual([row["dynamic_final_rank"] for row in rows], list(range(1, len(rows) + 1)))
        self.assertEqual([row["dynamic_final_score"] for row in rows],
                         sorted((row["dynamic_final_score"] for row in rows), reverse=True))
        self.assertTrue(all(row["engine_version"] == "biotech-radar-v1" for row in rows))
        self.assertTrue(all(len(row["score_components"]) == 5 for row in rows))
        self.assertTrue(all(row.get("company") and row.get("program") and row.get("indication") and row.get("catalyst") for row in rows))
        self.assertTrue(all("binary_risk" in row and "confidence" in row for row in rows))
        self.assertTrue(all(row["biotech_opportunity_score"] == row["opportunity_score"] for row in rows))
        self.assertTrue(all(row["price_discovery_stage"] in
                            ("Early Discovery", "Emerging", "Re-rating Underway", "Already Ran") for row in rows))
        self.assertTrue(all(row["already_priced_in"] in ("NO", "PARTIALLY", "YES") for row in rows))

    def test_rank_is_independent_of_action_label(self):
        def scored(item, *_args, **_kwargs):
            is_action = item["ticker"] == "NTLA"
            score = 50 if is_action else 90 if item["ticker"] == "BEAM" else 30
            return {**item, "actionable": is_action, "pool": "Action Pool" if is_action else "Discovery Pool",
                    "dynamic_final_score": score, "radar_rank_score": score,
                    "biotech_opportunity_score": score}

        with patch("scripts.update_news_dashboard.score_biotech_catalyst", side_effect=scored):
            rows = build_biotech_radar(date(2026, 8, 27))
        self.assertEqual(rows[0]["ticker"], "BEAM")
        self.assertEqual(rows[0]["pool"], "Discovery Pool")
        self.assertGreater(next(row["dynamic_final_rank"] for row in rows if row["ticker"] == "NTLA"), 1)

    def test_biotech_action_requires_rs_volume_entry_and_invalidation(self):
        row = {
            "biotech_opportunity_score": 80, "multibagger_potential_score": 70,
            "already_priced_in": "NO", "catalyst_validation": {"valid": True},
            "evidence_gate": {"passed": True}, "evidence_integrity_gate": {"concern_identified": False},
            "strategy_technical_setup": {"actionable": True, "falling": False,
                                         "failed_reversal": False, "extended": False},
            "biotech_technical_overlay": {
                "trend_confirmed": True, "relative_strength_confirmed": True,
                "volume_confirmed": True, "entry_confirmed": True,
                "invalidation_defined": True},
        }
        self.assertTrue(radar_action_pool_eligible(row, biotech=True))
        row["biotech_technical_overlay"]["relative_strength_confirmed"] = False
        self.assertFalse(radar_action_pool_eligible(row, biotech=True))

    def test_technical_overlay_separates_trend_rs_volume_and_entry(self):
        setup = {"primary_trend_confirmed": True, "actionable": True,
                 "invalidation_level": 42}
        snapshot = {"relative_strength": {"xbi": {"three_month": 7}},
                    "entry_inputs": {"breakout_volume_ratio": 1.4}}
        overlay = biotech_technical_overlay(snapshot, setup)
        self.assertTrue(all(overlay[key] for key in (
            "trend_confirmed", "relative_strength_confirmed", "volume_confirmed",
            "entry_confirmed", "invalidation_defined")))

    def test_dynamic_score_does_not_count_catalyst_or_valuation_twice(self):
        setup = {"score": 80, "actionable": False, "stage": "Mature Base"}
        base = {"radar_rank_score": 75, "strategy_technical_setup": setup}
        duplicated_inputs = {**base, "expectation": {"score": 20, "maximum": 20},
                             "catalyst_validation": {"valid": True}}
        self.assertEqual(radar_dynamic_final_score(base),
                         radar_dynamic_final_score(duplicated_inputs))

    def test_biotech_expectation_excludes_pe_and_eps_revision_signals(self):
        snapshot = {"expectation_data": {
            "data_status": "current",
            "available_input_groups": ["valuation", "price_run_up", "analyst_consensus"],
            "valuation": {"forward_pe": 5},
            "price_run_up": {"three_month_pct": 0},
            "analyst_consensus": {"net_revisions_4w": 10},
            "short_interest": {}, "sources": [],
        }}
        biotech = expectation_assessment(
            snapshot, "biotech", 20, exclude_conventional_earnings=True)
        conventional_equity = expectation_assessment(snapshot, "ai", 20)
        other_biotech_workflow = expectation_assessment(snapshot, "biotech", 20)
        self.assertEqual(biotech["state"], "Fairly Priced")
        self.assertEqual(biotech["score"], 11)
        self.assertEqual(conventional_equity["state"], "Underpriced")
        self.assertEqual(other_biotech_workflow["state"], "Underpriced")
        self.assertGreater(conventional_equity["score"], biotech["score"])

    def test_biotech_methodology_is_presented_next_to_section(self):
        with open("programs/genedrnews.html", encoding="utf-8") as handle:
            page = handle.read()
        biotech_start = page.index('id="biotech-radar-title"')
        crypto_start = page.index('id="crypto-radar-title"')
        biotech_section = page[biotech_start:crypto_start]
        self.assertIn("T. Ayers Pelz", biotech_section)
        self.assertIn("Conventional P/E and EPS are not required", biotech_section)

    def test_missing_inputs_are_not_zero(self):
        beam = next(row for row in build_biotech_radar(date(2026, 8, 27)) if row["ticker"] == "BEAM")
        missing = {part["key"]: part for part in beam["score_components"] if part["missing"]}
        self.assertIsNone(missing["expectation_gap"]["score"])
        self.assertIsNone(missing["sector_trend_capital_flow"]["score"])
        self.assertLess(beam["data_completeness"], 100)
        self.assertIn("Price/volume technical setup", beam["missing_data"])
        self.assertIn("Short interest / advanced positioning", beam["missing_data"])

    def test_evidence_gate_blocks_weak_science_from_high_conviction(self):
        krystal = next(row for row in build_biotech_radar(date(2026, 8, 27)) if row["ticker"] == "KRYS")
        self.assertIsNone(krystal["scientific_evidence_score"])
        self.assertFalse(krystal["evidence_gate"]["passed"])
        self.assertIn(krystal["opportunity_status"], ("Speculative Binary", "High Downside Risk"))
        self.assertIn(krystal["binary_risk"], ("High", "Extreme"))

    def test_news_is_evidence_only_and_history_is_preserved(self):
        item = next(item for item in BIOTECH_CATALYSTS if item["ticker"] == "BEAM")
        event = {
            "id": "beam-event", "published_at": "2026-08-26T12:00:00+00:00", "company": "Beam Therapeutics",
            "ticker": "BEAM", "drug_program": "BEAM-302", "indication": "Alpha-1 antitrypsin deficiency",
            "direction": "Positive / Advancing", "new_information": "Updated BEAM-302 data confirmed the previously reported response.",
            "news_importance_score": 65,
        }
        low_news = {"radar_evidence_interface": {"events": [event]}}
        high_news = {"radar_evidence_interface": {"events": [dict(event, news_importance_score=100)]}}
        first = score_biotech_catalyst(item, date(2026, 8, 27), low_news)
        high = score_biotech_catalyst(item, date(2026, 8, 27), high_news)
        self.assertEqual(first["opportunity_score"], high["opportunity_score"])
        self.assertEqual(len(first["confirming_evidence"]), 1)
        same_day = score_biotech_catalyst(item, date(2026, 8, 27), low_news, first)
        self.assertEqual(len(same_day["score_history"]), 1)
        next_day = score_biotech_catalyst(item, date(2026, 8, 27) + timedelta(days=1), low_news, same_day)
        self.assertEqual(len(next_day["score_history"]), 2)

    def test_integrity_concern_caps_confidence(self):
        item = next(item for item in BIOTECH_CATALYSTS if item["ticker"] == "BEAM")
        section = {"radar_evidence_interface": {"events": [{
            "id": "integrity-event", "published_at": "2026-08-26T12:00:00+00:00", "ticker": "BEAM",
            "drug_program": "BEAM-302", "indication": "Alpha-1 antitrypsin deficiency",
            "direction": "Negative / Delayed", "new_information": "A clinical hold cited an explicit data integrity concern.",
        }]}}
        result = score_biotech_catalyst(item, date(2026, 8, 27), section)
        self.assertTrue(result["evidence_integrity_gate"]["concern_identified"])
        self.assertEqual(result["confidence"], "Low")
        self.assertEqual(result["opportunity_status"], "High Downside Risk")

    def test_evidence_evolution_and_thesis_broken_status(self):
        item = next(item for item in BIOTECH_CATALYSTS if item["ticker"] == "BEAM")
        base = {"published_at": "2026-08-26T12:00:00+00:00", "ticker": "BEAM",
                "drug_program": "BEAM-302", "indication": "Alpha-1 antitrypsin deficiency"}
        section = {"radar_evidence_interface": {"events": [
            dict(base, id="confirming", direction="Positive / Advancing", new_information="The response was confirmed."),
            dict(base, id="mixed", direction="Mixed", new_information="The update contained mixed efficacy and safety observations."),
            dict(base, id="broken", direction="Negative / Delayed", new_information="The trial failed primary endpoint and the program was discontinued."),
        ]}}
        result = score_biotech_catalyst(item, date(2026, 8, 27), section)
        self.assertEqual(len(result["confirming_evidence"]), 1)
        self.assertEqual(len(result["mixed_evidence"]), 1)
        self.assertEqual(len(result["contradicting_evidence"]), 1)
        self.assertEqual(result["opportunity_status"], "Thesis Broken")
        self.assertIsNone(result["binary_risk_inputs"]["company_sensitivity"])
        self.assertIsNone(result["binary_risk_inputs"]["portfolio_dependence"])

    def test_mrna_backtest_is_frozen_at_cutoff(self):
        result = score_biotech_catalyst(MRNA_VALIDATION_CASE, date(2026, 7, 31))
        self.assertEqual(result["score_as_of"], "2026-07-31")
        self.assertTrue(all(source["date"] <= "2026-07-31" for source in result["sources"]))
        self.assertIsNone(result["expectation_gap_score"])
        self.assertLess(result["data_completeness"], 100)


if __name__ == "__main__":
    unittest.main()
