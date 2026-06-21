# GeneDr News & Invest Automation

The dashboard reads `data/news-dashboard.json`. GitHub Actions runs
`scripts/update_news_dashboard.py` every day at 11:17 UTC and commits refreshed
public RSS headlines and delayed public market data to `main`.

## Manual refresh

Run `python3 scripts/update_news_dashboard.py`, or start the
**Update GeneDr News Dashboard** workflow from the Actions tab.

## Data and API configuration

- News uses Google News RSS searches that link back to the publishing source.
- Delayed price history uses Stooq public CSV data. Values may be delayed or
  unavailable and must not be treated as trading quotes.
- No paid API key is required.
- To add live quotes or market capitalization later, store the provider key as
  a GitHub Actions repository secret and read it from an environment variable in
  `scripts/update_news_dashboard.py`. Never place keys in the website or JSON.

The summaries are concise, rules-based headline digests. An approved AI API can
be added later through a GitHub secret without changing the public dashboard.
