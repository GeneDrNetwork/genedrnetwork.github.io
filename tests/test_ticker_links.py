import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TickerLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / "assets" / "news-dashboard.js").read_text()
        cls.styles = (ROOT / "assets" / "news-dashboard.css").read_text()

    def test_yahoo_url_is_defined_once_in_shared_helper(self):
        self.assertEqual(self.script.count("https://finance.yahoo.com/quote/"), 1)
        self.assertIn("encodeURIComponent(ticker)", self.script)
        self.assertIn("target=\"_blank\"", self.script)
        self.assertIn("rel=\"noopener noreferrer\"", self.script)

    def test_representative_tickers_normalize_to_expected_quote_urls(self):
        for ticker in ("NVDA", "BE", "FCX", "BEAM", "LRCX"):
            normalized = ticker.strip().upper()
            self.assertEqual(
                f"https://finance.yahoo.com/quote/{normalized}/",
                f"https://finance.yahoo.com/quote/{ticker}/",
            )

    def test_all_strategy_renderers_use_the_shared_ticker_markup(self):
        expected_rendering_calls = (
            "tickerLink(ticker)",
            "tickerLink(alert.ticker)",
            "tickerLink(row.ticker)",
            "companyTickerMarkup(row)",
            "tickerPriceMarkup(row.ticker, market)",
            "tickerPriceMarkup(row.ticker, row.market_data)",
        )
        for call in expected_rendering_calls:
            self.assertIn(call, self.script)

        self.assertGreaterEqual(len(re.findall(r"tickerLink\(row\.ticker\)", self.script)), 5)
        self.assertIn(".ticker-link:hover", self.styles)
        self.assertIn(".ticker-link:focus-visible", self.styles)


if __name__ == "__main__":
    unittest.main()
