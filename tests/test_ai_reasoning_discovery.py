import unittest
from datetime import datetime, timezone

from scripts.ai_reasoning_discovery import build_ai_reasoning_discovery, credible_profile_match
from scripts.update_news_dashboard import (
    COMPANY_TICKER_INDEX,
    build_ai_radar,
    discover_candidate_pool,
    fetch_listed_company_universe,
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


def physical_ai_section():
    event = {
        "event_id": "robotics-1", "event_date": "2026-08-29T12:00+00:00",
        "headline": "Machine vision and industrial automation move into early production deployment",
        "company": "Industry research", "ticker": "N/A", "exchange": "", "listing_status": "Non-public",
        "company_identities": [], "event_type": "Industry Adoption", "direction": "Expanding",
        "confirmation_status": "NEW", "news_importance_score": 84,
        "new_information": "Industrial automation suppliers are integrating machine vision sensors into robotics systems.",
        "affected_trends": ["Physical AI / Robotics"], "direct_effects": ["Physical AI / Robotics"],
        "second_order_effects": ["Edge AI"], "evidence_sources": [], "archived": False,
    }
    return {"radar_evidence_interface": {"events": [event]}}


class AiReasoningDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.listed = [{"company": "Lumentum Holdings Inc.", "ticker": "LITE", "exchange": "",
                        "listing_status": "Public", "resolution": "test listed-company universe"},
                       {"company": "Bandwidth Inc.", "ticker": "BAND", "exchange": "",
                        "listing_status": "Public", "resolution": "test listed-company universe"}]

    def test_generic_digital_infrastructure_does_not_imply_data_center_relevance(self):
        wireless = {
            "company": "Example Wireless Infrastructure",
            "ticker": "EXWI",
            "listing_status": "Public",
            "industry": "Telecommunications Equipment",
            "description": "Owns and operates shared wireless communications infrastructure and cell towers.",
        }
        data_center = {
            "company": "Example Compute Facilities",
            "ticker": "EXCF",
            "listing_status": "Public",
            "industry": "EDP Services",
            "description": "Develops and operates data centers for high-performance computing workloads.",
        }
        self.assertFalse(credible_profile_match(wireless, "Data Centers")["credible"])
        self.assertTrue(credible_profile_match(data_center, "Data Centers")["credible"])

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
        self.assertEqual(lumentum["opportunity_stage"], "Early Beneficiary")
        self.assertTrue(lumentum["thesis_evidence"])
        self.assertEqual(lumentum["confirmation_evidence"], [])
        self.assertTrue(lumentum["confirmation_missing"])
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

    def test_commercial_confirmation_and_established_stages_are_separate_from_thesis(self):
        section = news_section()
        first = section["radar_evidence_interface"]["events"][0]
        first["new_information"] += " A named customer signed a contract for initial production shipments."
        commercial = build_ai_reasoning_discovery(section, self.listed)
        lumentum = next(row for row in commercial["stock_candidates"] if row["ticker"] == "LITE")
        self.assertEqual(lumentum["opportunity_stage"], "Commercial Confirmation")
        self.assertTrue(lumentum["thesis_evidence"])
        self.assertTrue(lumentum["confirmation_evidence"])

        second = dict(first, event_id="optical-2", event_date="2026-08-30T12:00+00:00",
                      headline="Lumentum reports optical AI backlog and revenue growth",
                      new_information="Lumentum reported backlog, customer orders, and revenue growth for optical AI products.")
        section["radar_evidence_interface"]["events"].append(second)
        established = build_ai_reasoning_discovery(section, self.listed)
        lumentum = next(row for row in established["stock_candidates"] if row["ticker"] == "LITE")
        self.assertEqual(lumentum["opportunity_stage"], "Established Beneficiary")
        self.assertGreaterEqual(len(lumentum["confirmation_evidence"]), 2)

    def test_missing_identity_is_not_fabricated(self):
        discovery = build_ai_reasoning_discovery(news_section(), [])
        self.assertNotIn("LITE", {row["ticker"] for row in discovery["stock_candidates"]})
        self.assertEqual(discovery["policy"]["missing_data"],
                         "Unresolved company identity remains unresolved and is not converted into a ticker.")

    def test_profile_validated_company_outside_focused_universe_enters_radar(self):
        emerging = {
            "company": "Adaptive Motion Systems Inc.", "ticker": "AMSX", "exchange": "NASDAQ",
            "listing_status": "Public", "resolution": "test broad listed universe",
            "sector": "Industrials", "industry": "Industrial automation",
            "description": "Develops machine vision sensors and motion control for robotics systems.",
            "market_cap": 850_000_000, "profile_source": "Test exchange company profile",
            "source_date": "2026-08-28", "source_link": "https://example.test/amsx",
        }
        irrelevant = {
            "company": "General Consumer Stores Inc.", "ticker": "GCST", "exchange": "NYSE",
            "listing_status": "Public", "resolution": "test broad listed universe",
            "sector": "Consumer", "industry": "Retail", "description": "Operates general merchandise stores.",
            "market_cap": 900_000_000, "profile_source": "Test exchange company profile",
            "source_date": "2026-08-28", "source_link": "https://example.test/gcst",
        }
        self.assertNotIn(emerging["ticker"], COMPANY_TICKER_INDEX)
        discovery = build_ai_reasoning_discovery(physical_ai_section(), [emerging, irrelevant])
        discovered = {row["ticker"]: row for row in discovery["stock_candidates"]}
        self.assertIn(emerging["ticker"], discovered)
        self.assertNotIn(irrelevant["ticker"], discovered)
        candidate = discovered[emerging["ticker"]]
        self.assertEqual(candidate["discovery_method"], "category_profile_validation")
        self.assertEqual(candidate["market_cap_bucket"], "Small/Emerging")
        self.assertEqual(candidate["opportunity_stage"], "Early Beneficiary")
        self.assertTrue(candidate["confirmation_missing"])
        self.assertTrue(any(item.get("source_link") == emerging["source_link"]
                            for item in candidate["thesis_evidence"]))

        radar = build_ai_radar(physical_ai_section(), [], RUN_AT, ai_reasoning_discovery=discovery)
        physical = next(row for row in radar if row["trend"] == "Physical AI / Robotics")
        self.assertIn(emerging["ticker"], {row["ticker"] for row in physical["beneficiary_records"]})

    def test_profile_discovery_preserves_size_diversity_without_size_scoring(self):
        profiles = []
        for index in range(5):
            profiles.append({
                "company": f"Established Optical Systems {index}", "ticker": f"EO{index}",
                "exchange": "NASDAQ", "listing_status": "Public",
                "description": "Optical networking equipment and fiber optic interconnect systems.",
                "market_cap": 250_000_000_000 + index, "profile_source": "Test exchange profile",
            })
        smaller = {
            "company": "Emerging Photonics Systems", "ticker": "EPSX", "exchange": "NASDAQ",
            "listing_status": "Public", "description": "Develops optical components.",
            "market_cap": 700_000_000, "profile_source": "Test exchange profile",
        }
        profiles.append(smaller)
        discovery = build_ai_reasoning_discovery(news_section(), profiles)
        profile_rows = [row for row in discovery["stock_candidates"]
                        if row.get("discovery_method") == "category_profile_validation"
                        and "Networking/Optical" in row.get("parent_tracks", [])]
        self.assertEqual(len(profile_rows), 5)
        self.assertIn(smaller["ticker"], {row["ticker"] for row in profile_rows})
        self.assertTrue(all("market_cap" not in component
                            for row in profile_rows for component in row.get("thesis_evidence", [])))

    def test_general_listed_universe_retains_discovery_metadata(self):
        def fetcher(_url, timeout):
            self.assertEqual(timeout, 20)
            return {"rows": [{
                "symbol": "EMRG", "name": "Emerging Automation Inc. Common Stock", "exchange": "NASDAQ",
                "sector": "Industrials", "industry": "Industrial automation",
                "country": "United States", "marketCap": "$750,000,000",
            }, {"symbol": "EMRGW", "name": "Emerging Automation Inc. Warrant", "marketCap": "100"},
               {"symbol": "AIF", "name": "Artificial Intelligence Opportunity Fund", "marketCap": "100"}]}

        companies, status = fetch_listed_company_universe(RUN_AT, fetcher)
        self.assertEqual([row["ticker"] for row in companies], ["EMRG"])
        self.assertEqual(companies[0]["industry"], "Industrial automation")
        self.assertEqual(companies[0]["market_cap"], 750_000_000)
        self.assertTrue(companies[0]["source_link"].endswith("/emrg"))
        self.assertEqual(status["records_with_industry"], 1)
        self.assertEqual(status["records_with_market_cap"], 1)
        self.assertEqual(status["non_company_securities_excluded"], 2)

    def test_category_specific_validation_blocks_news_identity_leakage(self):
        event = {
            "event_id": "infra-1", "event_date": "2026-08-29T12:00+00:00",
            "headline": "Market Analytics publishes AI infrastructure forecast",
            "company": "Market Analytics", "ticker": "RATE", "listing_status": "Public",
            "company_identities": [{"company": "Market Analytics", "ticker": "RATE",
                                    "listing_status": "Public", "exchange": ""}],
            "event_type": "Industry Research", "direction": "Expanding", "confirmation_status": "NEW",
            "news_importance_score": 85,
            "new_information": "AI power demand is increasing requirements for power distribution and liquid cooling.",
            "affected_trends": ["Data Centers"], "direct_effects": ["Data Centers"],
            "second_order_effects": ["Power/Electrical", "Cooling"], "evidence_sources": [],
        }
        section = {"radar_evidence_interface": {"events": [event]}}
        profiles = [
            {"company": "Market Analytics", "ticker": "RATE", "listing_status": "Public",
             "industry": "Business Services", "description": "Provides ratings, benchmarks and market research."},
            {"company": "Critical Infrastructure Systems", "ticker": "CISX", "listing_status": "Public",
             "industry": "Electrical Products",
             "description": "Supplies data center power distribution equipment and liquid cooling solutions.",
             "market_cap": 1_200_000_000},
        ]
        discovery = build_ai_reasoning_discovery(section, profiles)
        candidates = {row["ticker"]: row for row in discovery["stock_candidates"]}
        self.assertNotIn("RATE", candidates)
        self.assertIn("CISX", candidates)
        self.assertIn("Power/Electrical", candidates["CISX"]["parent_tracks"])
        self.assertIn("Cooling", candidates["CISX"]["parent_tracks"])

        radar = build_ai_radar(section, [], RUN_AT, ai_reasoning_discovery=discovery)
        power = next(row for row in radar if row["trend"] == "Power/Electrical")
        cooling = next(row for row in radar if row["trend"] == "Cooling")
        self.assertEqual({row["ticker"] for row in power["beneficiary_records"]}, {"CISX"})
        self.assertEqual({row["ticker"] for row in cooling["beneficiary_records"]}, {"CISX"})


if __name__ == "__main__":
    unittest.main()
