import unittest

from scripts.swing_trade import build_swing_trade_engine, technical_setup


def snapshot(state="entry"):
    price, ma20, ma50 = (100, 98, 102)
    macd = {"histogram": .4, "previous_histogram": .2, "improving": True, "crossover": None}
    distance = 12
    proximity = -5
    volume = 1.0
    if state == "early":
        price, ma20, ma50 = 96, 98, 105
    elif state == "bottoming":
        price, ma20, ma50 = 93, 98, 105
        macd = {"histogram": -.3, "previous_histogram": -.2, "improving": False, "crossover": None}
    elif state == "breakout":
        price, ma20, ma50, proximity, volume = 102, 98, 99, 2, 1.3
    elif state == "extended":
        price, ma20, ma50, distance = 125, 100, 102, 42
    return {
        "ticker": "TEST", "current_price": price, "price_date": "2026-08-29",
        "currency": "USD", "source": "Test daily data", "data_status": "current",
        "moving_averages": {"ma20": ma20, "ma50": ma50, "ma200": 110},
        "returns": {"one_month": 5, "three_month": -25, "six_month": -35},
        "rsi_14": 52, "macd": macd, "volume_vs_20d_average": volume,
        "fifty_two_week_position": 20,
        "entry_inputs": {
            "fifty_two_week_high": 165, "fifty_two_week_low": 80,
            "drawdown_from_fifty_two_week_high_pct": -39.4,
            "recent_low_63d": 89, "distance_from_recent_low_pct": distance,
            "tight_range_20d_pct": 12, "base_duration_sessions": 42,
            "up_down_volume_ratio_20d": 1.4, "resistance_level": 100,
            "breakout_proximity_pct": proximity, "breakout_volume_ratio": volume,
            "invalidation_level": 89,
        },
    }


def candidates():
    return {"candidates": [{"company": "Test Bio", "ticker": "TEST", "domain": "biotech",
                             "exchange": "", "listing_status": "Public"}]}


def biotech_radar():
    return [{"company": "Test Bio", "ticker": "TEST", "program": "TB-1",
             "catalyst": "Phase 2 clinical results", "expected_timing": "Fourth quarter 2026",
             "opportunity_score": 70, "sources": [{"title": "Company clinical update",
                 "url": "https://example.com/clinical", "date": "2026-08-01"}]}]


class SwingTradeEngineTests(unittest.TestCase):
    def test_classifies_requested_technical_states(self):
        self.assertEqual(technical_setup(snapshot("entry"))["state"], "Entry Zone")
        self.assertEqual(technical_setup(snapshot("early"))["state"], "Early Reversal")
        self.assertEqual(technical_setup(snapshot("bottoming"))["state"], "Bottoming")
        self.assertEqual(technical_setup(snapshot("breakout"))["state"], "Breakout")
        self.assertEqual(technical_setup(snapshot("extended"))["state"], "Extended")

    def test_technical_step_runs_before_catalyst_and_extended_is_rejected(self):
        market = {"securities": {"TEST": snapshot("extended")}}
        result = build_swing_trade_engine(candidates(), market, [], biotech_radar())
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["coverage"]["technical_qualified"], 0)

    def test_missing_catalyst_cannot_create_opportunity(self):
        market = {"securities": {"TEST": snapshot("entry")}}
        result = build_swing_trade_engine(candidates(), market, [], [])
        self.assertEqual(result["coverage"]["technical_qualified"], 1)
        self.assertEqual(result["opportunities"], [])

    def test_source_backed_biotech_catalyst_completes_second_step(self):
        market = {"securities": {"TEST": snapshot("entry")}}
        result = build_swing_trade_engine(candidates(), market, [], biotech_radar())
        row = result["opportunities"][0]
        self.assertEqual(row["classification"], "Entry Zone")
        self.assertTrue(row["catalyst"]["credible"])
        self.assertEqual(row["catalyst"]["source_link"], "https://example.com/clinical")
        self.assertIn("Why", "Why This Swing Trade Opportunity")
        self.assertIn("why_chart_selected", row["why_this_swing_trade_opportunity"])

    def test_non_biotech_company_can_qualify_from_source_backed_news(self):
        pool = {"candidates": [{"company": "Test Technology", "ticker": "TEST", "domain": "ai"}]}
        market = {"securities": {"TEST": snapshot("early")}}
        news = {"stories": [{"ticker": "TEST", "related_tickers": [],
            "new_information": "The company announced a material customer deployment.",
            "event_type": "Commercial Event", "news_importance_score": 82,
            "source": "Company investor relations", "published_at": "2026-08-20",
            "source_link": "https://example.com/technology"}]}
        result = build_swing_trade_engine(pool, market, [], [], ai_news_section=news)
        self.assertEqual(result["opportunities"][0]["domain"], "ai")
        self.assertEqual(result["opportunities"][0]["classification"], "Early Reversal")

    def test_entry_zone_is_prioritized_over_bottoming(self):
        pool = {"candidates": [
            {"company": "Bottom Bio", "ticker": "BOT", "domain": "biotech"},
            {"company": "Entry Bio", "ticker": "ENT", "domain": "biotech"},
        ]}
        market = {"securities": {"BOT": snapshot("bottoming"), "ENT": snapshot("entry")}}
        radar = [
            {**biotech_radar()[0], "ticker": "BOT"},
            {**biotech_radar()[0], "ticker": "ENT"},
        ]
        result = build_swing_trade_engine(pool, market, [], radar)
        self.assertEqual([row["ticker"] for row in result["opportunities"]], ["ENT", "BOT"])


if __name__ == "__main__":
    unittest.main()
