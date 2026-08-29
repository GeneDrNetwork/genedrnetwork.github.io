import unittest
from datetime import date, datetime, timedelta, timezone

from scripts.update_news_dashboard import (
    BIOTECH_CATALYSTS,
    attach_market_context,
    build_ai_radar,
    build_market_data_layer,
    calculate_market_technicals,
    expectation_assessment,
    market_timing_signal,
    score_biotech_catalyst,
)


RUN_AT = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def series(symbol, start=100, step=0.35, sessions=300, volume=1_000_000):
    start_date = date(2025, 7, 1)
    return {
        "symbol": symbol,
        "source": "Synthetic test series",
        "currency": "USD",
        "rows": [
            {"date": (start_date + timedelta(days=index)).isoformat(),
             "close": start + step * index + (index % 7) * 0.05,
             "volume": volume + index * 1000}
            for index in range(sessions)
        ],
    }


def market_layer():
    series_by_symbol = {
        "^GSPC": series("^GSPC", 4000, 2.0), "^IXIC": series("^IXIC", 15000, 7.0),
        "^DJI": series("^DJI", 34000, 8.0), "^RUT": series("^RUT", 1900, 0.7),
        "QQQ": series("QQQ", 400, 0.7), "XBI": series("XBI", 90, 0.08),
        "NVDA": series("NVDA", 100, 0.5), "BEAM": series("BEAM", 25, 0.06),
    }
    return build_market_data_layer({}, RUN_AT, series_by_symbol=series_by_symbol,
                                   market_caps={"NVDA": 4_000_000_000_000, "BEAM": 3_000_000_000})


class MarketTechnicalLayerTests(unittest.TestCase):
    def test_calculates_requested_market_fields(self):
        record = calculate_market_technicals("TEST", series("TEST"))
        self.assertIsNotNone(record["current_price"])
        self.assertIsNotNone(record["moving_averages"]["ma20"])
        self.assertIsNotNone(record["moving_averages"]["ma50"])
        self.assertIsNotNone(record["moving_averages"]["ma200"])
        self.assertIsNotNone(record["returns"]["one_month"])
        self.assertIsNotNone(record["returns"]["three_month"])
        self.assertIsNotNone(record["returns"]["six_month"])
        self.assertIsNotNone(record["rsi_14"])
        self.assertIsNotNone(record["macd"]["value"])
        self.assertIsNotNone(record["volume_vs_20d_average"])
        self.assertIsNotNone(record["fifty_two_week_position"])

    def test_shared_layer_has_benchmarks_relative_strength_and_missing_cap(self):
        layer = market_layer()
        nvda = layer["securities"]["NVDA"]
        self.assertEqual(layer["schema_version"], "shared-market-expectation-v1")
        self.assertEqual(nvda["market_cap"], 4_000_000_000_000)
        self.assertIsNotNone(nvda["relative_strength"]["sp500"]["three_month"])
        self.assertIsNotNone(nvda["relative_strength"]["qqq"]["three_month"])
        self.assertIsNotNone(nvda["relative_strength"]["xbi"]["three_month"])
        self.assertIsNone(layer["securities"].get("AMD"))

    def test_failed_refresh_retains_stale_record_without_signal(self):
        prior = {"market_data": {"securities": {"AMD": {
            "ticker": "AMD", "current_price": 150, "moving_averages": {"ma50": 140, "ma200": 130},
            "returns": {}, "macd": {}, "relative_strength": {}, "data_status": "current",
        }}}}
        layer = build_market_data_layer(prior, RUN_AT, series_by_symbol={}, market_caps={})
        self.assertEqual(layer["securities"]["AMD"]["data_status"], "stale")
        self.assertEqual(market_timing_signal(layer["securities"]["AMD"], "ai")["signal"], "Insufficient Data")

    def test_ai_radar_market_confirmation_uses_beneficiary_market_data(self):
        layer = market_layer()
        event = {
            "event_id": "nvda-results", "event_date": "2026-08-28T12:00:00+00:00",
            "company": "NVIDIA", "ticker": "NVDA", "exchange": "", "listing_status": "Public",
            "company_identities": [{"company": "NVIDIA", "ticker": "NVDA", "exchange": "", "listing_status": "Public"}],
            "event_type": "Financial Results", "direction": "Expanding", "news_importance_score": 95,
            "new_information": "Revenue increased as customers deployed additional AI compute.",
            "affected_trends": ["Compute"], "direct_effects": ["Compute"], "second_order_effects": [],
        }
        rows = build_ai_radar({"radar_evidence_interface": {"events": [event]}}, [], RUN_AT, layer)
        compute = next(row for row in rows if row["trend"] == "Compute")
        market_factor = next(component for component in compute["score_components"] if component["key"] == "market_confirmation")
        self.assertIsNotNone(market_factor["score"])
        self.assertIn("NVDA", compute["market_confirmation"]["tickers"])
        beneficiary = next(item for item in compute["beneficiary_records"] if item["ticker"] == "NVDA")
        self.assertIsNotNone(beneficiary["market_data"])

    def test_biotech_radar_uses_xbi_and_stock_technicals_without_news_scoring(self):
        layer = market_layer()
        item = next(row for row in BIOTECH_CATALYSTS if row["ticker"] == "BEAM")
        result = score_biotech_catalyst(item, date(2026, 8, 29), market_data=layer)
        self.assertIsNotNone(result["sector_trend_score"])
        self.assertIsNotNone(result["timing_technicals_score"])
        self.assertIsNone(result["expectation_gap_score"])
        self.assertIsNotNone(result["market_data"])

    def test_opportunities_and_watchlists_receive_timing_support(self):
        layer = market_layer()
        rows = attach_market_context([{"company": "NVIDIA", "ticker": "NVDA"}], layer, "ai")
        self.assertIsNotNone(rows[0]["market_data"])
        self.assertIn(rows[0]["timing_support"]["signal"], ("Buy", "Hold", "Reduce", "Sell"))
        self.assertIsNotNone(market_timing_signal(rows[0]["market_data"], "ai")["support_score"])


if __name__ == "__main__":
    unittest.main()
