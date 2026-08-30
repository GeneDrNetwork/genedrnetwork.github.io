"""Phase 6: reported company fundamentals, separate from discovery and Radar scores.

Nasdaq statement monetary units are retained exactly as delivered (scale not
declared by the API). Ratios use aligned statements only; no USD scale is guessed.
"""

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


BASE_WEIGHTS = {"revenue_growth": 15, "earnings_growth": 15, "margin_trend": 15,
                "free_cash_flow": 15, "balance_sheet": 20}
DOMAIN_WEIGHTS = {
    "ai": {"trend_exposure": 10, "earnings_sensitivity": 10},
    "biotech": {"cash_runway": 10, "lead_asset_dependence": 5, "pipeline_diversification": 5},
}


def number(value):
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace("$", "").replace(",", "").replace("%", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        result = float(text)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def iso_date(value):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def statement_fact(payload, table, label, as_of, previous=False):
    data = payload.get(table) or {}
    periods = sorted(((iso_date(value), key) for key, value in data.get("headers", {}).items()
                      if iso_date(value) and iso_date(value) <= as_of), reverse=True)
    index = 1 if previous else 0
    if len(periods) <= index:
        return None
    period, column = periods[index]
    row = next((row for row in data.get("rows", [])
                if str(row.get("value1", "")).strip().lower() == label.lower()), {})
    value = number(row.get(column))
    if value is None:
        return None
    return {"value": value, "period_end": period, "table": table,
            "line_item": label, "raw_value": row[column]}


def aligned(*facts):
    return all(facts) and len({fact["period_end"] for fact in facts}) == 1


def financial_metrics(payload, as_of):
    """Return values AND exact provider observations underlying each calculation."""
    metrics = {}
    def fact(table, label, previous=False):
        return statement_fact(payload, table, label, as_of, previous)
    def put(key, value, observations, method):
        metrics[key] = {"metric_key": key, "value": round(value, 4) if value is not None else None,
                        "observations": [item for item in observations if item], "method": method}
    income, balance, cash = "incomeStatementTable", "balanceSheetTable", "cashFlowTable"
    revenue = fact(income, "Total Revenue")
    for key, label in (("revenue_growth", "Total Revenue"), ("earnings_growth", "Net Income"),
                       ("eps_growth", "Diluted EPS")):
        current, prior = fact(income, label), fact(income, label, True)
        valid = current and prior and prior["value"] > 0
        if valid:
            days = (datetime.fromisoformat(current["period_end"]) - datetime.fromisoformat(prior["period_end"])).days
            valid = 330 <= days <= 400
        value = (current["value"] / prior["value"] - 1) * 100 if valid else None
        put(key, value, [current, prior], "Annual year-over-year %; a missing/nonpositive base or nonannual interval is not scored.")
    current_income = fact(income, "Net Income")
    put("net_income", current_income["value"] if current_income else None, [current_income],
        "Latest annual reported net income in provider units; used only for a loss-making quality cap.")
    op, old_op = fact(income, "Operating Income"), fact(income, "Operating Income", True)
    old_revenue = fact(income, "Total Revenue", True)
    margin = op["value"] / revenue["value"] * 100 if aligned(op, revenue) and revenue["value"] > 0 else None
    old_margin = old_op["value"] / old_revenue["value"] * 100 if aligned(old_op, old_revenue) and old_revenue["value"] > 0 else None
    annual = revenue and old_revenue and 330 <= (datetime.fromisoformat(revenue["period_end"]) - datetime.fromisoformat(old_revenue["period_end"])).days <= 400
    put("margin_trend", margin - old_margin if annual and margin is not None and old_margin is not None else None,
        [op, revenue, old_op, old_revenue], "Annual change in operating margin, percentage points.")
    operating, capex = fact(cash, "Net Cash Flow-Operating"), fact(cash, "Capital Expenditures")
    fcf = operating["value"] - abs(capex["value"]) if aligned(operating, capex) else None
    put("free_cash_flow", fcf, [operating, capex], "Annual operating cash flow minus absolute capital expenditures; provider monetary scale unspecified.")
    put("fcf_margin", fcf / revenue["value"] * 100 if fcf is not None and aligned(operating, revenue) and revenue["value"] > 0 else None,
        [operating, capex, revenue], "Annual free cash flow / same-period revenue, %.")
    cash_fact, investments = fact(balance, "Cash and Cash Equivalents"), fact(balance, "Short-Term Investments")
    short_debt = fact(balance, "Short-Term Debt / Current Portion of Long-Term Debt")
    long_debt = fact(balance, "Long-Term Debt")
    liquidity = cash_fact["value"] + investments["value"] if aligned(cash_fact, investments) else None
    debt = short_debt["value"] + long_debt["value"] if aligned(short_debt, long_debt) else None
    put("cash_and_investments", liquidity, [cash_fact, investments], "Cash plus short-term investments; missing investments are not zero.")
    put("total_debt", debt, [short_debt, long_debt], "Short-term plus long-term debt; missing debt is not zero.")
    put("net_cash", liquidity - debt if liquidity is not None and debt is not None and aligned(cash_fact, short_debt) else None,
        [cash_fact, investments, short_debt, long_debt], "Cash plus short-term investments minus total debt, same balance-sheet date.")
    assets, liabilities = fact(balance, "Total Current Assets"), fact(balance, "Total Current Liabilities")
    put("current_ratio", assets["value"] / liabilities["value"] if aligned(assets, liabilities) and liabilities["value"] > 0 else None,
        [assets, liabilities], "Current assets / current liabilities.")
    put("cash_runway", 12 * liquidity / -operating["value"] if liquidity is not None and aligned(cash_fact, operating) and operating["value"] < 0 else None,
        [cash_fact, investments, operating], "Months of cash at the statement date using annual operating burn; proxy, not management guidance or today's runway. Positive operating cash flow is not infinite runway.")
    return metrics


def threshold_score(value, steps):
    if value is None:
        return None
    return next(score for minimum, score in steps if value >= minimum)


def score_company_quality(candidate, raw, run_at):
    payload = raw.get("payload") or {}
    as_of = run_at.date().isoformat()
    ticker, domain = candidate["ticker"], candidate["domain"]
    source = {"name": "Nasdaq annual reported financial statements", "url": raw.get("url"),
              "retrieved_at": raw.get("retrieved_at"), "publication_date": None,
              "note": "Fiscal period dates are not publication dates. API does not declare monetary scale."}
    metrics = financial_metrics(payload, as_of)
    periods = [obs["period_end"] for metric in metrics.values() for obs in metric["observations"]]
    latest = max(periods) if periods else None
    age = (run_at.date() - datetime.fromisoformat(latest).date()).days if latest else None
    status = "current" if age is not None and age <= 550 and not raw.get("error") else "stale" if latest else "missing"
    components = []
    weights = {**BASE_WEIGHTS, **DOMAIN_WEIGHTS[domain]}
    def component(key, score, evidence, rationale, coverage=1):
        # Old annual statements remain evidence but may not qualify a stock.
        observations = [obs for item in evidence for obs in item.get("observations", [])]
        latest_observation = max((obs["period_end"] for obs in observations), default=None)
        if latest_observation and (run_at.date() - datetime.fromisoformat(latest_observation).date()).days > 550:
            score = None
        if status != "current":
            score = None
        evidence_refs = [item["metric_key"] for item in evidence if item.get("metric_key")]
        if any(item.get("radar_links") for item in evidence):
            evidence_refs.append("candidate_discovery.radar_links")
        components.append({"key": key, "weight": weights[key], "score": score,
                           "available_weight": round(weights[key] * coverage, 2) if score is not None else 0,
                           "evidence_refs": evidence_refs, "rationale": rationale})
    growth_steps = [(30, 100), (15, 85), (5, 70), (0, 55), (-10, 30), (-math.inf, 10)]
    for key in ("revenue_growth", "earnings_growth"):
        component(key, threshold_score(metrics[key]["value"], growth_steps), [metrics[key]], metrics[key]["method"])
    component("margin_trend", threshold_score(metrics["margin_trend"]["value"], [(3, 100), (1, 80), (0, 65), (-2, 40), (-math.inf, 15)]),
              [metrics["margin_trend"]], metrics["margin_trend"]["method"])
    component("free_cash_flow", threshold_score(metrics["fcf_margin"]["value"], [(20, 100), (10, 85), (0, 65), (-10, 35), (-math.inf, 10)]),
              [metrics["free_cash_flow"], metrics["fcf_margin"]], "Quality uses annual FCF margin; absolute FCF is also retained in provider units.")
    ratio_score = threshold_score(metrics["current_ratio"]["value"], [(2, 100), (1.5, 80), (1, 60), (0.5, 30), (-math.inf, 10)])
    net_cash = metrics["net_cash"]["value"]
    net_score = (90 if net_cash >= 0 else 35) if net_cash is not None else None
    scores = [value for value in (ratio_score, net_score) if value is not None]
    component("balance_sheet", round(sum(scores) / len(scores)) if scores else None,
              [metrics["current_ratio"], metrics["net_cash"]], "Equal liquidity/current-ratio and net-cash subweights; unreported debt is not zero.", len(scores) / 2)
    if domain == "ai":
        links = [link for link in candidate.get("radar_links", []) if link.get("evidence_ids")]
        exposure = max((link.get("exposure_score") for link in links if link.get("exposure_score") is not None), default=None)
        component("trend_exposure", exposure, [{"radar_links": links}], "Qualitative exposure reuses evidence-linked Radar exposure; not a claimed revenue percentage.")
        component("earnings_sensitivity", None, [], "Missing: no verified AI segment earnings sensitivity; never inferred from company name or a trend label.")
    else:
        component("cash_runway", threshold_score(metrics["cash_runway"]["value"], [(36, 100), (24, 85), (18, 65), (12, 40), (6, 20), (-math.inf, 5)]),
                  [metrics["cash_runway"]], metrics["cash_runway"]["method"])
        component("lead_asset_dependence", None, [], "Missing: connected Radar programs are not a verified full-company asset-dependence assessment.")
        component("pipeline_diversification", None, [], "Missing: the Radar's partial program list must not be treated as a complete pipeline inventory.")
    available = sum(item["available_weight"] for item in components)
    score = round(sum(item["score"] * item["available_weight"] for item in components if item["score"] is not None) / available) if available else None
    score_cap = None
    if score is not None and metrics["net_income"]["value"] is not None and metrics["net_income"]["value"] < 0:
        score_cap = {"maximum": 70, "applied": score > 70,
                     "rationale": "Latest reported annual net income is negative; volatile revenue, margin or cash-flow improvement cannot by itself produce an elite Company Quality score."}
        score = min(score, score_cap["maximum"])
    financial_count = sum(item["score"] is not None for item in components if item["key"] in BASE_WEIGHTS)
    confidence = "High" if available >= 85 and age is not None and age <= 270 else "Medium" if available >= 50 and financial_count >= 3 else "Low"
    if status != "current":
        confidence = "Low"
    qualified = score is not None and score >= 60 and available >= 50 and financial_count >= 3 and status == "current"
    return {"ticker": ticker, "domain": domain, "company_quality_score": score,
            "data_completeness": available, "confidence": confidence, "data_status": status,
            "qualified": qualified, "as_of": run_at.isoformat(timespec="seconds"), "latest_period_end": latest,
            "statement_age_days": age, "metrics": metrics, "components": components,
            "score_cap": score_cap,
            "sources": [source] if payload else [], "source_errors": [raw["error"]] if raw.get("error") else [],
            "missing_fields": [item["key"] for item in components if item["score"] is None],
            "qualification_rule": "Score >=60, completeness >=50%, at least three financial factors, and nonstale statements. This never substitutes for any High-Conviction gate."}


def build_company_quality_layer(candidates, run_at, fetcher, previous=None, supplied_raw=None):
    raw_by_ticker = {} if supplied_raw is None else supplied_raw
    if supplied_raw is None:
        def collect(ticker):
            url = f"https://api.nasdaq.com/api/company/{ticker}/financials?frequency=1"
            record = {"url": url, "retrieved_at": run_at.isoformat(timespec="seconds")}
            try:
                if ":" in ticker:
                    raise ValueError("Exchange-qualified ticker unsupported by this financial source")
                payload = fetcher(url)
                if not payload or str(payload.get("symbol", "")).upper() != ticker.upper():
                    raise ValueError("Missing statements or returned symbol does not match candidate")
                record["payload"] = payload
            except Exception as exc:
                record["error"] = str(exc)
            return record
        with ThreadPoolExecutor(max_workers=4) as executor:
            jobs = {executor.submit(collect, ticker): ticker for ticker in sorted({item["ticker"] for item in candidates})}
            for job in as_completed(jobs):
                raw_by_ticker[jobs[job]] = job.result()
    records = {}
    for candidate in candidates:
        key = f"{candidate['domain']}:{candidate['ticker']}"
        record = score_company_quality(candidate, raw_by_ticker.get(candidate["ticker"], {}), run_at)
        old = (previous or {}).get("records", {}).get(key)
        if old and record["data_status"] != "current":
            # Preserve evidence, not eligibility, through a failed source refresh.
            record["last_successful_observation"] = old.get("last_successful_observation") or {
                field: old.get(field) for field in ("as_of", "latest_period_end", "company_quality_score", "metrics", "sources")}
        history = list((old or {}).get("score_history", []))
        history = [item for item in history if str(item.get("as_of", ""))[:10] != run_at.date().isoformat()]
        record["score_history"] = (history + [{field: record[field] for field in
            ("as_of", "company_quality_score", "data_completeness", "confidence", "data_status")}])[-60:]
        records[key] = record
    return {"schema_version": "company-quality-v1", "updated_at": run_at.isoformat(timespec="seconds"),
            "methodology": {"base_weights": BASE_WEIGHTS, "domain_weights": DOMAIN_WEIGHTS,
                            "missing_policy": "Available weights renormalize; absent, stale or incomparable inputs are not zero.",
                            "source": "Nasdaq annual reported financial statements; fiscal dates are not publication dates.",
                            "growth_score_bands": growth_steps_for_metadata(),
                            "limitations": ["Monetary scale not declared: raw provider values retained; no absolute USD amounts inferred.",
                                            "Annual financial ratios, not quarterly estimates or forecasts.",
                                            "Cash runway is a historical burn proxy, not management guidance.",
                                            "No verified segment earnings sensitivity, lead-asset dependence, or complete pipeline census is assumed."]},
            "records": records, "coverage": {"requested": len(records),
                "scored": sum(item["company_quality_score"] is not None for item in records.values()),
                "qualified": sum(item["qualified"] for item in records.values()),
                "current": sum(item["data_status"] == "current" for item in records.values()),
                "missing_or_stale": sum(item["data_status"] != "current" for item in records.values()),
                "metric_coverage": {key: sum(item["metrics"].get(key, {}).get("value") is not None for item in records.values())
                                    for key in ("revenue_growth", "earnings_growth", "eps_growth", "margin_trend", "free_cash_flow", "net_cash", "cash_runway")}}}


def growth_steps_for_metadata():
    return {">=30%": 100, ">=15%": 85, ">=5%": 70, ">=0%": 55, ">=-10%": 30, "<-10%": 10}
