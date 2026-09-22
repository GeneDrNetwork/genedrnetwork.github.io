import unittest
from pathlib import Path

from scripts.entry_timing import calculate_gap_continuation_inputs
from scripts.swing_trade import (
    assess_gap_continuation,
    assess_long_base_breakout,
    build_swing_trade_engine,
    select_swing_market_universe,
    stage_transition,
    technical_setup,
)


def market_snapshot(kind="base"):
    snapshot = {
        "ticker": "TEST", "current_price": 102, "price_date": "2026-09-18",
        "currency": "USD", "source": "Test OHLCV", "data_status": "current",
        "market_cap": 2_000_000_000,
        "moving_averages": {"ma20": 98, "ma50": 96, "ma200": 88},
        "returns": {"daily": 2, "one_month": 8, "three_month": 15, "six_month": 22},
        "rsi_14": 61, "macd": {"histogram": .5, "improving": True, "crossover": None},
        "volume_vs_20d_average": 1.5, "fifty_two_week_position": 75,
        "relative_strength": {
            "sp500": {"one_month": 4, "three_month": 6, "six_month": 8},
            "xbi": {"one_month": 5, "three_month": 7, "six_month": 9},
        },
        "entry_inputs": {
            "base_duration_sessions": 63, "base_range_pct": 15,
            "tight_range_20d_pct": 8, "volume_contraction_ratio": .8,
            "higher_low_confirmed": True, "resistance_level": 100,
            "breakout_proximity_pct": 2, "breakout_volume_ratio": 1.5,
            "short_term_high_reclaimed": True, "failed_breakout": False,
            "ma20_slope_10d_pct": 2, "ma50_slope_20d_pct": 1,
            "up_down_volume_ratio_20d": 1.4, "recent_low_63d": 90,
            "distance_from_recent_low_pct": 13, "range_zone_transitions_63d": 3,
            "invalidation_level": 95,
            "gap_up_continuation": {"detected": False},
        },
    }
    if kind == "gap":
        snapshot["current_price"] = 55
        snapshot["moving_averages"] = {"ma20": 50, "ma50": 46, "ma200": 40}
        snapshot["entry_inputs"].update({
            "base_duration_sessions": None, "base_range_pct": None,
            "resistance_level": 54, "breakout_proximity_pct": 1.85,
            "gap_up_continuation": {
                "detected": True, "event_date": "2026-09-12", "days_since_gap": 4,
                "gap_pct": 20, "gap_open": 48, "gap_high": 52, "gap_low": 47,
                "gap_close": 51.5, "gap_close_position": .9, "gap_volume_ratio": 2.8,
                "gap_midpoint": 49.5, "post_gap_high": 55.5, "post_gap_low": 48,
                "continuation_pivot": 54, "post_gap_consolidation_range_pct": 8,
                "held_gap_support": True, "follow_through_sessions": 4,
            },
        })
    return snapshot


def company(ticker="TEST", biotech=False):
    return {
        "company": "Test Therapeutics" if biotech else "Test Industrials",
        "ticker": ticker, "sector": "Health Care" if biotech else "Industrials",
        "industry": "Biotechnology" if biotech else "Electrical Equipment",
        "market_cap": 2_000_000_000, "last_price": 102, "daily_volume": 500_000,
        "exchange": "Nasdaq", "swing_pool": "biotech" if biotech else "non_biotech",
    }


def verified_news(ticker="TEST"):
    return {"stories": [{
        "ticker": ticker, "company": "Test Therapeutics", "related_tickers": [],
        "new_information": "The company announced Phase 2 clinical data and a regulatory meeting.",
        "event_type": "Clinical / Regulatory Catalyst", "news_importance_score": 88,
        "source": "Company investor relations", "published_at": "2026-09-12",
        "source_link": "https://example.com/test-catalyst",
    }]}


