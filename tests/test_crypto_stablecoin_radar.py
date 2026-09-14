import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.update_news_dashboard import (CRYPTO_RADAR_WEIGHTS, attach_watchlist_entry_readiness,
                                           build_crypto_radar, build_market_data_layer,
                                           crypto_action_pool_eligible,
                                           crypto_dynamic_final_score,
                                           crypto_radar_methodology,
                                           crypto_technical_overlay)


ROOT = Path(__file__).resolve().parents[1]
RUN_AT = datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc)


def series(symbol, start, step, sessions=300):
    start_date = date(2025, 9, 1)
    return {"symbol": symbol, "source": "Synthetic test series", "currency": "USD", "rows": [
        {"date": (start_date + timedelta(days=index)).isoformat(),
         "close": start + step * index, "volume": 1_000_000 + index * 1_000}
        for index in range(sessions)
    ]}


def crypto_market_layer():
    symbols = {
        "^GSPC": series("^GSPC", 4000, 2), "^IXIC": series("^IXIC", 14000, 5),
        "^DJI": series("^DJI", 34000, 7), "^RUT": series("^RUT", 1900, .5),
        "QQQ": series("QQQ", 400, .5), "XBI": series("XBI", 90, .05),
        "BTC-USD": series("BTC-USD", 50000, 100), "ETH-USD": series("ETH-USD", 2500, 4),
        "SOL-USD": series("SOL-USD", 100, .2), "LINK-USD": series("LINK-USD", 12, .02),
        "COIN": series("COIN", 150, .2), "CRCL": series("CRCL", 70, .05),
        "HOOD": series("HOOD", 30, .04), "PYPL": series("PYPL", 60, .03),
    }
    caps = {"BTC-USD": 1_500_000_000_000, "ETH-USD": 500_000_000_000,
            "SOL-USD": 100_000_000_000, "LINK-USD": 15_000_000_000,
            "COIN": 80_000_000_000, "CRCL": 25_000_000_000,
            "HOOD": 90_000_000_000, "PYPL": 70_000_000_000}
    layer = build_market_data_layer({}, RUN_AT, series_by_symbol=symbols, market_caps=caps,
                                    expectations_by_ticker={})
    return attach_watchlist_entry_readiness(layer)


