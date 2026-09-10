import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.update_news_dashboard import (WEBSITE_SELECTED_LIMIT, attach_watchlist_entry_readiness,
                                           build_manual_watchlist_output, build_market_data_layer,
                                           build_strategy_watchlists, load_manual_watchlist,
                                           shared_market_ticker_domains, watch_rows,
                                           watchlist_selection_metrics)


ROOT = Path(__file__).resolve().parents[1]


class WatchlistWorkflowTests(unittest.TestCase):
    @staticmethod
    def market_data(status="READY TO BUY", score=82):
        decision = {"status": status}
        readiness = {"entry_timing_score": score, "state": "🚀 Breakout Confirmed",
                     "state_key": "breakout-confirmed", "buy_decision": decision}
        snapshot = {"current_price": 25, "moving_averages": {"ma20": 24, "ma50": 23},
                    "watchlist_entry_readiness": {"ai": readiness, "biotech": readiness}}
        return {"securities": {"TEST": snapshot, "BIO": snapshot}}

    def test_legacy_static_rows_are_not_marked_manual(self):
        rows = watch_rows([
            ("Example Co", "TEST", "Technology", "Selected reason", "Catalyst", "Mid Cap", "High", "Medium")
        ])
        self.assertNotIn("watchlist_source", rows[0])

    def test_strategy_watchlist_deduplicates_and_combines_sources(self):
        ai_radar = [{"trend": "Compute", "what_it_means": "Compute demand is expanding.",
                     "beneficiary_records": [{"company": "Example Co", "ticker": "TEST", "thesis_evidence": []}]}]
        biotech_radar = [{"company": "Bio Co", "ticker": "BIO", "program": "Drug A", "catalyst": "Readout",
                          "clinical_evidence": "Phase 2", "why_important": "Potentially material."}]
        monthly = {"ai": [{"company": "Example Co", "ticker": "TEST", "why_selected": "Quality company."}], "biotech": []}
        swing = {"opportunities": [{"company": "Example Co", "ticker": "TEST", "domain": "ai", "classification": "Entry Zone",
                                    "why_this_swing_trade_opportunity": {"why_chart_selected": "Early reversal.", "bottom_reversal_stage": "Entry Zone", "invalidation": "Lose support."},
                                    "catalyst": {"description": "Product event", "timing": "Soon"}}]}
        result = build_strategy_watchlists(ai_radar, biotech_radar, monthly, swing, self.market_data())
        test_rows = [row for row in result["ai"] if row["ticker"] == "TEST"]
        self.assertEqual(len(test_rows), 1)
        self.assertEqual(test_rows[0]["watchlist_sources"], ["Radar", "High Conviction", "Swing Trade"])
        self.assertEqual([row["ticker"] for row in result["biotech"]], ["BIO"])
        self.assertEqual(test_rows[0]["technical_entry_readiness_score"], 82)

    def test_website_selected_excludes_wait_and_extended_without_changing_sources(self):
        radar = [{"trend": "Compute", "beneficiary_records": [{"company": "Example Co", "ticker": "TEST"}]}]
        for status in ("WAIT", "EXTENDED / TOO LATE"):
            result = build_strategy_watchlists(radar, [], {"ai": [], "biotech": []}, {"opportunities": []},
                                               self.market_data(status, 60))
            self.assertEqual(result, {"ai": [], "biotech": []})

    def test_focused_website_selected_is_capped_and_ranked(self):
        rows = [{"company": f"Company {index}", "ticker": f"T{index:02d}", "why_selected": "Quality."}
                for index in range(24)]
        securities = {}
        for index, row in enumerate(rows):
            score = 90 - index
            status = "READY TO BUY" if index < 10 else "WAIT"
            state = "breakout-confirmed" if index < 10 else "base-building"
            securities[row["ticker"]] = {
                "current_price": 100, "moving_averages": {"ma20": 98, "ma50": 96},
                "entry_inputs": {"base_duration_sessions": 63, "base_range_pct": 15,
                                 "ma_compression_pct": 3, "volume_contraction_ratio": .8,
                                 "up_down_volume_ratio_20d": 1.3, "breakout_proximity_pct": -2,
                                 "breakout_volume_ratio": 1.1},
                "macd": {"histogram": .2, "improving": True},
                "watchlist_entry_readiness": {"ai": {"entry_timing_score": score,
                    "state_key": state, "buy_decision": {"status": status}}},
            }
        result = build_strategy_watchlists([], [], {"ai": rows, "biotech": []},
                                           {"opportunities": []}, {"securities": securities})
        selected = result["ai"] + result["biotech"]
        self.assertEqual(len(selected), WEBSITE_SELECTED_LIMIT)
        self.assertEqual([row["ticker"] for row in selected],
                         [f"T{index:02d}" for index in range(8)] + [f"T{index:02d}" for index in range(10, 22)])
        self.assertEqual([row["website_selected_rank"] for row in selected], list(range(1, 21)))

    def test_approaching_entry_requires_multiple_confirmed_signals(self):
        weak = {"current_price": 100, "moving_averages": {"ma20": 99, "ma50": 98},
                "entry_inputs": {"breakout_proximity_pct": -2},
                "macd": {"histogram": -.1, "improving": False}}
        strong = {"current_price": 100, "moving_averages": {"ma20": 99, "ma50": 98},
                  "entry_inputs": {"base_duration_sessions": 63, "base_range_pct": 15,
                                   "ma_compression_pct": 3, "volume_contraction_ratio": .8,
                                   "up_down_volume_ratio_20d": 1.3, "breakout_proximity_pct": -2,
                                   "breakout_volume_ratio": 1.1},
                  "macd": {"histogram": .2, "improving": True}}
        readiness = {"state_key": "near-buy-zone"}
        self.assertFalse(watchlist_selection_metrics(weak, readiness)["approaching_entry_qualified"])
        self.assertTrue(watchlist_selection_metrics(strong, readiness)["approaching_entry_qualified"])

    def test_manual_workflow_persists_pending_tickers_without_fabricating_quotes(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn('validation_status: "pending-market-data"', script)
        self.assertIn("was saved to Manually Entered", script)
        self.assertIn("no quote was fabricated", script)
        self.assertIn('validation_status: "validated-shared-market-data"', script)
        self.assertNotIn("so it was not added. No unverified quote was substituted", script)
        self.assertIn("function removeWatchlistItem(ticker)", script)
        self.assertIn("watchlistState.manual_items = watchlistState.manual_items.filter", script)
        self.assertIn("data-watchlist-remove", script)
        self.assertIn('item.validation_status = "validated-shared-market-data"', script)
        self.assertIn("if (upgradedValidation) writeWatchlistState()", script)
        self.assertIn("Data Unavailable", script)

    def test_manual_cards_expose_shared_score_stage_entry_and_visible_remove(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn('class="watchlist-summary manual-watchlist-summary"', script)
        for label in ("Current Price:", "Entry Readiness", "Entry Stage", "Buy Status", "Action"):
            self.assertIn(label, script)
        self.assertIn('class="watchlist-action watchlist-remove manual-watchlist-remove"', script)
        self.assertIn("event.stopPropagation(); removeWatchlistItem", script)

    def test_watchlist_summary_separates_existing_stage_status_and_action(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        styles = (ROOT / "assets" / "news-dashboard.css").read_text()
        expected_order = ('<small>Entry Readiness</small>', '<small>Entry Stage</small>',
                          '<small>Buy Status</small>', '<small>Action</small>')
        for summary_class in ('watchlist-summary manual-watchlist-summary', 'watchlist-summary'):
            summary = script.split(f'class="{summary_class}"', 1)[1].split('</summary>', 1)[0]
            positions = [summary.index(label) for label in expected_order]
            self.assertEqual(positions, sorted(positions))
        self.assertIn("technical.entry_timing_state", script)
        self.assertIn("extendedStage", script)
        self.assertIn('extendedStage ? "EXTENDED / TOO LATE"', script)
        self.assertIn("repeat(4,minmax(100px,.65fr))", styles)

    def test_manual_storage_is_normalized_and_deduplicated_on_load(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("seenManualTickers", script)
        self.assertIn("deduplicatedManualItems", script)
        self.assertIn("seenManualTickers.has(ticker)", script)

    def test_repository_manual_tickers_enter_shared_market_and_readiness_pipeline(self):
        manual = {"items": [
            {"ticker": "TESTA", "company": "Test A", "domain": "ai", "source": "Manual"},
            {"ticker": "TESTB", "company": "Test B", "domain": "ai", "source": "Manual"},
        ]}
        domains = shared_market_ticker_domains({}, {"candidates": []}, manual)
        self.assertEqual(domains["TESTA"], ["ai"])
        self.assertEqual(domains["TESTB"], ["ai"])

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        def series(symbol, offset):
            rows = [{"date": (start + timedelta(days=index)).date().isoformat(),
                     "close": round(40 + offset + index * .04, 2),
                     "volume": 1500 if index == 259 else 1000}
                    for index in range(260)]
            return {"symbol": symbol, "rows": rows, "source": "Test daily history", "currency": "USD"}

        supplied = {ticker: series(ticker, offset) for ticker, offset in (
            ("TESTA", 0), ("TESTB", 5), ("^GSPC", 10), ("QQQ", 12),
            ("XBI", 8), ("BTC-USD", 15))}
        market = build_market_data_layer(
            {}, datetime(2026, 9, 9, tzinfo=timezone.utc), series_by_symbol=supplied,
            market_caps={}, expectations_by_ticker={}, candidate_pool={"candidates": []},
            manual_watchlist=manual)
        attach_watchlist_entry_readiness(market)
        output = build_manual_watchlist_output(manual, market)
        for ticker in ("TESTA", "TESTB"):
            snapshot = market["securities"][ticker]
            readiness = snapshot["watchlist_entry_readiness"]["ai"]
            self.assertIsNotNone(snapshot["current_price"])
            self.assertIsNotNone(readiness["entry_timing_score"])
            self.assertIsNotNone(readiness["state"])
            self.assertIsNotNone(readiness["buy_decision"]["status"])
            rendered = next(item for item in output["items"] if item["ticker"] == ticker)
            self.assertEqual(rendered["watchlist_sources"], ["Manual"])
            self.assertIsNotNone(rendered["suggested_entry"]["reference"])

    def test_repository_manual_watchlist_is_the_production_source_of_truth(self):
        config = load_manual_watchlist(ROOT / "data" / "manual_watchlist.json")
        self.assertEqual({item["ticker"] for item in config["items"]}, {"BE", "FCX"})
        self.assertTrue(all(item["repository_managed"] for item in config["items"]))
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        self.assertIn("data?.manual_watchlist?.items", script)
        self.assertIn("repository_managed: true", script)
        self.assertIn("!item.repository_managed || productionTickers.has", script)

    def test_updater_declares_persistent_user_selection_policy(self):
        updater = (ROOT / "scripts" / "update_news_dashboard.py").read_text()
        self.assertIn('"watchlist_policy"', updater)
        self.assertIn("Only genuine Manual Add entries persist", updater)
        self.assertIn("Strategy-derived membership is added, combined, screened, ranked, and removed automatically", updater)

    def test_frontend_has_all_four_sources_and_no_duplicate_quote_provider(self):
        script = (ROOT / "assets" / "news-dashboard.js").read_text()
        for source in ("Radar", "High Conviction", "Swing Trade", "Manual"):
            self.assertIn(source, script)
        self.assertIn("WATCHLIST_STORAGE_KEY", script)
        self.assertIn("LEGACY_WATCHLIST_STORAGE_KEY", script)
        self.assertIn("automaticWatchlistSelections", script)
        self.assertIn("manual_items", script)
        self.assertIn("sharedMarketSecurities", script)
        self.assertIn("CONSTRUCTIVE_WATCHLIST_STATUSES", script)
        self.assertIn("websiteSelected", script)
        self.assertIn("manuallyEntered", script)
        self.assertIn("technical_entry_readiness_score", script)
        self.assertNotIn("fetch(\"https://query", script)

        page = (ROOT / "programs" / "genedrnews.html").read_text()
        self.assertIn('id="website-selected-watchlist"', page)
        self.assertIn('id="top-entry-watchlist"', page)
        self.assertIn('id="developing-watchlist"', page)
        self.assertIn('id="manually-entered-watchlist"', page)
        self.assertIn('href="#my-stocks">Watchlist</a>', page)
        self.assertIn('<h2>Watchlist</h2>', page)
        self.assertIn("Delete / Remove", script)


if __name__ == "__main__":
    unittest.main()
