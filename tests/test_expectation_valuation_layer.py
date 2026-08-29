import unittest
from datetime import date, datetime, timedelta, timezone

from scripts.update_news_dashboard import (
    BIOTECH_CATALYSTS,
    attach_market_context,
    build_ai_radar,
    build_market_data_layer,
    expectation_assessment,
    score_biotech_catalyst,
)


RUN_AT = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def series(symbol, start=100, step=0.35, sessions=300):
    start_date = date(2025, 7, 1)
    return {"symbol": symbol, "source": "Synthetic test series", "currency": "USD", "rows": [
        {"date": (start_date + timedelta(days=index)).isoformat(), "close": start + step * index,
         "volume": 1_000_000 + index * 1000}
        for index in range(sessions)
    ]}


def nasdaq_record(ticker, target, yearly_eps, revisions_up=5, revisions_down=1, days_to_cover=6.0):
    return {"ticker": ticker, "retrieved_at": RUN_AT.isoformat(), "payloads": {
        "summary": {"summaryData": {"MarketCap": {"value": "12,000,000,000"},
                                      "OneYrTarget": {"value": f"${target}"}}},
        "ratings": {"meanRatingType": "Buy", "ratingsSummary": f"Based on 20 analysts offering recommendations for '{ticker}'."},
        "forecast": {"quarterlyForecast": {"rows": [{"fiscalEnd": "Dec 2026", "consensusEPSForecast": 2.5,
                                                         "noOfEstimates": 12, "up": revisions_up, "down": revisions_down}]},
                     "yearlyForecast": {"rows": [{"fiscalEnd": "Dec 2027", "consensusEPSForecast": yearly_eps,
                                                    "noOfEstimates": 15, "up": revisions_up, "down": revisions_down}]}},
        "short_interest": {"shortInterestTable": {"rows": [
            {"settlementDate": "08/14/2026", "interest": "12,000,000", "avgDailyShareVolume": "2,000,000", "daysToCover": days_to_cover},
            {"settlementDate": "07/31/2026", "interest": "10,000,000", "avgDailyShareVolume": "2,100,000", "daysToCover": 4.8},
        ]}},
    }}


def expectation_layer():
    series_by_symbol = {
        "^GSPC": series("^GSPC", 4000, 2), "^IXIC": series("^IXIC", 15000, 7),
        "^DJI": series("^DJI", 34000, 8), "^RUT": series("^RUT", 1900, .7),
        "QQQ": series("QQQ", 400, .7), "XBI": series("XBI", 90, .08),
        "NVDA": series("NVDA", 100, .35), "BEAM": series("BEAM", 25, .06),
    }
    expectations = {"NVDA": nasdaq_record("NVDA", 280, 9), "BEAM": nasdaq_record("BEAM", 65, -1)}
    return build_market_data_layer({}, RUN_AT, series_by_symbol=series_by_symbol,
                                   market_caps={}, expectations_by_ticker=expectations)


class ExpectationValuationLayerTests(unittest.TestCase):
    def test_shared_record_keeps_source_dated_inputs_and_classifies(self):
        layer = expectation_layer(); record = layer["securities"]["NVDA"]["expectation_data"]
        self.assertEqual(set(record["available_input_groups"]), {"valuation", "price_run_up", "analyst_consensus", "positioning"})
        self.assertIsNotNone(record["valuation"]["forward_pe"])
        self.assertEqual(record["analyst_consensus"]["net_revisions_4w"], 4)
        self.assertEqual(record["short_interest"]["settlement_date"], "08/14/2026")
        self.assertTrue(record["sources"])
        assessment = expectation_assessment(layer["securities"]["NVDA"], "ai", 15)
        self.assertEqual(assessment["state"], "Underpriced")
        self.assertIsNotNone(assessment["score"])

    def test_missing_inputs_remain_data_insufficient(self):
        result = expectation_assessment({"expectation_data": {"data_status": "current",
            "available_input_groups": ["price_run_up"], "price_run_up": {"three_month_pct": 40}}}, "ai", 15)
        self.assertEqual(result["state"], "Data Insufficient")
        self.assertIsNone(result["score"])

    def test_crowded_and_fair_states_are_distinct(self):
        crowded = {"expectation_data": {"data_status": "current",
            "available_input_groups": ["valuation", "price_run_up", "analyst_consensus"],
            "valuation": {"target_upside_pct": -5, "forward_pe": 65},
            "price_run_up": {"three_month_pct": 35},
            "analyst_consensus": {"net_revisions_4w": -3}, "short_interest": {}, "sources": []}}
        fair = {"expectation_data": {"data_status": "current",
            "available_input_groups": ["valuation", "price_run_up", "analyst_consensus"],
            "valuation": {"target_upside_pct": 5, "forward_pe": 30},
            "price_run_up": {"three_month_pct": 5},
            "analyst_consensus": {"net_revisions_4w": 0}, "short_interest": {}, "sources": []}}
        self.assertEqual(expectation_assessment(crowded, "ai", 15)["state"], "Crowded / Priced In")
        self.assertEqual(expectation_assessment(fair, "ai", 15)["state"], "Fairly Priced")

    def test_ai_radar_uses_beneficiary_expectation_data(self):
        event = {"event_id": "nvda-results", "event_date": "2026-08-28T12:00:00+00:00",
                 "company": "NVIDIA", "ticker": "NVDA", "exchange": "", "listing_status": "Public",
                 "company_identities": [{"company": "NVIDIA", "ticker": "NVDA", "exchange": "", "listing_status": "Public"}],
                 "event_type": "Financial Results", "direction": "Expanding", "news_importance_score": 95,
                 "new_information": "Revenue increased as customers deployed additional AI compute.",
                 "affected_trends": ["Compute"], "direct_effects": ["Compute"], "second_order_effects": []}
        rows = build_ai_radar({"radar_evidence_interface": {"events": [event]}}, [], RUN_AT, expectation_layer())
        compute = next(row for row in rows if row["trend"] == "Compute")
        self.assertEqual(compute["expectation_state"], "Underpriced")
        self.assertIsNotNone(compute["opportunity_score"])
        factor = next(item for item in compute["score_components"] if item["key"] == "expectation_gap_valuation")
        self.assertIsNotNone(factor["score"])

    def test_biotech_radar_uses_expectation_layer_without_fabrication(self):
        item = next(row for row in BIOTECH_CATALYSTS if row["ticker"] == "BEAM")
        result = score_biotech_catalyst(item, date(2026, 8, 29), market_data=expectation_layer())
        self.assertEqual(result["expectation_state"], "Underpriced")
        self.assertIsNotNone(result["expectation_gap_score"])
        self.assertEqual(result["expectation"]["coverage"], 4)

    def test_high_conviction_rows_receive_final_ranking_inputs(self):
        rows = attach_market_context([
            {"rank": 2, "company": "Beam Therapeutics", "ticker": "BEAM"},
            {"rank": 1, "company": "NVIDIA", "ticker": "NVDA"},
        ], expectation_layer(), "ai", rank_opportunities=True)
        self.assertEqual([row["rank"] for row in rows], [1, 2])
        self.assertTrue(all(row.get("final_ranking_score") is not None for row in rows))
        self.assertTrue(all(any(item["key"] == "expectation_gap" for item in row["ranking_inputs"]) for row in rows))
        self.assertTrue(all("Expectation state:" in row["timing_support"]["rationale"] for row in rows))


if __name__ == "__main__":
    unittest.main()
