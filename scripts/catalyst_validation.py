"""Company-specific versus industry/theme catalyst validation."""

from __future__ import annotations

import re


THEME_ONLY_STATUS = "THEME ONLY / UNVERIFIED"
VALID_COMPANY_STATUS = "COMPANY-SPECIFIC CATALYST"
WAIT_FOR_CATALYST_ACTION = "WATCH / WAIT FOR VALID CATALYST"


def _normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def event_tickers(event):
    """Return only tickers explicitly attached to the source event."""
    values = {event.get("ticker"), *(event.get("related_tickers") or [])}
    values.update(identity.get("ticker") for identity in (event.get("company_identities") or [])
                  if isinstance(identity, dict))
    return {str(value).strip().upper() for value in values
            if value and str(value).strip().upper() not in {"PRIVATE", "N/A", "MISSING"}}


def event_text(event):
    fields = ("headline", "new_information", "description", "company", "project", "product",
              "program", "partnership", "regulatory_event", "financial_event")
    return " ".join(str(event.get(field) or "") for field in fields)


def company_evidence_source_priority(event):
    """Prefer filings and company/official material when direct evidence competes."""
    source_text = " ".join(str(event.get(field) or "") for field in
                           ("source", "source_link", "source_type")).lower()
    source_text += " " + " ".join(
        " ".join(str(item.get(field) or "") for field in ("source", "url", "type"))
        for item in (event.get("evidence_sources") or []) if isinstance(item, dict))
    if any(marker in source_text for marker in
           ("sec.gov", "10-k", "10-q", "8-k", "earnings release", "investor relations", "company filing")):
        return 4
    if any(marker in source_text for marker in
           ("official", "regulator", "press release", "news release", "/investor", "/ir/")):
        return 3
    if event.get("source_link"):
        return 2
    return 1


def company_name_variants(company):
    name = _normalized(company)
    if not name:
        return []
    suffixes = {"inc", "incorporated", "corp", "corporation", "company", "co", "ltd",
                "limited", "plc", "holdings", "holding", "group"}
    parts = name.split()
    simplified = " ".join(part for part in parts if part not in suffixes)
    return [value for value in dict.fromkeys((name, simplified)) if len(value) >= 4]


def company_catalyst_validation(event, ticker, company=None, linked_names=None):
    """Validate that an event is directly connected to the target company.

    Broad theme membership or a beneficiary evidence-id link is deliberately
    insufficient. The event must explicitly carry the ticker/company identity,
    mention the company in its source text, or name a supplied company-linked
    product/project/program.
    """
    ticker = str(ticker or "").strip().upper()
    if not event:
        return {"valid": False, "status": THEME_ONLY_STATUS,
                "reason": "No source event is connected to this company."}
    if ticker and ticker in event_tickers(event):
        return {"valid": True, "status": VALID_COMPANY_STATUS,
                "reason": f"The source event explicitly identifies {ticker}."}

    text = _normalized(event_text(event))
    for name in company_name_variants(company):
        if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
            return {"valid": True, "status": VALID_COMPANY_STATUS,
                    "reason": f"The source event directly names {company}."}
    for linked_name in linked_names or []:
        name = _normalized(linked_name)
        if len(name) >= 4 and re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
            return {"valid": True, "status": VALID_COMPANY_STATUS,
                    "reason": f"The source event names the company-linked product/project {linked_name}."}
    return {"valid": False, "status": THEME_ONLY_STATUS,
            "reason": f"The source supports an industry/theme, but does not directly identify {company or ticker or 'the company'} or a clearly linked company event."}


def catalyst_fields(company_event=None, theme_event=None, validation=None):
    validation = validation or {"valid": False, "status": THEME_ONLY_STATUS,
                                "reason": "No valid company catalyst was found."}
    return {
        "catalyst_validation": validation,
        "company_specific_catalyst": (company_event or {}).get("new_information") or (company_event or {}).get("headline"),
        "industry_theme_catalyst": (theme_event or {}).get("new_information") or (theme_event or {}).get("headline"),
    }
