import unittest

from scripts.strategy_technical import (
    dynamic_alignment_score,
    high_conviction_continuation_setup,
    radar_base_breakout_setup,
)
from scripts.swing_trade import swing_dynamic_final_score


def market_snapshot(**overrides):
    row = {
        "current_price": 100,
        "moving_averages": {"ma20": 98, "ma50": 95, "ma200": 80},
        "returns": {"one_month": 5, "three_month": 12, "six_month": 24},
        "rsi_14": 55,
        "macd": {"histogram": .3, "improving": True, "crossover": "bullish"},
        "entry_inputs": {
            "base_duration_sessions": 63, "base_range_pct": 15,
            "breakout_proximity_pct": -2, "breakout_volume_ratio": 1.0,
            "invalidation_level": 94, "recent_low_63d": 82,
        },
    }
    row.update(overrides)
    return row


class StrategyTechnicalSetupTests(unittest.TestCase):
    def test_radar_requires_mature_base_before_confirmed_reversal(self):
        confirmed = radar_base_breakout_setup(market_snapshot())
        self.assertEqual(confirmed["stage"], "Confirmed Reversal")
        self.assertTrue(confirmed["actionable"])

        first_bounce = market_snapshot(entry_inputs={
            "base_duration_sessions": None, "base_range_pct": None,
            "breakout_proximity_pct": -2, "breakout_volume_ratio": 1.5,
            "invalidation_level": 90,
        })
        unconfirmed = radar_base_breakout_setup(first_bounce)
        self.assertEqual(unconfirmed["stage"], "Volatile Bottom / First Bounce")
        self.assertFalse(unconfirmed["actionable"])

    def test_radar_breakout_requires_price_volume_and_mature_base(self):
        breakout = market_snapshot(entry_inputs={
            **market_snapshot()["entry_inputs"],
            "breakout_proximity_pct": 2, "breakout_volume_ratio": 1.4,
        })
        result = radar_base_breakout_setup(breakout)
        self.assertEqual(result["stage"], "Early Uptrend / Breakout")
        self.assertTrue(result["breakout_confirmed"])

    def test_high_conviction_accepts_middle_of_established_uptrend(self):
        snapshot = market_snapshot(
            current_price=125,
            moving_averages={"ma20": 114, "ma50": 108, "ma200": 82},
            entry_inputs={"recent_low_63d": 100, "invalidation_level": 108},
            macd={"histogram": -.1, "improving": False, "crossover": None},
        )
        result = high_conviction_continuation_setup(snapshot)
        self.assertEqual(result["stage"], "Established Uptrend")
        self.assertTrue(result["actionable"])
        self.assertFalse(result["extended"])

    def test_high_conviction_favors_pullback_support_and_resumption(self):
        result = high_conviction_continuation_setup(market_snapshot(
            current_price=108,
            moving_averages={"ma20": 106, "ma50": 104, "ma200": 80},
            entry_inputs={"recent_low_63d": 96, "invalidation_level": 103},
            macd={"histogram": .2, "improving": True, "crossover": "bullish"},
        ))
        self.assertEqual(result["stage"], "Trend Resumption")
        self.assertTrue(result["support_hold"])
        self.assertEqual(result["entry_quality"], "Best")

    def test_poor_or_extended_setup_lowers_dynamic_rank_score(self):
        good = radar_base_breakout_setup(market_snapshot())
        extended = radar_base_breakout_setup(market_snapshot(
            current_price=135,
            moving_averages={"ma20": 100, "ma50": 95, "ma200": 80},
            returns={"one_month": 20, "three_month": 55, "six_month": 80},
        ))
        self.assertGreater(
            dynamic_alignment_score(95, good, 90, 80, 80),
            dynamic_alignment_score(95, extended, 30, 80, 40),
        )

    def test_falling_and_unavailable_radar_setups_are_gated_and_penalized(self):
        falling = radar_base_breakout_setup(market_snapshot(
            current_price=70,
            moving_averages={"ma20": 75, "ma50": 80, "ma200": 85},
            returns={"one_month": -12, "three_month": -25, "six_month": -35},
            macd={"histogram": -.5, "improving": False, "crossover": None},
            entry_inputs={"base_duration_sessions": None, "base_range_pct": None},
        ))
        unavailable = radar_base_breakout_setup({})
        confirmed = radar_base_breakout_setup(market_snapshot())
        self.assertEqual(falling["stage"], "Falling")
        self.assertFalse(falling["actionable"])
        self.assertEqual(unavailable["stage"], "Unavailable")
        self.assertFalse(unavailable["actionable"])
        self.assertGreater(confirmed["score"], falling["score"])
        self.assertGreater(
            dynamic_alignment_score(80, confirmed, 85, 70, 80),
            dynamic_alignment_score(95, unavailable, 20, 70, 45),
        )

    def test_failed_reversal_is_not_actionable_and_is_penalized(self):
        failed = radar_base_breakout_setup(market_snapshot(
            current_price=94,
            moving_averages={"ma20": 98, "ma50": 92, "ma200": 80},
            macd={"histogram": -.4, "improving": False, "crossover": None},
        ))
        confirmed = radar_base_breakout_setup(market_snapshot())
        self.assertEqual(failed["stage"], "Failed Reversal")
        self.assertTrue(failed["failed_reversal"])
        self.assertFalse(failed["actionable"])
        self.assertGreater(
            dynamic_alignment_score(80, confirmed, 85, 70, 80),
            dynamic_alignment_score(95, failed, 15, 70, 80),
        )

    def test_swing_dynamic_score_is_technical_first(self):
        strong = {"state": "Early Reversal", "technical_setup_score": 90,
                  "current_price": 100, "support": 90, "resistance": 125, "extended": False}
        weak = {**strong, "technical_setup_score": 45}
        weak_catalyst = {"credible": True, "importance_score": 100}
        no_catalyst = {"credible": False, "importance_score": None}
        self.assertGreater(swing_dynamic_final_score(strong, no_catalyst),
                           swing_dynamic_final_score(weak, weak_catalyst))


if __name__ == "__main__":
    unittest.main()
