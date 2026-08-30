import unittest

from scripts.entry_timing import (
    ENTRY_WEIGHTS,
    build_entry_timing_layer,
    calculate_entry_inputs,
    score_entry_timing,
)


def snapshot(**overrides):
    data = {
        "ticker": "TEST", "current_price": 100, "price_date": "2026-08-28",
        "source": "Synthetic daily history", "data_status": "current",
        "moving_averages": {"ma5": 99.8, "ma10": 99.5, "ma20": 99, "ma50": 98, "ma200": 90},
        "returns": {"one_month": 3, "three_month": 8, "six_month": 15},
        "rsi_14": 52,
        "macd": {"value": .4, "signal": .2, "histogram": .2,
                 "previous_histogram": .1, "improving": True, "crossover": None},
        "relative_strength": {"qqq": {"one_month": 2, "three_month": 6},
                              "xbi": {"one_month": 4, "three_month": 8}},
        "entry_inputs": {"history_sessions": 300, "base_duration_sessions": 63,
            "base_range_pct": 10, "tight_range_20d_pct": 5, "ma_compression_pct": 2,
            "volume_contraction_ratio": .8, "up_down_volume_ratio_20d": 1.3,
            "resistance_level": 102, "breakout_proximity_pct": -1.96,
            "breakout_volume_ratio": 1, "invalidation_level": 98},
    }
    data.update(overrides)
    return data


THESIS_PASS = {"passed": True, "rationale": "Fundamental gates passed."}


class EntryTimingEngineTests(unittest.TestCase):
    def test_buy_zone_requires_thesis_and_all_timing_gates(self):
        result = score_entry_timing(snapshot(), "ai", THESIS_PASS)
        self.assertEqual(result["state_key"], "buy-zone")
        self.assertTrue(result["actionable"])
        self.assertGreaterEqual(result["entry_timing_score"], 75)
        self.assertEqual([item["weight"] for item in result["factors"]], list(ENTRY_WEIGHTS.values()))
        self.assertTrue(all(gate["passed"] for gate in result["gates"]))

    def test_technical_setup_cannot_override_failed_thesis(self):
        result = score_entry_timing(snapshot(), "ai", {"passed": False, "rationale": "Evidence Gate failed."})
        self.assertEqual(result["state_key"], "base-building")
        self.assertFalse(result["actionable"])
        self.assertIn("Not actionable", result["entry_guidance"])

    def test_extension_and_breakdown_states_override_score(self):
        extended = snapshot(current_price=130,
            moving_averages={"ma5": 128, "ma10": 125, "ma20": 100, "ma50": 100, "ma200": 85},
            returns={"one_month": 25, "three_month": 50, "six_month": 70},
            entry_inputs={**snapshot()["entry_inputs"], "breakout_proximity_pct": 10})
        self.assertEqual(score_entry_timing(extended, "ai", THESIS_PASS)["state_key"], "extended")
        deteriorating = snapshot(current_price=80,
            moving_averages={"ma5": 82, "ma10": 84, "ma20": 86, "ma50": 90, "ma200": 85},
            macd={"value": -.5, "signal": -.2, "histogram": -.3,
                  "previous_histogram": -.2, "improving": False, "crossover": None})
        self.assertEqual(score_entry_timing(deteriorating, "ai", THESIS_PASS)["state_key"], "deterioration")

    def test_confirmed_breakout_requires_volume(self):
        inputs = {**snapshot()["entry_inputs"], "breakout_proximity_pct": 1,
                  "breakout_volume_ratio": 1.3}
        result = score_entry_timing(snapshot(current_price=103, entry_inputs=inputs), "ai", THESIS_PASS)
        self.assertEqual(result["state_key"], "breakout-confirmed")
        self.assertTrue(result["actionable"])

    def test_missing_inputs_are_not_zero_or_passing_gates(self):
        result = score_entry_timing({}, "ai", THESIS_PASS)
        self.assertIsNone(result["entry_timing_score"])
        self.assertEqual(result["data_completeness"], 0)
        self.assertIsNone(next(gate for gate in result["gates"] if gate["key"] == "extension")["passed"])
        self.assertIsNone(next(gate for gate in result["gates"] if gate["key"] == "breakdown")["passed"])
        self.assertFalse(result["actionable"])

    def test_history_inputs_use_only_calculable_close_volume_levels(self):
        rows = [{"date": f"2026-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}",
                 "close": 100 + (index % 10) * .2, "volume": 1_000_000 - index * 1000}
                for index in range(100)]
        mas = {"ma5": 101, "ma10": 100.8, "ma20": 100.7, "ma50": 100.5}
        inputs = calculate_entry_inputs(rows, mas, {"improving": True, "crossover": None})
        self.assertEqual(inputs["base_duration_sessions"], 63)
        self.assertIsNotNone(inputs["resistance_level"])
        self.assertIsNotNone(inputs["invalidation_level"])
        self.assertEqual(inputs["history_sessions"], 100)

    def test_layer_preserves_candidate_order_and_reuses_watchlist_record(self):
        ai_rows = [{"ticker": "A", "gates": [{"key": key, "label": key, "passed": True}
                    for key in ("evidence", "beneficiary_proof", "expectation", "technical_entry")]},
                   {"ticker": "B", "gates": []}]
        watchlists = {"ai": [{"ticker": "A"}], "biotech": []}
        market = {"securities": {"A": snapshot(), "B": snapshot()}}
        layer = build_entry_timing_layer(ai_rows, [], market, watchlists)
        self.assertEqual([row["ticker"] for row in ai_rows], ["A", "B"])
        self.assertEqual(watchlists["ai"][0]["entry_timing"]["state"], layer["records"]["ai:A"]["state"])
        self.assertNotIn("factors", watchlists["ai"][0]["entry_timing"])


if __name__ == "__main__":
    unittest.main()
