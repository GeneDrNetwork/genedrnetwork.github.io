import unittest
from pathlib import Path

from scripts.entry_timing import calculate_gap_continuation_inputs
from scripts.swing_trade import (
    assess_gap_continuation,
    assess_long_base_breakout,
    assess_rebase_reacceleration,
    assess_stage2_continuation,
    build_swing_trade_engine,
    buy_now_first_display,
    is_biotech_company,
    resolve_strategy_b_catalyst,
    select_swing_market_universe,
    stage_transition,
    technical_setup,
)


def market_snapshot(kind="base"):
    snapshot = {
        "ticker": "TEST", "current_price": 102, "price_date": "2026-09-18",
        "currency": "USD", "source": "Test OHLCV", "data_status": "current",
        "market_cap": 2_000_000_000,
        "moving_averages": {"ma20": 101, "ma50": 96, "ma200": 88},
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
            "higher_low_confirmed": True, "resistance_level": 115,
            "breakout_proximity_pct": -11.3, "breakout_volume_ratio": 1.0,
            "short_term_high_10d": 102,
            "short_term_high_reclaimed": True, "failed_breakout": False,
            "ma20_slope_10d_pct": 2, "ma50_slope_20d_pct": 1,
            "up_down_volume_ratio_20d": 1.4, "recent_low_63d": 90,
            "distance_from_recent_low_pct": 13, "range_zone_transitions_63d": 3,
            "invalidation_level": 95,
            "fifty_two_week_low": 90, "fifty_two_week_high": 160,
            "gap_up_continuation": {"detected": False},
        },
    }
    if kind == "gap":
        snapshot["current_price"] = 55
        snapshot["moving_averages"] = {"ma20": 50, "ma50": 46, "ma200": 40}
        snapshot["entry_inputs"].update({
            "base_duration_sessions": None, "base_range_pct": None,
            "resistance_level": 54, "breakout_proximity_pct": 1.85,
            "fifty_two_week_low": 46, "fifty_two_week_high": 80,
            "gap_up_continuation": {
                "detected": True, "event_date": "2026-09-12", "days_since_gap": 4,
                "gap_pct": 20, "gap_open": 48, "gap_high": 52, "gap_low": 47,
                "gap_close": 51.5, "gap_close_position": .9, "gap_volume_ratio": 2.8,
                "gap_midpoint": 49.5, "post_gap_high": 55.5, "post_gap_low": 48,
                "continuation_pivot": 55, "post_gap_consolidation_range_pct": 8,
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
    def test_biotech_classification_requires_genuine_drug_development_profile(self):
        self.assertTrue(is_biotech_company({"company": "Example Therapeutics",
                                            "sector": "Health Care", "industry": "Biotechnology"}))
        self.assertTrue(is_biotech_company({"company": "Example Pharma",
                                            "sector": "Health Care", "industry": "Drug Manufacturers"}))
        self.assertTrue(is_biotech_company({
            "company": "Example Discovery Corp.", "sector": "Health Care",
            "industry": "Biotechnology: Commercial Physical & Biological Resarch",
            "description": ("A clinical-stage biopharmaceutical company focused on discovery and "
                            "development of proprietary therapeutics for patients with cancer."),
        }))
        self.assertTrue(is_biotech_company({
            "company": "Example Retina Sciences", "sector": "Health Care",
            "industry": "Biotechnology: Biological Products (No Diagnostic Substances)",
        }))
        self.assertTrue(is_biotech_company({
            "company": "Example Medicines", "sector": "Health Care",
            "industry": "Biotechnology: Commercial Physical & Biological Resarch",
            "description": "An established portfolio of medicines and next-generation medicines for patients in oncology.",
        }))
        false_positives = [
            {"company": "Herbalife Ltd.", "sector": "Health Care",
             "industry": "Other Pharmaceuticals"},
            {"company": "Phibro Animal Health", "sector": "Health Care",
             "industry": "Drug Manufacturers - Specialty & Generic"},
            {"company": "Example Diagnostics", "sector": "Health Care",
             "industry": "Diagnostics & Research"},
            {"company": "Example Instruments", "sector": "Health Care",
             "industry": "Medical Instruments & Supplies"},
            {"company": "Example Research plc", "sector": "Health Care",
             "industry": "Biotechnology: Commercial Physical & Biological Resarch",
             "description": "A contract research organization providing clinical trial services to sponsors."},
        ]
        self.assertTrue(all(not is_biotech_company(row) for row in false_positives))

    def test_full_listed_universe_screen_is_independent_of_radar(self):
        rows = [company("BIO", True), company("IND", False),
                {**company("ILLIQ", False), "daily_volume": 10_000}]
        selected, diagnostics = select_swing_market_universe(rows)
        self.assertEqual({row["ticker"] for row in selected}, {"BIO", "IND"})
        self.assertEqual(diagnostics["total_stocks_scanned"], 3)
        self.assertEqual(diagnostics["initial_screen_pass"], 2)
        self.assertIn("No Radar", diagnostics["technical_history_funnel"])

    def test_strategy_a_tracks_stage1_base_but_does_not_enter_before_launch(self):
        result = assess_long_base_breakout(market_snapshot(), biotech=False)
        self.assertTrue(result["candidate_qualified"])
        self.assertFalse(result["actionable"])
        self.assertEqual(result["stage"], "Early Right-Side")
        self.assertIsNone(result["limit_buy"])
        weak = market_snapshot()
        weak["entry_inputs"]["higher_low_confirmed"] = False
        weak_result = assess_long_base_breakout(weak, biotech=False)
        self.assertFalse(weak_result["actionable"])
        self.assertIn("higher low", weak_result["failed_gates"])

    def test_strategy_a_rejects_extended_and_requires_breakout_volume(self):
        extended = market_snapshot()
        extended["current_price"] = 121
        extended["entry_inputs"]["breakout_proximity_pct"] = 21
        self.assertFalse(assess_long_base_breakout(extended)["actionable"])
        unconfirmed = market_snapshot()
        unconfirmed["entry_inputs"]["breakout_volume_ratio"] = .7
        self.assertFalse(assess_long_base_breakout(unconfirmed)["actionable"])

    def test_strategy_a_stage_progression_and_early_stage_rank_priority(self):
        early = assess_long_base_breakout(market_snapshot())
        bottom = market_snapshot()
        bottom["entry_inputs"]["higher_low_confirmed"] = False
        bottom["entry_inputs"]["short_term_high_reclaimed"] = False
        bottom["macd"] = {"histogram": -.1, "improving": False, "crossover": None}
        bottom_result = assess_long_base_breakout(bottom)
        ready = market_snapshot()
        ready["entry_inputs"]["breakout_proximity_pct"] = -2
        ready_result = assess_long_base_breakout(ready)
        breakout = market_snapshot()
        breakout["entry_inputs"]["breakout_proximity_pct"] = 1
        breakout["entry_inputs"]["breakout_volume_ratio"] = 1.5
        breakout_result = assess_long_base_breakout(breakout)
        self.assertEqual(bottom_result["stage"], "Bottoming")
        self.assertEqual(ready_result["stage"], "Breakout Ready")
        self.assertEqual(breakout_result["stage"], "Breakout")
        self.assertGreater(early["score"], bottom_result["score"])
        self.assertGreater(bottom_result["score"], ready_result["score"])
        self.assertGreater(ready_result["score"], breakout_result["score"])

    def test_strategy_a_rejects_one_day_bounce_and_persistent_downtrend(self):
        bounce = market_snapshot()
        bounce["returns"]["daily"] = 10
        bounce["entry_inputs"]["short_term_high_reclaimed"] = False
        bounce["macd"]["crossover"] = None
        self.assertFalse(assess_long_base_breakout(bounce)["actionable"])
        falling = market_snapshot()
        falling["current_price"] = 92
        falling["moving_averages"].update({"ma20": 96, "ma50": 100})
        falling["entry_inputs"].update({"higher_low_confirmed": False,
                                         "short_term_high_reclaimed": False,
                                         "ma20_slope_10d_pct": -2,
                                         "ma50_slope_20d_pct": -2})
        falling["macd"] = {"histogram": -.5, "improving": False, "crossover": None}
        result = assess_long_base_breakout(falling)
        self.assertEqual(result["stage"], "Falling")
        self.assertFalse(result["candidate_qualified"])

    def test_strategy_b_requires_new_continuation_not_gap_day_chase(self):
        result = assess_gap_continuation(market_snapshot("gap"))
        self.assertTrue(result["candidate_qualified"])
        self.assertTrue(result["actionable"])
        first_day = market_snapshot("gap")
        first_day["entry_inputs"]["gap_up_continuation"]["days_since_gap"] = 0
        self.assertFalse(assess_gap_continuation(first_day)["actionable"])
        self.assertIn("at least two follow-through sessions",
                      assess_gap_continuation(first_day)["failed_gates"])

    def test_three_technical_strategies_are_independent_of_catalyst_and_long_base(self):
        stage2 = market_snapshot()
        stage2["entry_inputs"].update({"base_duration_sessions": None,
                                        "base_range_pct": None})
        strategy_b = assess_stage2_continuation(stage2)
        self.assertTrue(strategy_b["candidate_qualified"])
        self.assertTrue(strategy_b["actionable"])
        self.assertEqual(strategy_b["mountain_position"], "Lower")

        rebase = assess_rebase_reacceleration(stage2)
        self.assertTrue(rebase["candidate_qualified"])
        self.assertTrue(rebase["actionable"])
        self.assertEqual(rebase["strategy"], "C")

        no_prior_advance = market_snapshot()
        no_prior_advance["returns"].update({"three_month": -2, "six_month": 3})
        self.assertFalse(assess_rebase_reacceleration(no_prior_advance)["candidate_qualified"])

    def test_biotech_preserves_verified_catalyst_gate_for_strategy_a(self):
        candidate = company(biotech=True)
        snapshot = market_snapshot()
        snapshot["current_price"] = 115.5
        snapshot["moving_averages"].update({"ma20": 112, "ma50": 110})
        snapshot["entry_inputs"].update({
            "resistance_level": 115, "breakout_proximity_pct": .4,
            "breakout_volume_ratio": 1.5, "recent_breakout_attempt": True,
            "breakout_age_sessions": 1,
        })
        market = {"securities": {"TEST": snapshot}}
        without = build_swing_trade_engine([candidate], market)
        row = without["pools"]["biotech"]["strategy_a"]["candidates"][0]
        self.assertEqual(row["action"], "WAIT")
        self.assertFalse(row["catalyst_validation"]["valid"])
        with_news = build_swing_trade_engine([candidate], market,
                                             biotech_news_section=verified_news())
        self.assertEqual(with_news["pools"]["biotech"]["strategy_a"]["buy_now"][0]["ticker"], "TEST")

    def test_biotech_strategy_b_requires_catalyst_for_buy(self):
        candidate = company(biotech=True)
        market = {"securities": {"TEST": market_snapshot()}}
        without = build_swing_trade_engine([candidate], market)
        row = without["pools"]["biotech"]["strategy_b"]["candidates"][0]
        self.assertEqual(row["action"], "WAIT")
        self.assertIn("company-specific catalyst not verified", row["why_not_now"])
        with_news = build_swing_trade_engine([candidate], market,
                                             biotech_news_section=verified_news())
        self.assertEqual(with_news["pools"]["biotech"]["strategy_b"]["buy_now"][0]["ticker"], "TEST")

    def test_audited_strategy_b_company_catalysts_and_absences(self):
        assessment = assess_gap_continuation(market_snapshot("gap"))

        def resolve(ticker, issuer, events, aliases=None):
            candidate = {**company(ticker, ticker in {"DFTX", "ROIV", "VKTX", "MAZE", "HELP"}),
                         "company": issuer}
            return resolve_strategy_b_catalyst(
                candidate, assessment,
                {"attempted": True, "source_available": True, "events": events,
                 "aliases": aliases or []})

        audited = {
            "ATEC": resolve("ATEC", "Alphatec Holdings Inc. Common Stock", [{
                "ticker": "ATEC", "headline": "Alphatec CEO reports open-market purchase",
                "transaction_code": "P", "open_market_purchase": True,
                "purchase_value_usd": 1_013_150, "published_at": "2026-09-12",
                "source": "SEC EDGAR", "source_link": "https://sec.example/atec-form4",
            }]),
            "SIG": resolve("SIG", "Signet Jewelers Limited Common Shares", [{
                "ticker": "SIG", "headline": "Signet reports earnings, raises guidance and expands buyback",
                "published_at": "2026-09-12", "source": "Signet investor relations",
                "source_link": "https://ir.example/sig-results",
            }]),
            "DFTX": resolve("DFTX", "Definium Therapeutics Inc. Common Shares", [{
                "headline": "Definium announces positive topline Phase 3 trial results",
                "published_at": "2026-09-12", "source": "Definium investor relations",
                "source_link": "https://ir.example/dftx-results",
            }]),
            "ROIV": resolve("ROIV", "Roivant Sciences Ltd. Common Shares", [{
                "headline": "Roivant announces positive Phase 2 PHocus clinical results",
                "published_at": "2026-09-12", "source": "Roivant investor relations",
                "source_link": "https://ir.example/roiv-results",
            }]),
            "VKTX": resolve("VKTX", "Viking Therapeutics Inc. Common Stock", [{
                "ticker": "VKTX", "headline": "Viking stock surges on weight-loss drug trial",
                "published_at": "2026-09-12", "source": "Viking investor relations",
                "source_link": "https://ir.example/vktx-results",
            }]),
        }
        self.assertTrue(all(result["status"] == "QUALIFYING" for result in audited.values()))
        self.assertEqual(audited["ATEC"]["event_type"], "MATERIAL_INSIDER_PURCHASE")

        maze = resolve("MAZE", "Maze Therapeutics Inc. Common Stock", [{
            "headline": "Maze rises after rival Vertex APOL1 clinical results",
            "peer_readthrough": True, "published_at": "2026-09-12",
            "source": "Reliable biotech news", "source_link": "https://example.com/vertex",
        }])
        self.assertEqual(maze["status"], "NO_COMPANY_CATALYST")
        self.assertIn("Theme Evidence", maze["validation_reason"])
        self.assertEqual(resolve("VFF", "Village Farms International Inc. Common Shares", [{
            "ticker": "VFF", "headline": "Village Farms insider open-market purchase",
            "transaction_code": "P", "open_market_purchase": True,
            "purchase_value_usd": 101_258, "published_at": "2026-09-12",
            "source": "SEC EDGAR", "source_link": "https://sec.example/vff-form4",
        }])["status"], "NO_COMPANY_CATALYST")
        self.assertEqual(resolve("HELP", "Cybin Inc. Common Stock", [], ["Helus Pharma"])["status"],
                         "NO_COMPANY_CATALYST")

    def test_strategy_b_rejects_old_events_and_analyst_actions(self):
        assessment = assess_gap_continuation(market_snapshot("gap"))
        candidate = {**company("MAZE", True), "company": "Maze Therapeutics Inc. Common Stock"}
        result = resolve_strategy_b_catalyst(candidate, assessment, {
            "attempted": True, "source_available": True, "events": [{
                "ticker": "MAZE", "headline": "Maze positive Phase 2 clinical results",
                "published_at": "2026-08-01", "source_link": "https://example.com/old",
            }, {
                "ticker": "MAZE", "headline": "Analyst upgrades Maze and raises price target",
                "published_at": "2026-09-12", "source_link": "https://example.com/analyst",
            }],
        })
        self.assertEqual(result["status"], "OUTSIDE_WINDOW")
        self.assertFalse(result["credible"])
        self.assertIn("Analyst upgrades", result["analyst_evidence"])

    def test_strategy_b_records_source_and_identity_failures(self):
        assessment = assess_gap_continuation(market_snapshot("gap"))
        candidate = {**company("TEST", True), "company": "Test Therapeutics Common Stock"}
        unavailable = resolve_strategy_b_catalyst(candidate, assessment, {
            "attempted": True, "source_available": False, "events": [],
        })
        self.assertEqual(unavailable["status"], "SOURCE_UNAVAILABLE")
        identity_failed = resolve_strategy_b_catalyst(candidate, assessment, {
            "attempted": True, "source_available": True, "events": [{
                "headline": "Unresolved company announces positive Phase 2 results",
                "identity_hint": True, "published_at": "2026-09-12",
                "source_link": "https://example.com/unresolved",
            }],
        })
        self.assertEqual(identity_failed["status"], "IDENTITY_FAILED")

    def test_non_biotech_catalyst_is_optional(self):
        market = {"securities": {"TEST": market_snapshot()}}
        result = build_swing_trade_engine([company()], market)
        row = result["pools"]["non_biotech"]["strategy_b"]["buy_now"][0]
        self.assertEqual(row["action"], "BUY NOW")
        self.assertIn("not verified", row["forward_catalyst"].lower())

    def test_swing_52_week_position_is_context_not_a_buy_gate(self):
        snapshot = market_snapshot()
        snapshot["entry_inputs"].update({"fifty_two_week_low": 50,
                                          "fifty_two_week_high": 105})
        result = build_swing_trade_engine(
            [company("EGBN")], {"securities": {"EGBN": snapshot}})
        row = result["pools"]["non_biotech"]["strategy_b"]["candidates"][0]
        self.assertEqual(row["action"], "BUY NOW")
        self.assertEqual(row["pct_above_52_week_low"], 104.0)
        self.assertEqual(row["pct_below_52_week_high"], 2.86)
        self.assertEqual(row["base_support"], 101)
        self.assertEqual(row["pct_above_base_support"], 0.99)

    def test_swing_material_extension_from_nearest_entry_level_is_do_not_chase(self):
        snapshot = market_snapshot()
        snapshot["moving_averages"].update({"ma20": 94, "ma50": 93})
        snapshot["entry_inputs"]["short_term_high_10d"] = 96
        result = build_swing_trade_engine(
            [company("EXT")], {"securities": {"EXT": snapshot}})
        row = result["pools"]["non_biotech"]["strategy_a"]["candidates"][0]
        self.assertEqual(row["action"], "DO NOT CHASE — Extended: +7.4% above current support")
        self.assertEqual(row["support_pivot_level"], 95)
        self.assertEqual(row["pct_above_support_pivot"], 7.37)

    def test_fresh_volume_confirmed_strategy_a_breakout_can_be_buy_now(self):
        snapshot = market_snapshot()
        snapshot["current_price"] = 101.1
        snapshot["entry_inputs"].update({
            "resistance_level": 101, "breakout_proximity_pct": 1,
            "breakout_volume_ratio": 1.5, "short_term_high_10d": 100,
            "recent_breakout_attempt": True, "breakout_age_sessions": 0,
        })
        result = build_swing_trade_engine(
            [company("BREAK")], {"securities": {"BREAK": snapshot}})
        row = result["pools"]["non_biotech"]["strategy_a"]["candidates"][0]
        self.assertEqual(row["stage"], "Breakout")
        self.assertEqual(row["action"], "BUY NOW")
        self.assertTrue(row["fresh_breakout"])
        self.assertEqual(row["breakout_age_sessions"], 0)
        self.assertEqual(row["strategy_classification"],
                         "Strategy A — Stage 1 → Stage 2 Launch")
        self.assertEqual(row["entry_classification"], "Entry 1 — Initial Breakout")
        self.assertEqual(row["support_pivot_level"], 101)
        self.assertEqual(row["limit_buy"], 101.2)

        stale = market_snapshot()
        stale["current_price"] = 101.1
        stale["entry_inputs"].update({
            "resistance_level": 101, "breakout_proximity_pct": 1,
            "breakout_volume_ratio": 1.5, "short_term_high_10d": 100,
            "recent_breakout_attempt": True, "breakout_age_sessions": 5,
        })
        stale_result = build_swing_trade_engine(
            [company("STALE")], {"securities": {"STALE": stale}})
        stale_row = stale_result["pools"]["non_biotech"]["strategy_a"]["candidates"][0]
        self.assertEqual(stale_row["action"], "WAIT")
        self.assertFalse(stale_row["fresh_breakout"])

    def test_swing_limit_below_current_is_not_buy_now(self):
        snapshot = market_snapshot()
        snapshot["entry_inputs"]["short_term_high_10d"] = 100
        snapshot["moving_averages"]["ma20"] = 98
        result = build_swing_trade_engine(
            [company("LIMIT")], {"securities": {"LIMIT": snapshot}})
        row = result["pools"]["non_biotech"]["strategy_b"]["candidates"][0]
        self.assertEqual(row["action"], "SET LIMIT $100.20 — wait for pullback")
        self.assertEqual(row["limit_buy"], 100.2)
        self.assertFalse(row["actionable"])

    def test_strategy_c_rebase_support_reversal_can_be_buy_now(self):
        snapshot = market_snapshot()
        market = {"securities": {"TEST": snapshot}}
        result = build_swing_trade_engine(
            [company("TEST", True)], market, biotech_news_section=verified_news())
        row = result["pools"]["biotech"]["strategy_c"]["candidates"][0]
        self.assertEqual(row["action"], "BUY NOW")
        self.assertTrue(row["support_reversal"])
        self.assertEqual(row["entry_stage"], "Re-Base Breakout")
        self.assertEqual(row["strategy_classification"],
                         "Strategy C — Re-Base / Re-Acceleration")
        self.assertEqual(row["entry_classification"],
                         "Fresh Re-Base Breakout")
        self.assertEqual(row["base_support"], 101)
        self.assertEqual(row["base_pivot"], 102)

    def test_strategy_a_first_retest_is_classified_separately_from_strategy(self):
        snapshot = market_snapshot()
        snapshot["current_price"] = 114
        snapshot["moving_averages"].update({"ma20": 112, "ma50": 105})
        snapshot["entry_inputs"].update({"recent_breakout_attempt": True,
                                         "breakout_age_sessions": 2,
                                         "resistance_level": 115,
                                         "breakout_proximity_pct": -.9,
                                         "short_term_high_10d": 114})
        result = build_swing_trade_engine(
            [company("RETEST")], {"securities": {"RETEST": snapshot}})
        row = result["pools"]["non_biotech"]["strategy_a"]["candidates"][0]
        self.assertEqual(row["strategy_classification"],
                         "Strategy A — Stage 1 → Stage 2 Launch")
        self.assertEqual(row["entry_classification"],
                         "Entry 2 — First Pullback/Retest")

    def test_six_pool_strategy_outputs_and_price_based_execution_levels(self):
        candidates = [company("BIO", True), company("NON", False)]
        market = {"securities": {"BIO": market_snapshot(), "NON": market_snapshot()}}
        news = {"stories": []}
        for ticker in ("BIO", "NON"):
            event = verified_news(ticker)["stories"][0]
            event["ticker"] = ticker
            news["stories"].append(event)
        result = build_swing_trade_engine(candidates, market, biotech_news_section=news)
        self.assertEqual(len(result["pools"]["biotech"]["strategy_b"]["buy_now"]), 1)
        self.assertEqual(len(result["pools"]["biotech"]["strategy_c"]["buy_now"]), 1)
        self.assertEqual(len(result["pools"]["non_biotech"]["strategy_b"]["buy_now"]), 1)
        self.assertEqual(len(result["pools"]["non_biotech"]["strategy_c"]["buy_now"]), 1)
        row = result["pools"]["non_biotech"]["strategy_b"]["buy_now"][0]
        self.assertNotIn("shares_for_200", row)
        self.assertNotIn("stop_price", row)
        self.assertNotIn("full_exit_price", row)
        self.assertEqual(row["trailing_stop_policy"]["initial_stop"], "No initial fixed stop")
        self.assertIn("20% trailing stop", row["trailing_stop_policy"]["gain_30"])
        self.assertIn("15% trailing stop", row["trailing_stop_policy"]["gain_50"])
        self.assertEqual(result["pools"]["non_biotech"]["strategy_b"]["candidate_count"], 1)
        funnel = result["coverage"]["diagnostic_funnel"]["overall"]
        self.assertEqual(funnel["universe"], 2)
        self.assertEqual(funnel["data_liquidity"], 2)
        self.assertEqual(funnel["buy_now"], 2)
        for pool in ("biotech", "non_biotech"):
            for strategy in ("strategy_a", "strategy_b", "strategy_c"):
                for buy in result["pools"][pool][strategy]["buy_now"]:
                    self.assertTrue(buy["near_support_or_pivot"] or buy["fresh_breakout"])
                    self.assertLessEqual(buy["pct_above_support_pivot"], 5)
                    self.assertGreaterEqual(buy["limit_buy"], buy["current_price"] * .99)
                    self.assertIn(buy["mountain_position"], ("Lower", "Middle", "Upper"))

    def test_buy_now_is_displayed_first_without_changing_candidate_rank(self):
        rows = [{"ticker": f"WAIT{i}", "action": "WAIT", "candidate_rank": i}
                for i in range(1, 12)]
        rows.append({"ticker": "BUY", "action": "BUY NOW", "candidate_rank": 12})
        displayed = buy_now_first_display(rows, 10)
        self.assertEqual(displayed[0]["ticker"], "BUY")
        self.assertEqual(displayed[0]["candidate_rank"], 12)
        self.assertEqual(len(displayed), 10)

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

    def test_ui_has_required_six_tables_and_common_columns(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "assets" / "news-dashboard.js").read_text()
        page = (root / "programs" / "genedrnews.html").read_text()
        for label in ("Biotech Swing", "Non-Biotech Swing", "Strategy A", "Strategy B",
                      "Strategy C", "Stage 1 → Stage 2 Launch", "Stage 2 Trend Continuation",
                      "Re-Base / Re-Acceleration", "Mountain Position", "Support / Pivot",
                      "% Distance", "Volume", "Action"):
            self.assertIn(label, script)
        self.assertIn("Independent full-market short-term execution", page)
        self.assertIn("does not source candidates from Radar or High Conviction", page)
        self.assertIn("diagnostic funnel", script)
        self.assertIn("no initial fixed stop", script)
        self.assertNotIn("row.stop_price", script)
        self.assertIn("% above 52-wk low ·", script)
        self.assertIn("% below 52-wk high", script)
        self.assertIn("Base Support", script)
        self.assertIn("entry_stage", script)
        self.assertIn("Re-Base / Re-Acceleration", script)
        self.assertIn("strategy_classification", script)
        self.assertIn("entry_classification", script)

    def test_swing_renderer_closes_pool_builder_and_renders_zero_buy_groups(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "assets" / "news-dashboard.js").read_text()
        page = (root / "programs" / "genedrnews.html").read_text()
        self.assertIn(
            'return `<section class="swing-pool"',
            script,
        )
        self.assertIn(
            '  };\n  document.getElementById("swing-opportunities").innerHTML = '
            'pool("biotech", "Biotech Swing") + pool("non_biotech", "Non-Biotech Swing");',
            script,
        )
        self.assertIn('group.candidates || []', script)
        self.assertIn('group.buy_now_count ?? 0', script)
        self.assertIn('news-dashboard.js?v=20260926-1', page)

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
