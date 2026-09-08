import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts.update_news_dashboard import (CRYPTO_RADAR_WEIGHTS, attach_watchlist_entry_readiness,
                                           build_crypto_radar, build_market_data_layer,
                                           crypto_radar_methodology)


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

    def test_frontend_contains_third_radar_without_new_top_level_section(self):
        page = (ROOT / "programs" / "genedrnews.html").read_text()
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn('id="crypto-radar-title"', page)
        self.assertIn('id="crypto-radar-summary-copy"', page)
        self.assertIn('id="crypto-radar-takeaways"', page)
        self.assertIn('id="crypto-radar"', page)
        self.assertIn("function renderCryptoRadar", script)
        self.assertIn("renderCryptoRadar(cryptoRadarRows(data))", script)


if __name__ == "__main__":
    unittest.main()