class CryptoStablecoinRadarTests(unittest.TestCase):
    def test_crypto_radar_has_distinct_scores_stages_and_penalty(self):
        rows = build_crypto_radar(RUN_AT, crypto_market_layer())
        self.assertGreaterEqual(len(rows), 6)
        self.assertEqual([row["dynamic_final_rank"] for row in rows], list(range(1, len(rows) + 1)))
        self.assertEqual([row["dynamic_final_score"] for row in rows],
                         sorted((row["dynamic_final_score"] for row in rows), reverse=True))
        for row in rows:
            self.assertGreaterEqual(row["crypto_opportunity_score"], 0)
            self.assertLessEqual(row["crypto_opportunity_score"], 100)
            self.assertGreaterEqual(row["multibagger_potential_score"], 0)
            self.assertLessEqual(row["multibagger_potential_score"], 100)
            self.assertIn(row["price_discovery_stage"],
                          ("Early Discovery", "Emerging", "Re-rating Underway", "Already Ran"))
            self.assertIn(row["already_priced_in"], ("NO", "PARTIALLY", "YES"))
            self.assertIn(row["entry_stage"]["stage"],
                          ("Falling", "Bottoming", "Reversal", "Entry Zone", "Breakout", "Extended", "Unavailable"))
            self.assertEqual(row["multibagger_potential_score"],
                             max(0, row["raw_multibagger_potential_score"] - row["priced_in_penalty"]))
            self.assertIn(row["pool"], ("Discovery Pool", "Action Pool"))
            self.assertIsNotNone(row["crypto_technical_overlay"]["score"])

    def test_rank_is_independent_of_action_label(self):
        with patch("scripts.update_news_dashboard.crypto_action_pool_eligible",
                   side_effect=lambda row: row["ticker"] == "PYPL"):
            rows = build_crypto_radar(RUN_AT, crypto_market_layer())
        pypl = next(row for row in rows if row["ticker"] == "PYPL")
        self.assertEqual(pypl["pool"], "Action Pool")
        self.assertGreater(pypl["dynamic_final_rank"], 1)

    def test_action_requires_complete_technical_and_liquidity_gate(self):
        row = {
            "crypto_opportunity_score": 75, "multibagger_potential_score": 65,
            "already_priced_in": "NO", "data_completeness": 80,
            "score_components": [{"key": "liquidity", "score_100": 90}],
            "crypto_technical_overlay": {
                "actionable": True, "falling": False, "failed_reversal": False,
                "extended": False, "invalidation_level": 90,
                "momentum_score": 75, "relative_strength_score": 65,
                "volume_score": 70},
        }
        self.assertTrue(crypto_action_pool_eligible(row))
        row["crypto_technical_overlay"]["volume_score"] = 30
        self.assertFalse(crypto_action_pool_eligible(row))

    def test_technical_overlay_uses_trend_momentum_rs_volume_and_entry(self):
        layer = crypto_market_layer()
        overlay = crypto_technical_overlay(layer["securities"]["ETH-USD"], "ETH-USD")
        for key in ("trend_score", "momentum_score", "relative_strength_score",
                    "volume_score", "entry_score"):
            self.assertIsNotNone(overlay[key])

    def test_dynamic_score_does_not_add_equity_expectation_twice(self):
        setup = {"score": 75, "actionable": False, "stage": "Bottoming"}
        base = {"raw_radar_rank_score": 80, "priced_in_penalty": 5,
                "crypto_technical_overlay": setup}
        with_expectation = {**base, "expectation": {"score": 5, "maximum": 5}}
        self.assertEqual(crypto_dynamic_final_score(base),
                         crypto_dynamic_final_score(with_expectation))

    def test_native_crypto_has_no_equity_valuation_while_equities_may_use_it(self):
        layer = crypto_market_layer()
        layer["securities"]["COIN"]["expectation_data"] = {
            "data_status": "current", "available_input_groups": ["valuation", "price_run_up"],
            "valuation": {"target_upside_pct": 25, "forward_pe": 20},
            "price_run_up": {"three_month_pct": 0}, "analyst_consensus": {},
            "short_interest": {}, "sources": []}
        rows = build_crypto_radar(RUN_AT, layer)
        btc = next(row for row in rows if row["ticker"] == "BTC-USD")
        coin = next(row for row in rows if row["ticker"] == "COIN")
        self.assertIsNone(btc["expectation"]["score"])
        self.assertEqual(btc["expectation"]["state"], "Data Insufficient")
        self.assertIsNotNone(coin["expectation"]["score"])

    def test_missing_crypto_factor_is_excluded_not_zero(self):
        row = next(item for item in build_crypto_radar(RUN_AT, crypto_market_layer())
                   if item["ticker"] == "BTC-USD")
        network = next(item for item in row["score_components"]
                       if item["key"] == "network_activity_revenue_fees")
        self.assertIsNone(network["score"])
        self.assertTrue(network["missing"])
        self.assertIn("Network Activity Revenue Fees", row["missing_data"])

    def test_crypto_market_data_uses_btc_benchmark(self):
        layer = crypto_market_layer()
        self.assertIn("btc", layer["benchmarks"])
        self.assertIn("crypto", layer["securities"]["ETH-USD"]["domains"])
        self.assertIn("crypto", layer["securities"]["ETH-USD"]["watchlist_entry_readiness"])

    def test_methodology_weights_total_one_hundred(self):
        self.assertEqual(sum(CRYPTO_RADAR_WEIGHTS.values()), 100)
        self.assertIn("0–25", crypto_radar_methodology()["priced_in_penalty"])
        self.assertIn("Native crypto never uses equity P/E", crypto_radar_methodology()["asset_type_boundary"])

    def test_frontend_contains_third_radar_without_new_top_level_section(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn('id="crypto-radar-title"', page)
        self.assertIn('id="crypto-radar-summary-copy"', page)
        self.assertIn('id="crypto-radar-takeaways"', page)
        self.assertIn('id="crypto-radar"', page)
        crypto_start = page.index('id="crypto-radar-title"')
        crypto_section = page[crypto_start:page.index('</section>', crypto_start)]
        self.assertIn("Michael Covel", crypto_section)
        self.assertIn("Native crypto never uses equity P/E", crypto_section)
        self.assertIn("function renderCryptoRadar", script)
        self.assertIn("renderCryptoRadar(cryptoRadarRows(data))", script)


if __name__ == "__main__":
    unittest.main()
