import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from scripts.ai_reasoning_discovery import build_ai_reasoning_discovery
from scripts.update_news_dashboard import (
    AI_RADAR_FACTOR_WEIGHTS,
    ai_early_opportunity_scores,
    ai_adoption_stage,
    ai_evidence_age,
    build_ai_radar,
    build_ai_reacceleration_alerts,
    build_manual_radar_market_context,
    deduplicate_ai_radar_evidence,
    focus_ai_radar_companies,
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
    def test_reacceleration_alert_is_secondary_and_accepts_rerated_company(self):
        linked_event = {
            **evidence("known-1"), "age_band": "Fresh", "signal": "confirming",
            "company": "Known AI Supplier", "ticker": "KNOWN", "related_tickers": [],
            "company_identities": [{"company": "Known AI Supplier", "ticker": "KNOWN",
                                    "exchange": "", "listing_status": "Public"}],
            "new_information": "Orders and backlog accelerated after a new customer deployment.",
        }
        beneficiary = {
            "company": "Known AI Supplier", "ticker": "KNOWN", "listing_status": "Public",
            "evidence_ids": ["known-1"], "price_discovery_stage": "Already Ran",
            "already_priced_in": "YES", "radar_rank_score": 31,
        }
        rows = [{"trend": "Compute", "confirming_evidence": [linked_event],
                 "beneficiary_records": [beneficiary]}]
        market_data = {"securities": {"KNOWN": {
            "current_price": 123.45, "price_date": "2026-08-28", "currency": "USD",
            "data_status": "current",
            "returns": {"daily": 6.2}, "volume_vs_20d_average": 2.1,
            "macd": {"improving": True, "crossover": "bullish"},
            "entry_inputs": {"breakout_volume_ratio": 1.5},
            "watchlist_entry_readiness": {"ai": {"state_key": "breakout-confirmed",
                "state": "Breakout Confirmed", "entry_guidance": "Breakout confirmed."}},
        }}}
        original = deepcopy(rows)
        result = build_ai_reacceleration_alerts(rows, market_data)
        self.assertEqual(result["alert_count"], 1)
        alert = result["alerts"][0]
        self.assertEqual(alert["ticker"], "KNOWN")
        self.assertEqual(alert["entry_stage"], "Breakout")
        self.assertEqual(alert["action"], "BUY")
        self.assertEqual(alert["price_discovery_stage"], "Already Ran")
        self.assertIn("Significant new catalyst/news", alert["trigger_types"])
        self.assertIn("Abnormal price/volume acceleration", alert["trigger_types"])
        self.assertIn("Renewed earnings/order/backlog acceleration", alert["trigger_types"])
        self.assertIn("Technical breakout/reversal", alert["trigger_types"])
        self.assertEqual(alert["source_events"][0]["matched_ticker"], "KNOWN")
        self.assertIn("Orders and backlog accelerated", alert["reacceleration_signal"])
        self.assertEqual(rows, original)

    def test_reacceleration_does_not_inherit_unlinked_category_news(self):
        rows = [{"trend": "Cooling", "confirming_evidence": [{
            **evidence("unlinked-1", trend="Cooling"), "age_band": "Fresh", "signal": "confirming",
        }], "beneficiary_records": [{
            "company": "Cooling Candidate", "ticker": "COOL", "listing_status": "Public",
            "evidence_ids": [], "price_discovery_stage": "Emerging", "already_priced_in": "NO",
        }]}]
        result = build_ai_reacceleration_alerts(rows, {"securities": {"COOL": {
            "returns": {"daily": 1}, "volume_vs_20d_average": 1,
            "data_status": "current",
            "watchlist_entry_readiness": {"ai": {"state_key": "base-building"}},
        }}})
        self.assertEqual(result["alerts"], [])

    def test_reacceleration_rejects_linked_id_when_event_ticker_is_different(self):
        wrong_company_event = {
            **evidence("wrong-company"), "age_band": "Fresh", "signal": "confirming",
            "new_information": "NVIDIA orders and backlog accelerated materially.",
        }
        rows = [{"trend": "Compute", "confirming_evidence": [wrong_company_event],
                 "beneficiary_records": [{
                     "company": "Unrelated Supplier", "ticker": "OTHER", "listing_status": "Public",
                     "evidence_ids": ["wrong-company"], "price_discovery_stage": "Emerging",
                     "already_priced_in": "NO",
                 }]}]
        result = build_ai_reacceleration_alerts(rows, {"securities": {"OTHER": {
            "current_price": 20, "data_status": "current", "returns": {"daily": 0, "one_month": -2},
            "volume_vs_20d_average": 0.8, "moving_averages": {"ma20": 21},
            "relative_strength": {"qqq": {"one_month": -3, "three_month": -1}},
            "macd": {"improving": False}, "entry_inputs": {},
            "watchlist_entry_readiness": {"ai": {"state_key": "base-building"}},
        }}})
        self.assertEqual(result["alerts"], [])

    def test_bottoming_alone_does_not_qualify_reacceleration(self):
        rows = [{"trend": "Compute", "confirming_evidence": [], "beneficiary_records": [{
            "company": "Base Builder", "ticker": "BASE", "listing_status": "Public",
            "evidence_ids": [], "price_discovery_stage": "Emerging", "already_priced_in": "NO",
        }]}]
        result = build_ai_reacceleration_alerts(rows, {"securities": {"BASE": {
            "current_price": 20, "data_status": "current", "returns": {"daily": 0, "one_month": -1},
            "volume_vs_20d_average": 0.9, "moving_averages": {"ma20": 21},
            "relative_strength": {"qqq": {"one_month": -2, "three_month": -1}},
            "macd": {"improving": True}, "entry_inputs": {},
            "watchlist_entry_readiness": {"ai": {"state_key": "base-building"}},
        }}})
        self.assertEqual(result["alerts"], [])

    def test_reacceleration_action_is_derived_from_entry_stage_only(self):
        event = {
            **evidence("company-catalyst"), "age_band": "Fresh", "signal": "confirming",
            "company": "Action Test", "ticker": "ACTN", "related_tickers": [],
            "company_identities": [{"company": "Action Test", "ticker": "ACTN",
                                    "exchange": "", "listing_status": "Public"}],
        }
        beneficiary = {"company": "Action Test", "ticker": "ACTN", "listing_status": "Public",
                       "evidence_ids": ["company-catalyst"]}
        expected = {"deterioration": ("Falling", "WAIT"),
                    "base-building": ("Bottoming", "WATCH"),
                    "near-buy-zone": ("Reversal", "WATCH / SCALE IN"),
                    "buy-zone": ("Entry Zone", "BUY / SCALE IN"),
                    "breakout-confirmed": ("Breakout", "BUY"),
                    "extended": ("Extended", "DO NOT CHASE")}
        for state_key, (stage, action) in expected.items():
            market = {"securities": {"ACTN": {"data_status": "current", "returns": {},
                "relative_strength": {"qqq": {}}, "moving_averages": {}, "entry_inputs": {},
                "macd": {}, "watchlist_entry_readiness": {"ai": {"state_key": state_key}}}}}
            alert = build_ai_reacceleration_alerts(
                [{"trend": "Compute", "confirming_evidence": [event],
                  "beneficiary_records": [beneficiary]}], market)["alerts"][0]
            self.assertEqual((alert["entry_stage"], alert["action"]), (stage, action))

    def test_manual_market_context_does_not_create_radar_scores(self):
        snapshot = {
            "ticker": "TEST", "current_price": 20, "returns": {"one_month": 2, "three_month": -4, "six_month": -8},
            "fifty_two_week_position": 35, "data_status": "current",
            "watchlist_entry_readiness": {"ai": {"state_key": "base-building", "state": "Base Building",
                                                       "entry_timing_score": 60, "entry_guidance": "Wait."}},
        }
        context = build_manual_radar_market_context({"securities": {"TEST": snapshot}})["TEST"]["ai"]
        self.assertFalse(context["scores_available"])
        self.assertIn("does not create a score", context["score_note"])
        self.assertEqual(context["entry_stage"]["stage"], "Bottoming")
        self.assertEqual(context["price_discovery_stage"], "Early Discovery")

    def test_already_ran_and_priced_in_penalty_changes_actual_rank(self):
        base = {
            "category": "Bottleneck/Picks-and-Shovels", "market_cap_bucket": "Mid",
            "profile_matches": ["capacity", "specialized systems"], "evidence_ids": ["event-1"],
            "thesis_evidence": [{"basis": "Specialized capacity is a documented supply bottleneck.",
                                 "evidence_types": ["Industry Position"]}],
            "confirmation_evidence": [{"basis": "Orders and backlog accelerated.",
                                       "evidence_types": ["Orders / Backlog"]}],
            "score_components": [
                {"label": "Trend Exposure", "score": 26},
                {"label": "Revenue Sensitivity", "score": 20},
                {"label": "Evidence Quality", "score": 9},
            ],
            "expectation": {"state": "Fairly Priced", "score": 8, "maximum": 15, "signals": []},
        }
        early = ai_early_opportunity_scores({**base, "market_data": {
            "returns": {"one_month": -2, "three_month": -8, "six_month": -12},
            "fifty_two_week_position": 35,
        }})
        ran = ai_early_opportunity_scores({**base, "market_data": {
            "returns": {"one_month": 20, "three_month": 65, "six_month": 110},
            "fifty_two_week_position": 98,
        }})
        self.assertEqual(early["priced_in_penalty"], 6)
        self.assertEqual(ran["priced_in_penalty"], 25)
        self.assertGreater(early["radar_rank_score"], ran["radar_rank_score"])
        self.assertGreater(early["multibagger_potential_score"], ran["multibagger_potential_score"])

    def test_global_focus_targets_unique_companies_and_preserves_categories(self):
        rows = []
        for category_index in range(10):
            beneficiaries = []
            for company_index in range(4):
                ticker = "SHARED" if company_index == 0 else f"C{category_index}{company_index}"
                beneficiaries.append({"company": ticker, "ticker": ticker, "category": "Direct",
                                      "beneficiary_relevance": 90 - company_index,
                                      "market_cap_bucket": "Small/Emerging" if company_index == 3 else "Large"})
            rows.append({"trend": f"Category {category_index}", "trend_strength": 80 - category_index,
                         "data_completeness": 75, "beneficiary_records": beneficiaries})
        focused, diagnostics = focus_ai_radar_companies(rows, target=24)
        tickers = [item["ticker"] for row in focused for item in row["beneficiary_records"]]
        self.assertEqual(len(tickers), 24)
        self.assertEqual(len(set(tickers)), 24)
        self.assertEqual(len(focused), 10)
        self.assertEqual(diagnostics["unique_companies_after"], 24)
        self.assertLessEqual(tickers.count("SHARED"), 1)

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