class SwingTradeEngineTests(unittest.TestCase):
    def test_full_listed_universe_screen_is_independent_of_radar(self):
        rows = [company("BIO", True), company("IND", False),
                {**company("ILLIQ", False), "daily_volume": 10_000}]
        selected, diagnostics = select_swing_market_universe(rows)
        self.assertEqual({row["ticker"] for row in selected}, {"BIO", "IND"})
        self.assertEqual(diagnostics["total_stocks_scanned"], 3)
        self.assertEqual(diagnostics["initial_screen_pass"], 2)
        self.assertIn("No Radar", diagnostics["technical_history_funnel"])

    def test_strategy_a_requires_complete_right_side_breakout(self):
        result = assess_long_base_breakout(market_snapshot(), biotech=False)
        self.assertTrue(result["candidate_qualified"])
        self.assertTrue(result["actionable"])
        self.assertEqual(result["limit_buy"], 100.2)
        weak = market_snapshot()
        weak["entry_inputs"]["higher_low_confirmed"] = False
        weak_result = assess_long_base_breakout(weak, biotech=False)
        self.assertFalse(weak_result["actionable"])
        self.assertIn("higher low", weak_result["failed_gates"])

    def test_strategy_a_rejects_extended_and_unconfirmed_breakout(self):
        extended = market_snapshot()
        extended["current_price"] = 121
        extended["entry_inputs"]["breakout_proximity_pct"] = 21
        self.assertFalse(assess_long_base_breakout(extended)["actionable"])
        unconfirmed = market_snapshot()
        unconfirmed["entry_inputs"]["breakout_volume_ratio"] = 1.0
        self.assertFalse(assess_long_base_breakout(unconfirmed)["actionable"])

    def test_strategy_b_requires_new_continuation_not_gap_day_chase(self):
        result = assess_gap_continuation(market_snapshot("gap"))
        self.assertTrue(result["candidate_qualified"])
        self.assertTrue(result["actionable"])
        first_day = market_snapshot("gap")
        first_day["entry_inputs"]["gap_up_continuation"]["days_since_gap"] = 0
        self.assertFalse(assess_gap_continuation(first_day)["actionable"])
        self.assertIn("at least two follow-through sessions",
                      assess_gap_continuation(first_day)["failed_gates"])

    def test_strategy_a_never_requires_catalyst_even_for_biotech(self):
        candidate = company(biotech=True)
        market = {"securities": {"TEST": market_snapshot()}}
        without = build_swing_trade_engine([candidate], market)
        row = without["pools"]["biotech"]["strategy_a"]["candidates"][0]
        self.assertEqual(row["action"], "BUY NOW")
        self.assertFalse(row["catalyst_validation"]["valid"])

    def test_strategy_b_ranks_unverified_gap_but_requires_catalyst_for_buy(self):
        candidate = company(biotech=True)
        market = {"securities": {"TEST": market_snapshot("gap")}}
        without = build_swing_trade_engine([candidate], market)
        row = without["pools"]["biotech"]["strategy_b"]["candidates"][0]
        self.assertEqual(row["action"], "WAIT")
        self.assertIn("company-specific catalyst not verified", row["why_not_now"])
        with_news = build_swing_trade_engine([candidate], market,
                                             biotech_news_section=verified_news())
        self.assertEqual(with_news["pools"]["biotech"]["strategy_b"]["buy_now"][0]["ticker"], "TEST")

    def test_non_biotech_catalyst_is_optional(self):
        market = {"securities": {"TEST": market_snapshot()}}
        result = build_swing_trade_engine([company()], market)
        row = result["pools"]["non_biotech"]["strategy_a"]["buy_now"][0]
        self.assertEqual(row["action"], "BUY NOW")
        self.assertIn("not verified", row["forward_catalyst"].lower())

    def test_four_pool_strategy_outputs_and_price_based_execution_levels(self):
        candidates = [company("BIOA", True), company("BIOB", True),
                      company("NONA", False), company("NONB", False)]
        market = {"securities": {
            "BIOA": market_snapshot(), "BIOB": market_snapshot("gap"),
            "NONA": market_snapshot(), "NONB": market_snapshot("gap"),
        }}
        news = {"stories": []}
        for ticker in ("BIOA", "BIOB", "NONA", "NONB"):
            event = verified_news(ticker)["stories"][0]
            event["ticker"] = ticker
            news["stories"].append(event)
        result = build_swing_trade_engine(candidates, market, biotech_news_section=news)
        self.assertEqual(len(result["pools"]["biotech"]["strategy_a"]["buy_now"]), 1)
        self.assertEqual(len(result["pools"]["biotech"]["strategy_b"]["buy_now"]), 1)
        self.assertEqual(len(result["pools"]["non_biotech"]["strategy_a"]["buy_now"]), 1)
        self.assertEqual(len(result["pools"]["non_biotech"]["strategy_b"]["buy_now"]), 1)
        row = result["pools"]["non_biotech"]["strategy_a"]["buy_now"][0]
        self.assertNotIn("shares_for_200", row)
        self.assertEqual(row["stop_price"], 85.17)
        self.assertEqual(row["full_exit_price"], 130.26)
        self.assertEqual(row["exit_policy"], "Sell the entire position at +30%; no runner.")
        self.assertEqual(result["pools"]["non_biotech"]["strategy_a"]["candidate_count"], 1)

    def test_gap_measurement_uses_ohlcv_and_follow_through(self):
        rows = []
        for index in range(30):
            close = 10 + index * .02
            rows.append({"date": f"2026-08-{index + 1:02d}", "open": close,
                         "high": close * 1.01, "low": close * .99,
                         "close": close, "volume": 100_000})
        rows[25].update({"open": 13, "high": 14, "low": 12.8, "close": 13.8, "volume": 300_000})
        for index in range(26, 30):
            rows[index].update({"open": 13.7, "high": 14.1, "low": 13.4,
                                "close": 13.9, "volume": 140_000})
        result = calculate_gap_continuation_inputs(rows)
        self.assertTrue(result["detected"])
        self.assertEqual(result["days_since_gap"], 4)
        self.assertGreaterEqual(result["gap_volume_ratio"], 2.8)

    def test_legacy_transition_still_rejects_one_day_only_confirmation(self):
        previous = {"stage": "Bottoming", "technical": {"returns": {"daily": 0}}}
        current = {"state": "Early Reversal", "price_date": "2026-09-18",
                   "returns": {"daily": 6}, "macd": {}, "relative_strength": {}}
        result = stage_transition(previous, current)
        self.assertFalse(result["fresh_favorable_transition"])
        self.assertTrue(result["large_one_day_gain_only"])

    def test_ui_has_required_four_tables_and_columns(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "assets" / "news-dashboard.js").read_text()
        page = (root / "programs" / "genedrnews.html").read_text()
        for label in ("Biotech Swing", "Non-Biotech Swing", "Strategy A", "Strategy B",
                      "Candidate Rank", "Pattern", "Trend", "Volume", "Entry Status",
                      "BUY NOW / WAIT", "Why Not Now / Next Confirmation"):
            self.assertIn(label, script)
        self.assertIn("Independent full-market short-term execution", page)
        self.assertIn("does not source candidates from Radar or High Conviction", page)

    def test_legacy_pattern_helper_remains_available_for_other_consumers(self):
        legacy = market_snapshot()
        legacy["entry_inputs"].update({
            "drawdown_from_fifty_two_week_high_pct": -30,
            "distance_from_recent_low_pct": 12,
            "range_zone_transitions_63d": 3,
        })
        self.assertIsNotNone(technical_setup(legacy)["state"])


if __name__ == "__main__":
    unittest.main()
