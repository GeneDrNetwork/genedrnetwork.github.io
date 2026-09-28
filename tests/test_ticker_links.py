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
        self.assertIn('ticker.replace(/\\./g, "-")', self.script)

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
            "tickerPriceMarkup(alert.ticker, market)",
            "tickerPriceMarkup(row.ticker, row.snapshot)",
            "companyTickerMarkup(row)",
            "tickerPriceMarkup(row.ticker, market)",
            "tickerPriceMarkup(row.ticker, row.market_data)",
        )
        for call in expected_rendering_calls:
            self.assertIn(call, self.script)

        self.assertGreaterEqual(len(re.findall(r"tickerPriceMarkup\(row\.ticker", self.script)), 8)
        self.assertIn(".ticker-link:hover", self.styles)
        self.assertIn(".ticker-link:focus-visible", self.styles)

    def test_site_wide_identity_helper_includes_price_and_security_type(self):
        helper = self.script.split("function tickerPriceMarkup", 1)[1].split("function marketSnapshotText", 1)[0]
        self.assertIn("tickerLink(normalized)", helper)
        self.assertIn("currentPriceLabel", helper)
        self.assertIn("securityTypeLabel", helper)
        self.assertIn('return "N/A"', self.script)
        self.assertEqual(self.script.count("tickerLink(row.ticker)"), 0)


if __name__ == "__main__":
    unittest.main()
