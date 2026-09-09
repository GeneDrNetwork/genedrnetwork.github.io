import unittest

from scripts.swing_trade import build_swing_trade_engine, stage_transition, technical_setup


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
    def test_large_one_day_gain_alone_does_not_confirm_transition(self):
        previous = {"stage": "Bottoming", "technical": {"returns": {"daily": 0}}}
        current = {"state": "Early Reversal", "price_date": "2026-08-29",
                   "returns": {"daily": 6}, "macd": {}, "relative_strength": {}}
        result = stage_transition(previous, current)
        self.assertFalse(result["fresh_favorable_transition"])
        self.assertTrue(result["large_one_day_gain_only"])

    def test_full_screened_universe_can_enter_on_fresh_favorable_transition(self):
        prior_technical = {
            "current_price": 92, "ma20": 99, "ma50": 106,
            "price_vs_ma20_pct": -7.1, "price_vs_ma50_pct": -13.2,
            "recent_low": 85, "macd": {"improving": False}, "returns": {"daily": 0},
        }
        previous = {"stage_tracking": [{
            "ticker": "TEST", "stage": "Bottoming", "as_of": "2026-08-28",
            "last_changed_on": "2026-08-25", "technical": prior_technical,
        }], "opportunities": []}
        market = {"securities": {"TEST": snapshot("early")}}
        result = build_swing_trade_engine(
            candidates(), market, [], biotech_radar(), previous_section=previous)
        row = result["opportunities"][0]
        self.assertEqual(row["stage_transition"]["transition"], "Bottoming → Early Reversal")
        self.assertTrue(row["stage_transition"]["fresh_favorable_transition"])
        self.assertEqual(row["stage_transition"]["days_since_change"], 0)
        self.assertEqual(result["stage_tracking"][0]["ticker"], "TEST")

    def test_days_since_change_persists_when_stage_is_unchanged(self):
        current = technical_setup(snapshot("entry"))
        previous = {"stage": "Entry Zone", "last_changed_on": "2026-08-25",
                    "as_of": "2026-08-28", "technical": current}
        transition = stage_transition(previous, current, "biotech")
        self.assertFalse(transition["changed"])
        self.assertEqual(transition["days_since_change"], 4)

    def test_recent_transition_label_and_priority_persist_for_five_days(self):
        current = technical_setup(snapshot("early"))
        previous = {
            "stage": "Early Reversal", "last_changed_on": "2026-08-25", "as_of": "2026-08-28",
            "technical": current, "transition": {
                "previous_stage": "Bottoming", "current_stage": "Early Reversal",
                "fresh_favorable_transition": True, "signals": ["Higher trailing low", "MACD reversal momentum improved"],
            },
        }
        transition = stage_transition(previous, current, "biotech")
        self.assertEqual(transition["transition"], "Bottoming → Early Reversal")
        self.assertEqual(transition["days_since_change"], 4)
        self.assertTrue(transition["fresh_favorable_transition"])

    def test_failed_reversal_is_tracked_as_technical_deterioration(self):
        previous = {"stage": "Early Reversal", "technical": {
            "support": 95, "current_price": 98, "price_vs_ma20_pct": 1,
            "macd": {"improving": True},
        }}
        current = {"state": "Bottoming", "price_date": "2026-08-29", "current_price": 90,
                   "price_vs_ma20_pct": -5, "macd": {"crossover": "bearish"},
                   "returns": {}, "relative_strength": {}}
        transition = stage_transition(previous, current)
        self.assertTrue(transition["failed_reversal"])
        self.assertEqual(transition["current_stage"], "Failed Reversal / Technical Deterioration")

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

    def test_fresh_confirmed_transition_ranks_ahead_of_static_entry_zone(self):
        pool = {"candidates": [
            {"company": "Fresh Bio", "ticker": "FRESH", "domain": "biotech"},
            {"company": "Static Bio", "ticker": "STATIC", "domain": "biotech"},
        ]}
        fresh_snapshot, static_snapshot = snapshot("early"), snapshot("entry")
        market = {"securities": {"FRESH": fresh_snapshot, "STATIC": static_snapshot}}
        radar = [
            {**biotech_radar()[0], "ticker": "FRESH"},
            {**biotech_radar()[0], "ticker": "STATIC"},
        ]
        previous = {"stage_tracking": [
            {"ticker": "FRESH", "stage": "Bottoming", "as_of": "2026-08-28",
             "technical": {"current_price": 92, "ma20": 99, "ma50": 106,
                           "price_vs_ma20_pct": -7.1, "price_vs_ma50_pct": -13.2,
                           "recent_low": 85, "macd": {"improving": False}, "returns": {"daily": 0}}},
            {"ticker": "STATIC", "stage": "Entry Zone", "as_of": "2026-08-28",
             "technical": technical_setup(static_snapshot)},
        ]}
        result = build_swing_trade_engine(pool, market, [], radar, previous_section=previous)
        self.assertEqual([row["ticker"] for row in result["opportunities"]], ["FRESH", "STATIC"])

    def test_swing_cards_show_compact_stage_transition(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parents[1] / "assets" / "news-dashboard.js").read_text()
        self.assertIn("transition.previous_stage", script)
        self.assertIn("since change", script)
        self.assertIn("swing-transition", script)


if __name__ == "__main__":
    unittest.main()
