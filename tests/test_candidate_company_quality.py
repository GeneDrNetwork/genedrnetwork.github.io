import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.company_quality import build_company_quality_layer, financial_metrics
from scripts.update_news_dashboard import discover_candidate_pool


RUN_AT = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def table(headers, rows):
    return {"headers": headers, "rows": [{"value1": label, **values} for label, values in rows]}


def statements(symbol="NVDA"):
    headers = {"value1": "Period Ending:", "value2": "12/31/2025", "value3": "12/31/2024"}
    return {"symbol": symbol,
        "incomeStatementTable": table(headers, [
            ("Total Revenue", {"value2": "$120", "value3": "$100"}),
            ("Net Income", {"value2": "$12", "value3": "$8"}),
            ("Operating Income", {"value2": "$24", "value3": "$15"}),
        ]),
        "balanceSheetTable": table(headers, [
            ("Cash and Cash Equivalents", {"value2": "$60", "value3": "$50"}),
            ("Short-Term Investments", {"value2": "$20", "value3": "$10"}),
            ("Short-Term Debt / Current Portion of Long-Term Debt", {"value2": "$5", "value3": "$6"}),
            ("Long-Term Debt", {"value2": "$15", "value3": "$20"}),
            ("Total Current Assets", {"value2": "$100", "value3": "$90"}),
            ("Total Current Liabilities", {"value2": "$50", "value3": "$50"}),
        ]),
        "cashFlowTable": table(headers, [
            ("Net Cash Flow-Operating", {"value2": "$20", "value3": "$15"}),
            ("Capital Expenditures", {"value2": "-$5", "value3": "-$4"}),
        ])}


class CandidateAndCompanyQualityTests(unittest.TestCase):
    def test_discovery_is_focused_and_radar_linked(self):
        data = json.loads((Path(__file__).parents[1] / "data" / "news-dashboard.json").read_text())
        pool = discover_candidate_pool(data["radar"]["ai"], data["radar"]["biotech"])
        self.assertGreaterEqual(pool["coverage"]["total"], 30)
        self.assertLessEqual(pool["coverage"]["total"], 50)
        self.assertEqual(len({(row["domain"], row["ticker"]) for row in pool["candidates"]}),
                         pool["coverage"]["total"])
        self.assertTrue(all(row["discovery_sources"] for row in pool["candidates"]))
        self.assertIn("candidate_is_not_conviction", pool["methodology"])

    def test_reported_metrics_keep_observations_and_do_not_invent_eps(self):
        metrics = financial_metrics(statements(), RUN_AT.date().isoformat())
        self.assertEqual(metrics["revenue_growth"]["value"], 20)
        self.assertEqual(metrics["margin_trend"]["value"], 5)
        self.assertEqual(metrics["free_cash_flow"]["value"], 15)
        self.assertEqual(metrics["net_cash"]["value"], 60)
        self.assertIsNone(metrics["eps_growth"]["value"])
        self.assertEqual(metrics["revenue_growth"]["observations"][0]["raw_value"], "$120")

    def test_quality_score_has_sources_completeness_and_missing_fields(self):
        candidate = {"domain": "ai", "ticker": "NVDA", "company": "NVIDIA",
                     "radar_links": [{"trend": "Compute", "exposure_score": 90,
                                      "evidence_ids": ["event-1"]}]}
        raw = {"NVDA": {"payload": statements(), "url": "https://example.com/nvda",
                        "retrieved_at": RUN_AT.isoformat()}}
        layer = build_company_quality_layer([candidate], RUN_AT, None, supplied_raw=raw)
        quality = layer["records"]["ai:NVDA"]
        self.assertTrue(quality["qualified"])
        self.assertGreaterEqual(quality["data_completeness"], 80)
        self.assertIn("earnings_sensitivity", quality["missing_fields"])
        self.assertEqual(quality["sources"][0]["publication_date"], None)

    def test_source_failure_never_reuses_old_quality_as_eligibility(self):
        candidate = {"domain": "ai", "ticker": "NVDA", "company": "NVIDIA", "radar_links": []}
        old = {"records": {"ai:NVDA": {"as_of": "2026-08-28T00:00:00+00:00",
            "company_quality_score": 90, "metrics": {}, "sources": [], "score_history": []}}}
        layer = build_company_quality_layer([candidate], RUN_AT, None, previous=old,
            supplied_raw={"NVDA": {"error": "source unavailable"}})
        quality = layer["records"]["ai:NVDA"]
        self.assertIsNone(quality["company_quality_score"])
        self.assertFalse(quality["qualified"])
        self.assertIn("last_successful_observation", quality)

    def test_reported_loss_caps_otherwise_strong_quality_score(self):
        payload = statements()
        net_income = next(row for row in payload["incomeStatementTable"]["rows"]
                          if row["value1"] == "Net Income")
        net_income.update({"value2": "-$1", "value3": "-$10"})
        candidate = {"domain": "biotech", "ticker": "STOK", "company": "Stoke Therapeutics",
                     "radar_links": []}
        layer = build_company_quality_layer([candidate], RUN_AT, None, supplied_raw={"STOK": {
            "payload": payload, "url": "https://example.com/stok", "retrieved_at": RUN_AT.isoformat()}})
        quality = layer["records"]["biotech:STOK"]
        self.assertLessEqual(quality["company_quality_score"], 70)
        self.assertTrue(quality["score_cap"]["applied"])


if __name__ == "__main__":
    unittest.main()
