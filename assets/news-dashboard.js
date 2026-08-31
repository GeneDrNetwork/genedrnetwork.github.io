const scriptSource = document.currentScript && document.currentScript.src ? document.currentScript.src : document.baseURI;
const dataUrl = new URL("../data/news-dashboard.json", scriptSource);
dataUrl.searchParams.set("_", Date.now().toString());
const DATA_URL = dataUrl.href;

const escapeHtml = (value = "") => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#039;");
const setText = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value ?? "No update available."; };
let sharedMarketSecurities = {};
let currentDashboardData = null;
let watchlistState = null;
let currentAutomaticWatchlistTickers = new Set();
const WATCHLIST_STORAGE_KEY = "genedr-investment-watchlist-v2";
const LEGACY_WATCHLIST_STORAGE_KEY = "genedr-investment-watchlist-v1";

function normalizedTicker(value) {
  return String(value || "").trim().toUpperCase();
}

function writeWatchlistState() {
  try { localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(watchlistState)); } catch (_) { /* Browser storage may be disabled. */ }
}

function initializeWatchlistState(data) {
  if (watchlistState) return watchlistState;
  try {
    const saved = JSON.parse(localStorage.getItem(WATCHLIST_STORAGE_KEY) || "null");
    if (saved && saved.version === 2 && Array.isArray(saved.manual_items)) watchlistState = saved;
  } catch (_) { watchlistState = null; }
  if (!watchlistState) {
    let legacyItems = [];
    try {
      const legacy = JSON.parse(localStorage.getItem(LEGACY_WATCHLIST_STORAGE_KEY) || "null");
      if (legacy?.version === 1 && Array.isArray(legacy.items)) legacyItems = legacy.items;
    } catch (_) { legacyItems = []; }
    const timestampCounts = legacyItems.reduce((counts, item) => {
      counts[item.added_at] = (counts[item.added_at] || 0) + 1; return counts;
    }, {});
    const genuineManual = legacyItems.filter((item) => item.source === "Manual" && timestampCounts[item.added_at] === 1)
      .map((item) => ({ ticker: normalizedTicker(item.ticker), company: item.company, domain: item.domain,
        reason: item.reason || "Manually selected for active technical monitoring.", added_at: item.added_at }));
    watchlistState = { version: 2, manual_items: genuineManual };
    writeWatchlistState();
    try { localStorage.removeItem(LEGACY_WATCHLIST_STORAGE_KEY); } catch (_) { /* Browser storage may be disabled. */ }
  }
  return watchlistState;
}

function isOnWatchlist(ticker) {
  const key = normalizedTicker(ticker);
  return currentAutomaticWatchlistTickers.has(key) || Boolean(watchlistState?.manual_items?.some((item) => normalizedTicker(item.ticker) === key));
}

function watchlistAction(ticker, company, source, domain) {
  const key = normalizedTicker(ticker);
  if (!key || ["PRIVATE", "N/A", "MISSING"].includes(key)) return "";
  return `<button type="button" class="watchlist-action" data-watchlist-add data-ticker="${escapeHtml(key)}" data-company="${escapeHtml(company || key)}" data-source="${escapeHtml(source)}" data-domain="${escapeHtml(domain)}" disabled>✓ Auto Watchlist</button>`;
}

const PLACEHOLDER_SCORES = [88, 84, 81, 78, 75, 72, 69, 66, 63, 60];
const stageFor = (score) => score >= 85 ? "Hot" : score >= 76 ? "Heating Up" : score >= 66 ? "Emerging" : "Cooling";
const stageClass = (stage = "") => String(stage).toLowerCase().replace(/\s+/g, "-");
const classKey = (value = "") => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const detailItem = (label, value, placeholder = false) => `<div class="detail-item${placeholder ? " detail-placeholder" : ""}"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`;

function renderReasoning(targetId, rows = []) {
  const target = document.getElementById(targetId);
  if (!target) return;
  target.innerHTML = rows.map((row) => `<article class="reasoning-point"><h4>${escapeHtml(row.label || "Interpretation")}</h4><p>${escapeHtml(row.text || "Evidence is currently insufficient for interpretation.")}</p></article>`).join("")
    || `<p class="loading-state">Reasoning is unavailable because the connected evidence is incomplete.</p>`;
}

function renderNumberedMessages(targetId, rows = []) {
  const target = document.getElementById(targetId);
  if (!target) return;
  target.innerHTML = rows.map((row) => `<li>${escapeHtml(row)}</li>`).join("") || `<li>No evidence-supported conclusion is available.</li>`;
}

function renderDashboardCommentary(commentary = {}) {
  const aiNews = commentary.news?.ai_technology || commentary.news || {};
  const biotechNews = commentary.news?.biotech_healthcare || commentary.news || {};
  renderReasoning("news-reasoning", aiNews.reasoning);
  renderNumberedMessages("news-takeaways", aiNews.take_home_messages);
  renderReasoning("biotech-news-reasoning", biotechNews.reasoning);
  renderNumberedMessages("biotech-news-takeaways", biotechNews.take_home_messages);
  renderReasoning("radar-reasoning", commentary.radar?.reasoning);
  renderNumberedMessages("radar-takeaways", commentary.radar?.take_home_messages);
  renderNumberedMessages("high-conviction-reasons", commentary.high_conviction?.reasons);
}

function aiRadarRows(data) {
  if (Array.isArray(data.radar?.ai)) return data.radar.ai;
  return (data.ai?.demand_drivers || []).map((item, index) => {
    const score = PLACEHOLDER_SCORES[index] || Math.max(50, 88 - index * 3);
    return {
      trend: item.area, heat_score: score, direction: index < 6 ? "Rising" : "Tracking", stage: stageFor(score),
      why_now: item.why, potential_beneficiaries: `${item.public_companies}; ${item.emerging_companies}`,
      key_intelligence: data.summaries?.ai || "Daily AI monitoring is active.", demand_drivers: item.why,
      bottleneck: "Radar Engine analysis pending.", beneficiaries: `${item.public_companies}; ${item.emerging_companies}`,
      market_expectation: "Pricing analysis will be supplied by the future Radar Engine.",
      risks: "Risk and invalidation analysis will be supplied by the future Radar Engine.",
      watch_next: "Daily automated news and market feeds continue to monitor this theme."
    };
  });
}

function biotechRadarRows(data) {
  if (Array.isArray(data.radar?.biotech)) return data.radar.biotech;
  return [];
}

function renderScore(score, label) {
  const missing = score === null || score === undefined || !Number.isFinite(Number(score));
  const safeScore = missing ? 0 : Math.max(0, Math.min(100, Number(score)));
  if (missing) return `<div class="score score-missing" aria-label="${escapeHtml(label)} missing"><strong>Missing</strong><i><b style="width:0%"></b></i></div>`;
  return `<div class="score" aria-label="${escapeHtml(label)} ${safeScore} out of 100"><strong>${safeScore}</strong><span>/100</span><i><b style="width:${safeScore}%"></b></i></div>`;
}

function formatMarketValue(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "Missing";
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString([], { maximumFractionDigits: digits }) : "Missing";
}

function formatMarketCap(value) {
  if (value === null || value === undefined || value === "") return "Missing";
  const number = Number(value);
  if (!Number.isFinite(number)) return "Missing";
  if (number >= 1e12) return `$${(number / 1e12).toFixed(2)}T`;
  if (number >= 1e9) return `$${(number / 1e9).toFixed(2)}B`;
  if (number >= 1e6) return `$${(number / 1e6).toFixed(2)}M`;
  return `$${number.toLocaleString()}`;
}

function currentPriceLabel(ticker, snapshot = null) {
  const normalizedTicker = String(ticker || "").trim();
  if (!normalizedTicker || ["Private", "N/A", "Missing"].includes(normalizedTicker)) return "";
  const hasPrice = (market) => market?.current_price !== null && market?.current_price !== undefined && market?.current_price !== "" && Number.isFinite(Number(market.current_price));
  const market = hasPrice(snapshot) ? snapshot : sharedMarketSecurities[normalizedTicker.toUpperCase()] || snapshot || null;
  if (!hasPrice(market)) return "Price unavailable";
  const price = Number(market.current_price);
  const currency = /^[A-Z]{3}$/.test(String(market?.currency || "")) ? market.currency : "USD";
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price);
  } catch (_) {
    return `$${price.toFixed(2)}`;
  }
}

function tickerPriceLabel(ticker, snapshot = null) {
  const normalizedTicker = String(ticker || "").trim();
  if (!normalizedTicker || normalizedTicker === "Missing") return "Ticker missing";
  const price = currentPriceLabel(normalizedTicker, snapshot);
  return price ? `${normalizedTicker} ${price}` : normalizedTicker;
}

function marketSnapshotText(snapshot, benchmark = "sp500") {
  if (!snapshot) return "Market data missing.";
  const averages = snapshot.moving_averages || {};
  const returns = snapshot.returns || {};
  const macd = snapshot.macd || {};
  const relative = snapshot.relative_strength?.[benchmark] || {};
  return `Price ${currentPriceLabel(snapshot.ticker, snapshot) || "unavailable"} · Market cap ${formatMarketCap(snapshot.market_cap)} · MA20/50/200 ${formatMarketValue(averages.ma20)}/${formatMarketValue(averages.ma50)}/${formatMarketValue(averages.ma200)} · 1M/3M/6M ${formatChange(returns.one_month)}/${formatChange(returns.three_month)}/${formatChange(returns.six_month)} · RSI ${formatMarketValue(snapshot.rsi_14)} · MACD ${formatMarketValue(macd.value, 4)} (${formatMarketValue(macd.histogram, 4)} histogram) · Volume/20D ${formatMarketValue(snapshot.volume_vs_20d_average)}x · 52W position ${formatMarketValue(snapshot.fifty_two_week_position)}% · 3M RS vs ${benchmark.toUpperCase()} ${formatChange(relative.three_month)} · ${snapshot.data_status || "status missing"}.`;
}

function renderMarketSnapshot(snapshot, benchmark) {
  return `<div class="detail-item detail-wide"><dt>Shared Market &amp; Technical Data</dt><dd>${escapeHtml(marketSnapshotText(snapshot, benchmark))}</dd></div>`;
}

function renderAiFactorBreakdown(row) {
  const factors = (row.score_components || []).map((factor) => `<li class="${factor.missing ? "score-component-missing" : ""}">
    <span>${escapeHtml(factor.label)}</span><strong>${factor.score === null || factor.score === undefined ? "Missing" : `${escapeHtml(factor.score)} / ${escapeHtml(factor.weight)}`}</strong>
    <small>${escapeHtml(factor.rationale)}</small></li>`).join("");
  const opportunity = row.opportunity_score === null || row.opportunity_score === undefined ? "Missing" : `${row.opportunity_score} / 100`;
  return `<div class="detail-item detail-wide score-breakdown"><dt>Trend Strength vs Opportunity Score</dt><dd><p>Trend Strength: ${escapeHtml(row.trend_strength)} / 100 · Opportunity Score: ${escapeHtml(opportunity)} · Completeness: ${escapeHtml(row.data_completeness)}% · Confidence: ${escapeHtml(row.confidence)}</p><ul>${factors}</ul></dd></div>`;
}

function renderAiHorizons(horizons = {}) {
  return `<div class="detail-item detail-wide"><dt>Three Horizons</dt><dd><strong>Near-term</strong><p>${escapeHtml(horizons.near_term || "Missing")}</p><strong>6–36 months</strong><p>${escapeHtml(horizons.six_to_36_months || "Missing")}</p><strong>3–10 years</strong><p>${escapeHtml(horizons.three_to_10_years || "Missing")}</p></dd></div>`;
}

function renderAiEvidence(label, evidence = []) {
  const rows = evidence.map((item) => `<li><strong>${escapeHtml(companyTickerLabel(item))}</strong> · ${escapeHtml(item.age_band || "Age missing")} · ${escapeHtml(formatNewsDate(item.event_date))}<br>${escapeHtml(item.new_information || "Evidence detail missing")}</li>`).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>${escapeHtml(label)}</dt><dd><ul>${rows || "<li>Missing / no connected evidence.</li>"}</ul></dd></div>`;
}

function renderDiscoveryEvidence(label, evidence = [], missingCopy) {
  if (!evidence.length) return `<p><strong>${escapeHtml(label)}:</strong> ${escapeHtml(missingCopy)}</p>`;
  const rows = evidence.slice(0, 3).map((item) => {
    const types = (item.evidence_types || []).join(", ") || "Evidence type missing";
    return `<li><strong>${escapeHtml(types)}</strong> — ${escapeHtml(item.basis || item.headline || "Evidence detail missing")}</li>`;
  }).join("");
  return `<p><strong>${escapeHtml(label)}</strong></p><ul>${rows}</ul>`;
}

function renderAiBeneficiaries(rows = [], trend = "") {
  const items = rows.map((item) => `<li><strong>${escapeHtml(companyTickerLabel(item))}</strong> — ${escapeHtml(item.opportunity_stage || "Stage unavailable")} · ${escapeHtml(item.category)} — relevance ${escapeHtml(item.beneficiary_relevance)}/100 · completeness ${escapeHtml(item.data_completeness)}%
    ${renderDiscoveryEvidence("Thesis Evidence", item.thesis_evidence || [], "Missing / logical beneficiary thesis has not been structured.")}
    ${renderDiscoveryEvidence("Confirmation Evidence", item.confirmation_evidence || [], "Not yet commercially confirmed; orders, backlog, customers, guidance, and revenue are not required for early Radar entry.")}
    <p>${escapeHtml(marketSnapshotText(item.market_data, "qqq"))}</p>${watchlistAction(item.ticker, item.company, "Radar", "ai")}</li>`).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>Evidence-Supported Beneficiaries</dt><dd><ul>${items || "<li>Missing / insufficient evidence.</li>"}</ul></dd></div>`;
}

function renderAiHistory(row) {
  const history = (row.score_history || []).slice(-5).reverse().map((item) => `<li>${escapeHtml(formatNewsDate(item.as_of))}: Trend ${escapeHtml(item.trend_strength ?? "Missing")} · Opportunity ${escapeHtml(item.opportunity_score ?? "Missing")} · Completeness ${escapeHtml(item.data_completeness)}% · ${escapeHtml(item.confidence)}</li>`).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>Evidence / Score History</dt><dd><p>${escapeHtml(row.why_changed || "Missing")}</p><ul>${history || "<li>No prior snapshot.</li>"}</ul></dd></div>`;
}

function aiBeneficiaryLabels(row, limit = null) {
  const records = Array.isArray(row.beneficiary_records) ? row.beneficiary_records : [];
  if (!records.length) return row.potential_beneficiaries || row.beneficiaries || "Missing / insufficient evidence";
  return (limit ? records.slice(0, limit) : records).map((item) => companyTickerLabel(item)).join("; ");
}

function renderAiRadar(rows) {
  document.getElementById("ai-radar").innerHTML = rows.map((row) => `<details class="radar-item ai-radar-item"><summary>
      <span class="radar-name"><strong>${escapeHtml(row.trend)}</strong><small>Technology trend</small></span>${renderScore(row.trend_strength, "Trend Strength")}
      <span class="direction"><i aria-hidden="true">${row.direction === "Contradicting" ? "↘" : row.direction === "Mixed" ? "↔" : "↗"}</i>${escapeHtml(row.direction)}</span><span><b class="stage ${stageClass(row.adoption_stage || "missing")}">${escapeHtml(row.stage)}</b></span>
      <span class="radar-copy">${escapeHtml(row.why_now)}</span><span class="beneficiaries">${escapeHtml(aiBeneficiaryLabels(row, 3))}</span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid">
      ${detailItem("What It Means", row.what_it_means)}${detailItem("Key Intelligence", row.key_intelligence)}${detailItem("Demand Drivers", row.demand_drivers)}${detailItem("Current Bottleneck", row.current_bottleneck)}${detailItem("Next Likely Bottleneck", row.next_likely_bottleneck)}
      ${detailItem("Beneficiaries", aiBeneficiaryLabels(row))}${detailItem("Market Expectation / Priced In", row.market_expectation, true)}
      ${detailItem("Market Confirmation", row.market_confirmation?.score === null || row.market_confirmation?.score === undefined ? "Missing" : `${row.market_confirmation.score} / 10. ${row.market_confirmation.rationale}`)}
      ${detailItem("Risks / Invalidation", row.risks, true)}${detailItem("What to Watch Next", row.watch_next)}
      ${renderAiFactorBreakdown(row)}${renderAiHorizons(row.horizons)}${renderAiEvidence("Confirming Evidence", row.confirming_evidence)}${renderAiEvidence("Mixed Evidence", row.mixed_evidence)}${renderAiEvidence("Contradicting Evidence", row.contradicting_evidence)}${renderAiBeneficiaries(row.beneficiary_records, row.trend)}${renderAiHistory(row)}
    </dl></details>`).join("") || `<p class="loading-state">No AI trends are available.</p>`;
}

function safeSourceUrl(value) {
  try {
    const url = new URL(String(value));
    return ["https:", "http:"].includes(url.protocol) ? url.href : "";
  } catch (_) { return ""; }
}

function formatNewsDate(value) {
  if (!value) return "Date/time missing";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function newsScore(label, value) {
  const score = Number.isFinite(Number(value)) ? Math.max(0, Math.min(100, Number(value))) : null;
  return `<span class="news-score"><small>${escapeHtml(label)}</small><strong>${score === null ? "Missing" : `${escapeHtml(score)}<i>/100</i>`}</strong></span>`;
}

function companyTickerLabel(row = {}) {
  const company = row.company || "Company missing";
  const ticker = row.ticker && row.ticker !== "Missing" ? ` · ${tickerPriceLabel(row.ticker, row.market_data)}` : "";
  return `${company}${ticker}`;
}

function relatedTickerLabel(row = {}) {
  return Array.isArray(row.related_tickers) && row.related_tickers.length ? `Related: ${row.related_tickers.map((ticker) => tickerPriceLabel(ticker)).join(", ")}` : "";
}

function newsTags(values = []) {
  return values.map((value) => `<span>${escapeHtml(value)}</span>`).join("");
}

function newsCategory(story = {}, kind = "ai") {
  const values = kind === "biotech" ? story.subsectors : story.affected_trends;
  if (Array.isArray(values) && values.length) return values[0];
  return story.subsector || story.category || "";
}

function newsDetail(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "Missing")}</dd></div>`;
}

function renderNewsCard(story, kind = "ai", archived = false) {
  const sourceUrl = safeSourceUrl(story.source_link);
  const affectedFactors = Array.isArray(story.affected_radar_factors) && story.affected_radar_factors.length
    ? story.affected_radar_factors : (story.affected_trends || []);
  const subsectors = Array.isArray(story.subsectors) ? story.subsectors : [];
  const category = newsCategory(story, kind);
  const evidenceSources = (story.evidence_sources || []).map((item) => {
    const url = safeSourceUrl(item.url);
    const label = `${item.primary ? "Primary" : "Corroborating"}: ${item.source}${item.date ? ` · ${formatNewsDate(item.date)}` : ""}`;
    return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>` : escapeHtml(label)}</li>`;
  }).join("");
  const previousToNew = `${story.previous_state || "Missing"} → ${story.new_state || "Missing"}`;
  return `<details class="top-news-card news-item${archived ? " news-item-archived" : ""}">
    <summary class="news-summary">
      <span class="news-summary-copy"><span class="news-summary-meta"><time>${escapeHtml(formatNewsDate(story.published_at))}</time>${category ? `<span class="news-category">${escapeHtml(category)}</span>` : ""}</span><span class="news-headline">${escapeHtml(story.headline || "Headline missing")}</span></span>
      ${newsScore("Importance", story.news_importance_score)}
      <span class="expand-control" aria-hidden="true">+</span>
    </summary>
    <div class="news-detail-panel">
      <dl class="news-detail-grid">
        ${newsDetail("Source", story.source)}
        ${newsDetail("Company / ticker", companyTickerLabel(story))}
        ${newsDetail("Confirmation status", story.status)}
      </dl>
      ${relatedTickerLabel(story) ? `<p class="news-related-tickers">${escapeHtml(relatedTickerLabel(story))}</p>` : ""}
    <div class="news-why"><strong>What changed</strong><p>${escapeHtml(story.new_information || "Missing")}</p></div>
      <dl class="news-detail-grid">
        ${newsDetail("Event type", story.event_type)}
        ${newsDetail("Development stage / evidence level", story.development_stage)}
        ${newsDetail("Indication", story.indication)}
        ${newsDetail("Previous → new state", previousToNew)}
        ${newsDetail("Direction", story.direction)}
        <div><dt>Affected Radar factors</dt><dd class="news-trend-tags">${newsTags(affectedFactors) || "Missing"}</dd></div>
        <div><dt>Subsector</dt><dd class="news-trend-tags">${newsTags(subsectors) || escapeHtml(story.subsector || "Missing")}</dd></div>
      </dl>
      <div class="news-evidence-sources"><strong>Sources &amp; evidence</strong>${evidenceSources ? `<ul>${evidenceSources}</ul>` : `<p class="missing-value">Missing</p>`}</div>
    ${sourceUrl ? `<a class="news-source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read source <span aria-hidden="true">↗</span></a>` : `<span class="news-source-link missing-value">Source link missing</span>`}
    </div>
  </details>`;
}

function renderTopNews(section = {}) {
  const stories = Array.isArray(section.stories) ? section.stories : [];
  const archive = Array.isArray(section.important_news_archive) ? section.important_news_archive : [];
  setText("ai-news-selection-status", section.selection_status || "AI Technology News V1 active");
  setText("ai-news-archive-count", archive.length);
  document.getElementById("ai-top-news").innerHTML = stories.map((story) => renderNewsCard(story, "ai")).join("") || `<p class="loading-state">No source-qualified AI or technology stories are available yet. The daily updater will preserve prior selections when feeds are unavailable.</p>`;
  document.getElementById("ai-news-archive").innerHTML = archive.map((story) => renderNewsCard(story, "ai", true)).join("") || `<p class="loading-state">The archive will populate as important stories rotate out of Top Investment News.</p>`;
}

function renderBiotechNews(section = {}) {
  const stories = Array.isArray(section.stories) ? section.stories : [];
  const archive = Array.isArray(section.important_news_archive) ? section.important_news_archive : [];
  setText("biotech-news-selection-status", section.selection_status || "Biotech News V1 active");
  setText("biotech-news-archive-count", archive.length);
  document.getElementById("biotech-top-news").innerHTML = stories.map((story) => renderNewsCard(story, "biotech")).join("") || `<p class="loading-state">No biotech events currently meet the prominent-news threshold. Qualified events remain available in Evidence History.</p>`;
  document.getElementById("biotech-news-archive").innerHTML = archive.map((story) => renderNewsCard(story, "biotech", true)).join("") || `<p class="loading-state">Evidence History will populate when events score 65–79 or rotate out of prominent news.</p>`;
}

function renderScoreBreakdown(components = [], completeness) {
  const rows = components.map((component) => `<li class="${component.missing ? "score-component-missing" : ""}">
    <span>${escapeHtml(component.label)}</span><strong>${component.score === null || component.score === undefined ? "Missing" : `${escapeHtml(component.score)} / ${escapeHtml(component.weight)}`}</strong>
    <small>${escapeHtml(component.rationale)}</small></li>`).join("");
  return `<div class="detail-item detail-wide score-breakdown"><dt>Score Breakdown</dt><dd><ul>${rows}</ul>
    <p>Data completeness: ${escapeHtml(completeness)}%. Opportunity Score is normalized over available weighted inputs; missing inputs are excluded rather than scored as zero.</p></dd></div>`;
}

function renderBiotechEvidenceGroup(label, events = []) {
  const items = events.map((event) => `<li><strong>${escapeHtml(event.relation || "Evidence")}</strong> · ${escapeHtml(formatNewsDate(event.published_at))} · ${escapeHtml(event.age_band || "Age missing")}<br>${escapeHtml(event.new_information || "Evidence detail missing")}</li>`).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>${escapeHtml(label)}</dt><dd><ul>${items || "<li>Missing / no connected evidence.</li>"}</ul></dd></div>`;
}

function renderBiotechHistory(row) {
  const history = (row.score_history || []).slice(-5).reverse().map((item) => `<li>${escapeHtml(formatNewsDate(item.as_of))}: Opportunity ${escapeHtml(item.opportunity_score ?? "Missing")} · Scientific ${escapeHtml(item.scientific_evidence_score ?? "Missing")} · Binary Risk ${escapeHtml(item.binary_risk)} · Completeness ${escapeHtml(item.data_completeness)}%</li>`).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>Evidence / Score History</dt><dd><p>${escapeHtml(row.why_changed || "Missing")}</p><ul>${history || "<li>No prior snapshot.</li>"}</ul></dd></div>`;
}

function renderSources(sources = [], scoreAsOf) {
  const links = sources.map((item) => {
    const url = safeSourceUrl(item.url);
    const label = `${item.title}${item.date ? ` (${item.date})` : ""}`;
    return url ? `<li><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a></li>` : `<li>${escapeHtml(label)}</li>`;
  }).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>Evidence Sources</dt><dd><ul>${links || "<li>No source connected.</li>"}</ul>
    <p>Score as of ${escapeHtml(scoreAsOf)}.</p></dd></div>`;
}

function renderBiotechRadar(rows) {
  document.getElementById("biotech-radar").innerHTML = rows.map((row) => `<details class="radar-item biotech-radar-item"><summary>
      <span class="radar-name"><strong>${escapeHtml(row.company)}</strong><small>${escapeHtml(tickerPriceLabel(row.ticker, row.market_data))} · ${escapeHtml(row.program)} · ${escapeHtml(row.indication)} · ${escapeHtml(row.catalyst)}</small></span>${renderScore(row.opportunity_score, "Opportunity Score")}
      <span class="timing">${escapeHtml(row.expected_timing)}</span><span><b class="stage ${stageClass(row.stage)}">${escapeHtml(row.stage)}</b></span>
      <span class="radar-copy">${escapeHtml(row.why_important)}</span><span class="status-badge ${stageClass(row.opportunity_status)}">${escapeHtml(row.opportunity_status)}</span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid biotech-details">
      ${detailItem("Company → Program → Indication → Catalyst", `${row.company} (${tickerPriceLabel(row.ticker, row.market_data)}) → ${row.program} → ${row.indication} → ${row.catalyst}`)}
      ${detailItem("Clinical Evidence", row.clinical_evidence, String(row.clinical_evidence).startsWith("Missing"))}${detailItem("Upcoming Catalyst", row.upcoming_catalyst)}${detailItem("Previous Trial Results", row.previous_results, String(row.previous_results).startsWith("Missing"))}
      ${detailItem("FDA / Regulatory Status", row.regulatory_status)}${detailItem("Commercial Potential", row.commercial_potential)}
      ${detailItem("Market Expectation / Priced In", row.market_expectation, String(row.market_expectation).startsWith("Missing"))}${detailItem("Positioning / Short Interest", row.positioning, String(row.positioning).startsWith("Missing"))}
      ${detailItem("Risks", row.risks)}${detailItem("What to Watch Next", row.watch_next)}
      ${detailItem("Scientific Evidence", row.scientific_evidence_score === null ? "Missing" : `${row.scientific_evidence_score} / 30`)}${detailItem("Catalyst Impact / Company Sensitivity", `${row.catalyst_impact_score} / 25. ${row.company_sensitivity}`)}${detailItem("Expectation Gap", row.expectation_gap_score === null ? "Missing" : `${row.expectation_gap_score} / 20`)}
      ${detailItem("Binary Risk", `${row.binary_risk}. ${row.binary_risk_rationale}`)}${detailItem("Data Completeness / Confidence", `${row.data_completeness}% / ${row.confidence}`)}${detailItem("Evidence Gate", `${row.evidence_gate.passed ? "Passed" : "Not passed"}. ${row.evidence_gate.rule}`)}
      ${detailItem("Evidence Integrity Gate", `${row.evidence_integrity_gate.concern_identified ? "Concern identified; confidence capped." : "No explicit integrity concern identified in connected evidence."} ${row.evidence_integrity_gate.rule}`)}
      ${renderMarketSnapshot(row.market_data, "xbi")}${renderMarketSnapshot(row.sector_market_data, "sp500")}
      ${renderScoreBreakdown(row.score_components, row.data_completeness)}${renderSources(row.sources, row.score_as_of)}
      ${renderBiotechEvidenceGroup("Confirming Evidence", row.confirming_evidence)}${renderBiotechEvidenceGroup("Mixed Evidence", row.mixed_evidence)}${renderBiotechEvidenceGroup("Contradicting Evidence", row.contradicting_evidence)}${renderBiotechHistory(row)}
      <div class="detail-item detail-wide"><dt>Active Monitoring</dt><dd>${watchlistAction(row.ticker, row.company, "Radar", "biotech")}</dd></div>
    </dl></details>`).join("") || `<p class="loading-state">No biotech opportunities are available.</p>`;
}

function buyDecisionFor(row = {}) {
  if (row.buy_decision?.status) return row.buy_decision;
  const entry = row.entry_timing || {};
  const mapping = {
    "breakout-confirmed": ["ready-to-buy", "READY TO BUY"],
    "buy-zone": ["in-entry-zone", "IN ENTRY ZONE"],
    "near-buy-zone": ["approaching-entry", "APPROACHING ENTRY"],
    extended: ["extended", "EXTENDED / TOO LATE"],
  };
  const mapped = mapping[entry.state_key] || ["wait", "WAIT"];
  const ready = entry.actionable && ["ready-to-buy", "in-entry-zone"].includes(mapped[0]);
  return { status_key: mapped[0], status: mapped[1], ready_now: ready,
    why_buy_now: ready ? entry.entry_guidance : "Not ready now under the existing thesis and Entry Timing rules.",
    missing_condition: ready ? "None under the current rules; continue monitoring the documented gates." : (entry.entry_guidance || "A complete buy setup is still missing."),
    timing_state: entry.state, entry_timing_score: entry.entry_timing_score };
}

function decisionPrice(value, currency = "USD") {
  return value === null || value === undefined ? "Unavailable" : currentPriceLabel("VALUE", { current_price: value, currency });
}

function renderBuyDecision(row, isBiotech, decision) {
  const swing = row.swing_trade || {};
  const currency = swing.currency || row.market_data?.currency || "USD";
  const zone = swing.entry_zone || {};
  const targets = swing.targets || {};
  const zoneText = zone.low === null || zone.low === undefined || zone.high === null || zone.high === undefined
    ? "Unavailable" : `${decisionPrice(zone.low, currency)} – ${decisionPrice(zone.high, currency)}${zone.active ? " · Active" : " · Planning reference only"}`;
  const biotechFields = isBiotech ? `<dl class="biotech-buy-grid">
      <div><dt>Current Price</dt><dd>${escapeHtml(currentPriceLabel(row.ticker, row.market_data) || "Unavailable")}</dd></div>
      <div><dt>Entry Zone</dt><dd>${escapeHtml(zoneText)}</dd></div>
      <div><dt>Buy Status</dt><dd>${escapeHtml(decision.status || "WAIT")}</dd></div>
      <div><dt>+10% Target</dt><dd>${escapeHtml(decisionPrice(targets.plus_10, currency))}</dd></div>
      <div><dt>+15% Target</dt><dd>${escapeHtml(decisionPrice(targets.plus_15, currency))}</dd></div>
      <div><dt>+20% Target</dt><dd>${escapeHtml(decisionPrice(targets.plus_20, currency))}</dd></div>
      <div><dt>Binary Risk</dt><dd>${escapeHtml(row.binary_risk || "Missing")}</dd></div>
      <div class="opportunity-wide"><dt>Catalyst</dt><dd>${escapeHtml(row.catalyst || "Missing")}${row.catalyst_timing ? ` · ${escapeHtml(row.catalyst_timing)}` : ""}</dd></div>
    </dl><p class="buy-plan-note">${escapeHtml(zone.basis || "Entry-zone methodology unavailable.")} ${escapeHtml(targets.basis || "")}</p>` : "";
  return `<section class="buy-decision-panel buy-decision-${stageClass(decision.status_key)}">
    <div class="buy-decision-heading"><span>Buy decision</span><strong>${escapeHtml(decision.status || "WAIT")}</strong><small>${escapeHtml(decision.timing_state || "Timing state unavailable")}${decision.entry_timing_score === null || decision.entry_timing_score === undefined ? "" : ` · ${escapeHtml(decision.entry_timing_score)}/100`}</small></div>
    ${biotechFields}
    <dl class="buy-decision-reasons"><div><dt>Why Buy Now</dt><dd>${escapeHtml(decision.why_buy_now || "Missing")}</dd></div><div><dt>What Condition Is Still Missing?</dt><dd>${escapeHtml(decision.missing_condition || "Missing")}</dd></div></dl>
  </section>`;
}

function renderWhyThisStock(row) {
  const why = row.why_this_stock || {};
  return `<section class="why-this-stock"><h4>Why This Stock</h4><p>${escapeHtml(why.summary || row.why_selected || "Selection reasoning is unavailable.")}</p>
    <dl><div><dt>Trend / Catalyst</dt><dd>${escapeHtml(why.trend_or_catalyst || row.catalyst || "Missing")}</dd></div>
    <div><dt>Evidence Supporting the Thesis</dt><dd>${escapeHtml(why.supporting_evidence || "Missing")}</dd></div>
    <div><dt>Why It Ranks Here</dt><dd>${escapeHtml(why.relative_strength || "Missing")}</dd></div>
    <div><dt>Main Risk / Missing Condition</dt><dd>${escapeHtml(why.main_risk_or_missing || row.thesis_invalidation || "Missing")}</dd></div>
    <div class="opportunity-wide"><dt>Current Buy / Entry Status</dt><dd>${escapeHtml(why.buy_status || row.buy_decision?.status || "WAIT")}</dd></div></dl></section>`;
}

function renderOpportunities(targetId, rows = []) {
  const isBiotech = targetId.includes("biotech");
  document.getElementById(targetId).innerHTML = rows.map((row) => {
    const factors = (row.factor_scores || []).map((factor) => `<li class="${factor.missing ? "factor-missing" : ""}"><span>${escapeHtml(factor.label)}</span><strong>${factor.score === null || factor.score === undefined ? "Missing" : `${escapeHtml(factor.score)}/100`}</strong><small>${escapeHtml(factor.available_weight ?? (factor.missing ? 0 : factor.weight))}/${escapeHtml(factor.weight)} weight available</small></li>`).join("");
    const gates = (row.gates || []).map((gate) => `<li class="gate-${gate.passed === true ? "pass" : gate.passed === false ? "fail" : "missing"}" title="${escapeHtml(gate.rationale)}"><span aria-hidden="true">${gate.passed === true ? "✓" : gate.passed === false ? "×" : "—"}</span>${escapeHtml(gate.label)}</li>`).join("");
    const technical = row.technical_entry_status || row.timing_support || {};
    const quality = row.company_quality || {};
    const entry = row.entry_timing || {};
    const entryFactors = (entry.factors || []).map((factor) => `<li class="${factor.missing ? "factor-missing" : ""}"><span>${escapeHtml(factor.label)}</span><strong>${factor.score === null || factor.score === undefined ? "Missing" : `${escapeHtml(factor.score)}/100`}</strong><small>${escapeHtml(factor.rationale)}</small></li>`).join("");
    const entryGates = (entry.gates || []).map((gate) => `<li class="gate-${gate.passed === true ? "pass" : gate.passed === false ? "fail" : "missing"}" title="${escapeHtml(gate.rationale)}"><span aria-hidden="true">${gate.passed === true ? "✓" : gate.passed === false ? "×" : "—"}</span>${escapeHtml(gate.label)}</li>`).join("");
    const decision = buyDecisionFor(row);
    const score = row.final_score === null || row.final_score === undefined ? "Missing" : `${row.final_score}/100`;
    return `<details class="opportunity-card opportunity-${escapeHtml(row.classification_key || "unclassified")}"><summary class="opportunity-summary"><span class="opportunity-rank">${escapeHtml(row.rank)}</span>
      <div><div class="opportunity-top"><h4>${escapeHtml(companyTickerLabel(row))}</h4><span class="opportunity-classification">${escapeHtml(row.classification || "Classification missing")}</span></div>
      <div class="opportunity-score-line"><strong>${escapeHtml(score)}</strong><span>${escapeHtml(row.data_completeness ?? "Missing")}% complete</span><span class="opportunity-timing-pill buy-status-${stageClass(decision.status_key)}">${escapeHtml(decision.status || "WAIT")}</span></div></div><span class="opportunity-expand" aria-hidden="true"></span></summary>
      <div class="opportunity-detail">
      ${renderWhyThisStock(row)}
      ${watchlistAction(row.ticker, row.company, "High Conviction", isBiotech ? "biotech" : "ai")}
      ${renderBuyDecision(row, isBiotech, decision)}
      <p class="opportunity-why"><strong>Why selected:</strong> ${escapeHtml(row.why_selected || row.thesis || "Missing")}</p>
      <ul class="opportunity-factors">${factors || "<li class=\"factor-missing\"><span>Factor scores</span><strong>Missing</strong></li>"}</ul>
      <dl><div><dt>Company Quality</dt><dd><strong>${quality.company_quality_score === null || quality.company_quality_score === undefined ? "Missing" : `${escapeHtml(quality.company_quality_score)}/100`}</strong> · ${escapeHtml(quality.data_completeness ?? 0)}% complete · ${escapeHtml(quality.confidence || "Low")} confidence${quality.latest_period_end ? ` · period ${escapeHtml(quality.latest_period_end)}` : ""}</dd></div><div><dt>Expectation state</dt><dd>${escapeHtml(row.expectation_state || row.expectation?.state || "Data Insufficient")}</dd></div><div><dt>Technical / entry status</dt><dd><strong>${escapeHtml(technical.signal || "Insufficient Data")}</strong> · ${escapeHtml(technical.rationale || "Market inputs missing.")}</dd></div>${isBiotech ? "" : `<div><dt>Catalyst</dt><dd>${escapeHtml(row.catalyst || "Missing")}${row.catalyst_timing ? ` · ${escapeHtml(row.catalyst_timing)}` : ""}</dd></div>`}<div><dt>Action</dt><dd>${escapeHtml(row.action || "Missing")}</dd></div><div class="opportunity-wide"><dt>Thesis invalidation</dt><dd>${escapeHtml(row.thesis_invalidation || "Missing")}</dd></div></dl>
      <ul class="opportunity-gates" aria-label="High-conviction gates">${gates}</ul>
      <details class="entry-timing-details"><summary><span><small>Entry Timing Score</small>${escapeHtml(entry.state || "Entry timing unavailable")}</span><strong>${entry.entry_timing_score === null || entry.entry_timing_score === undefined ? "Missing" : `${escapeHtml(entry.entry_timing_score)}/100`}</strong><small>${escapeHtml(entry.data_completeness ?? 0)}% complete</small></summary><div class="entry-timing-body"><p>${escapeHtml(entry.entry_guidance || "Entry guidance unavailable because technical inputs are missing.")}</p><dl><div><dt>Resistance / breakout</dt><dd>${entry.resistance_level === null || entry.resistance_level === undefined ? "Missing" : formatMarketValue(entry.resistance_level)}${entry.price_date ? ` · as of ${escapeHtml(entry.price_date)}` : ""}</dd></div><div><dt>Technical invalidation</dt><dd>${entry.invalidation_level === null || entry.invalidation_level === undefined ? "Missing" : formatMarketValue(entry.invalidation_level)}</dd></div></dl><ul class="entry-factor-list">${entryFactors}</ul><ul class="opportunity-gates" aria-label="Entry timing gates">${entryGates}</ul></div></details></div></details>`;
  }).join("") || `<p class="loading-state">No opportunities are available.</p>`;
}

function renderSwingTrades(section = {}) {
  const reasoning = section.reasoning || [];
  const takeaways = section.take_home_messages || [];
  document.getElementById("swing-reasoning").innerHTML = reasoning.map((item) => `<p>${escapeHtml(item)}</p>`).join("") || `<p>No swing-trade strategy reasoning is available.</p>`;
  document.getElementById("swing-takeaways").innerHTML = takeaways.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || `<li>No qualifying swing-trade conclusions are available.</li>`;
  const rows = section.opportunities || [];
  document.getElementById("swing-opportunities").innerHTML = rows.map((row) => {
    const technical = row.technical || {};
    const catalyst = row.catalyst || {};
    const why = row.why_this_swing_trade_opportunity || {};
    const market = row.market_data || {};
    const sourceUrl = safeSourceUrl(catalyst.source_link);
    const formatPrice = (value) => value === null || value === undefined ? "Unavailable" : decisionPrice(value, market.currency || "USD");
    return `<details class="swing-card"><summary class="swing-summary"><span class="opportunity-rank">${escapeHtml(row.rank)}</span><div><h4>${escapeHtml(tickerPriceLabel(row.ticker, market))}</h4><small>${escapeHtml(row.company)} · Technical ${escapeHtml(technical.technical_setup_score ?? "Missing")}/100</small></div><span class="swing-state swing-state-${classKey(row.classification)}">${escapeHtml(row.classification)}</span><span class="opportunity-expand" aria-hidden="true"></span></summary>
      <div class="swing-detail"><section class="swing-why"><h4>Why This Swing Trade Opportunity</h4><ol>
        <li>${escapeHtml(why.why_chart_selected || "Technical selection reasoning unavailable.")}</li>
        <li>${escapeHtml(why.bottom_reversal_stage || "Bottom/reversal stage unavailable.")}</li>
        <li>${escapeHtml(why.why_still_early || "Entry-timing interpretation unavailable.")}</li>
        <li>${escapeHtml(why.catalyst_support || "Catalyst support unavailable.")}</li>
        <li>${escapeHtml(why.invalidation || "Invalidation condition unavailable.")}</li>
      </ol></section>
      <dl class="swing-technical-grid"><div><dt>Classification</dt><dd>${escapeHtml(row.classification)}</dd></div><div><dt>Current Price</dt><dd>${escapeHtml(formatPrice(technical.current_price))}</dd></div><div><dt>MA20</dt><dd>${escapeHtml(formatPrice(technical.ma20))}</dd></div><div><dt>MA50</dt><dd>${escapeHtml(formatPrice(technical.ma50))}</dd></div>
        <div><dt>Price vs MA20 / MA50</dt><dd>${escapeHtml(formatChange(technical.price_vs_ma20_pct))} / ${escapeHtml(formatChange(technical.price_vs_ma50_pct))}</dd></div><div><dt>Decline from 52W High</dt><dd>${escapeHtml(formatChange(technical.drawdown_from_high_pct))}</dd></div><div><dt>Recent Low</dt><dd>${escapeHtml(formatPrice(technical.recent_low))}</dd></div><div><dt>Distance From Bottom</dt><dd>${escapeHtml(formatChange(technical.distance_from_bottom_pct))}</dd></div>
        <div><dt>Bottom Formation</dt><dd>${technical.bottom_stabilized ? "Stabilization rule passed" : "Still forming / not confirmed"}${technical.base_duration_sessions ? ` · ${escapeHtml(technical.base_duration_sessions)} sessions` : ""}</dd></div><div><dt>Early Reversal</dt><dd>${technical.early_reversal_confirmed ? "Confirmed by available momentum rules" : "Not yet confirmed"}</dd></div><div><dt>RSI / MACD</dt><dd>${escapeHtml(technical.rsi_14 ?? "Missing")} / ${escapeHtml(technical.macd?.histogram ?? "Missing")}</dd></div><div><dt>Volume vs 20D Average</dt><dd>${technical.volume_vs_20d_average === null || technical.volume_vs_20d_average === undefined ? "Unavailable" : `${escapeHtml(technical.volume_vs_20d_average)}x`}</dd></div>
        <div><dt>Support</dt><dd>${escapeHtml(formatPrice(technical.support))}</dd></div><div><dt>Resistance</dt><dd>${escapeHtml(formatPrice(technical.resistance))}</dd></div><div><dt>Invalidation</dt><dd>${escapeHtml(formatPrice(technical.invalidation_level))}</dd></div><div><dt>Extended?</dt><dd>${technical.extended ? "Yes — do not chase" : "No"}</dd></div></dl>
      <section class="swing-catalyst"><h5>Step 2 · Credible Catalyst Check</h5><p><strong>${escapeHtml(catalyst.event_type || "Catalyst")}</strong> · ${escapeHtml(catalyst.description || "Missing")}</p><p>Timing: ${escapeHtml(catalyst.timing || "Missing")} · Source: ${escapeHtml(catalyst.source || "Missing")}${catalyst.date ? ` · ${escapeHtml(catalyst.date)}` : ""}</p><p>${escapeHtml(catalyst.basis || "Missing")}</p>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read Source</a>` : ""}</section>
      ${watchlistAction(row.ticker, row.company, "Swing Trade", row.domain || "ai")}</div></details>`;
  }).join("") || `<p class="loading-state">No stock currently passes both the technical-first screen and the credible-catalyst check.</p>`;
}

function automaticWatchlistSelections(data) {
  const selected = new Map();
  const add = (row, source, domain, why, context) => {
    const ticker = normalizedTicker(row?.ticker);
    if (!ticker || ["PRIVATE", "N/A", "MISSING"].includes(ticker)) return;
    if (!selected.has(ticker)) selected.set(ticker, { ticker, company: row.company || ticker, domain, sources: [], records: [], contexts: [] });
    const item = selected.get(ticker);
    if (!item.sources.includes(source)) item.sources.push(source);
    if (domain === "biotech") item.domain = "biotech";
    item.records.push({ source, row, why, context });
    if (context && !item.contexts.includes(context)) item.contexts.push(context);
  };
  for (const trend of data.radar?.ai || []) {
    for (const beneficiary of trend.beneficiary_records || []) {
      const thesis = beneficiary.thesis_evidence?.[0]?.basis || trend.what_it_means || trend.why_now;
      add(beneficiary, "Radar", "ai", `Why on Radar: ${beneficiary.company} is an evidence-linked beneficiary of ${trend.trend}. ${thesis}`,
        `Radar growth thesis — ${trend.trend}: ${thesis}`);
    }
  }
  for (const row of data.radar?.biotech || []) add(row, "Radar", "biotech", row.why_important,
    `Radar catalyst — ${row.program}: ${row.catalyst}. ${row.clinical_evidence || "Evidence detail missing."}`);
  for (const domain of ["ai", "biotech"]) {
    for (const row of data.monthly_picks?.[domain] || []) add(row, "High Conviction", domain,
      row.why_this_stock?.summary || row.why_selected,
      `High Conviction quality thesis: ${row.why_this_stock?.supporting_evidence || row.why_selected || "Missing"}`);
  }
  for (const row of data.swing_trade_opportunities?.opportunities || []) add(row, "Swing Trade", row.domain || "ai",
    row.why_this_swing_trade_opportunity?.why_chart_selected,
    `Swing setup — ${row.classification}: ${row.why_this_swing_trade_opportunity?.bottom_reversal_stage || ""} Catalyst: ${row.catalyst?.description || "Missing"}. Invalidation: ${row.why_this_swing_trade_opportunity?.invalidation || "Missing"}`);
  currentAutomaticWatchlistTickers = new Set(selected.keys());
  return selected;
}

function watchlistTechnical(snapshot = {}, domain = "ai") {
  const price = snapshot.current_price; const averages = snapshot.moving_averages || {}; const inputs = snapshot.entry_inputs || {}; const macd = snapshot.macd || {};
  const ma20 = averages.ma20; const ma50 = averages.ma50;
  const distance = (reference) => Number.isFinite(Number(price)) && Number.isFinite(Number(reference)) && Number(reference) > 0 ? Math.round((price / reference - 1) * 10000) / 100 : null;
  const vs20 = distance(ma20); const vs50 = distance(ma50); const proximity = inputs.breakout_proximity_pct;
  const volumeRatio = snapshot.volume_vs_20d_average; const rsi = snapshot.rsi_14;
  const extended = (Number.isFinite(Number(rsi)) && rsi >= 75) || (Number.isFinite(Number(inputs.distance_from_recent_low_pct)) && inputs.distance_from_recent_low_pct >= 35);
  let buyStatus = "WAIT";
  if (extended) buyStatus = "EXTENDED / TOO LATE";
  else if (Number.isFinite(Number(proximity)) && proximity >= -1 && proximity <= 2 && volumeRatio >= 1.2 && vs20 >= 0 && vs50 >= 0) buyStatus = "READY TO BUY";
  else if (Number.isFinite(Number(proximity)) && proximity >= -3 && proximity <= 2 && vs20 >= 0) buyStatus = "IN ENTRY ZONE";
  else if ((Number.isFinite(Number(proximity)) && proximity >= -8 && proximity < -3) || (vs20 >= 0 && macd.improving)) buyStatus = "APPROACHING ENTRY";
  const resistance = inputs.resistance_level;
  const entryZone = Number.isFinite(Number(resistance)) ? { low: Math.round(resistance * .99 * 100) / 100, high: Math.round(resistance * 1.01 * 100) / 100, reference: resistance } : { low: null, high: null, reference: null };
  const supportCandidates = [inputs.base_low, ma20, ma50, inputs.invalidation_level].filter((value) => Number.isFinite(Number(value)) && Number(value) < Number(price));
  const support = supportCandidates.length ? Math.max(...supportCandidates) : null;
  const trend = vs20 === null || vs50 === null ? "Data unavailable" : vs20 >= 0 && vs50 >= 0 ? "Constructive uptrend" : vs20 < 0 && vs50 < 0 ? "Weak/downtrend" : "Mixed / transition";
  const bottom = inputs.base_duration_sessions ? `${inputs.base_duration_sessions}-session consolidation detected; this is a range rule, not proof of a durable bottom.` : "No qualifying 42/63-session consolidation; bottom formation is not confirmed.";
  const reversal = macd.crossover === "bullish" ? "Bullish MACD crossover detected." : macd.improving ? "Momentum is improving, but reversal confirmation is incomplete." : macd.histogram === null || macd.histogram === undefined ? "Reversal data unavailable." : "No confirmed momentum reversal in the available MACD data.";
  const volumeTrend = volumeRatio === null || volumeRatio === undefined ? "Unavailable" : `${formatMarketValue(volumeRatio)}x 20-day average${inputs.up_down_volume_ratio_20d === null || inputs.up_down_volume_ratio_20d === undefined ? "" : ` · up/down volume ${formatMarketValue(inputs.up_down_volume_ratio_20d)}x`}`;
  const targets = domain === "biotech" && entryZone.reference ? { plus_10: Math.round(entryZone.reference * 1.1 * 100) / 100, plus_15: Math.round(entryZone.reference * 1.15 * 100) / 100, plus_20: Math.round(entryZone.reference * 1.2 * 100) / 100 } : null;
  return { current_price: price, ma20, ma50, price_vs_ma20_pct: vs20, price_vs_ma50_pct: vs50, support, resistance,
    volume_vs_20d_average: volumeRatio, volume_trend: volumeTrend, trend, bottom_formation: bottom, reversal_status: reversal,
    entry_zone: entryZone, buy_status: buyStatus, invalidation_level: inputs.invalidation_level, targets,
    target_basis: targets ? "Planned watchlist entry reference" : null };
}

function waitingCondition(technical) {
  if (technical.buy_status === "READY TO BUY") return "No additional trigger under the current technical rules; confirm the move continues to hold above the entry area.";
  if (technical.buy_status === "IN ENTRY ZONE") return "Wait for confirming volume and price acceptance above the entry reference before treating the setup as ready.";
  if (technical.buy_status === "APPROACHING ENTRY") return "Price still needs to reach and hold the entry area with improving momentum and volume.";
  if (technical.buy_status === "EXTENDED / TOO LATE") return "Do not chase; wait for extension to normalize and a new base or controlled pullback to form.";
  return "A tighter base, improving momentum, and price confirmation near resistance are still missing.";
}

function hydratedWatchlistRows(data) {
  const selected = automaticWatchlistSelections(data);
  for (const manual of initializeWatchlistState(data).manual_items) {
    const ticker = normalizedTicker(manual.ticker);
    if (!selected.has(ticker)) selected.set(ticker, { ticker, company: manual.company || ticker, domain: manual.domain || sharedMarketSecurities[ticker]?.domains?.[0] || "ai", sources: [], records: [], contexts: [] });
    const item = selected.get(ticker);
    if (!item.sources.includes("Manual")) item.sources.push("Manual");
    const candidate = (data.candidate_discovery?.candidates || []).find((row) => normalizedTicker(row.ticker) === ticker) || { company: manual.company || ticker, ticker };
    item.records.push({ source: "Manual", row: candidate, why: manual.reason || "Manually selected for active technical monitoring.",
      context: "This ticker was personally added and does not need to qualify for another strategy." });
    item.contexts.push("Manual selection: personally added for active technical monitoring.");
  }
  const sourcePriority = { "Swing Trade": 3, "High Conviction": 2, Radar: 1, Manual: 0 };
  return [...selected.values()].map((selection) => {
    const ticker = selection.ticker;
    const primaryRecord = [...selection.records].sort((a, b) => sourcePriority[b.source] - sourcePriority[a.source])[0] || { row: {} };
    const sourceRow = primaryRecord.row;
    const snapshot = sharedMarketSecurities[ticker] || sourceRow.market_data || {};
    const domain = selection.domain || snapshot.domains?.[0] || sourceRow.domain || "ai";
    const technical = watchlistTechnical(snapshot, domain);
    const reasons = selection.records.map((record) => record.why).filter(Boolean);
    const reason = reasons.join(" ") || "Selected for active technical monitoring.";
    const sourceLabel = selection.sources.join(" + ");
    const commentary = {
      why_on_watchlist: reason,
      selection_source: `Sources: ${sourceLabel}. ${selection.contexts.join(" ")}`,
      chart: `${technical.trend}. Price is ${technical.price_vs_ma20_pct ?? "an unknown distance"}% versus MA20 and ${technical.price_vs_ma50_pct ?? "an unknown distance"}% versus MA50. ${technical.bottom_formation} ${technical.reversal_status}`,
      entry: `Buy status is ${technical.buy_status}. ${waitingCondition(technical)}`,
      waiting_for: waitingCondition(technical),
      stronger: "Stronger if price holds above MA20/MA50, MACD improves, and volume confirms a move through resistance.",
      weaker: "Weaker or invalidated if price loses documented support/invalidation, relative strength fades, or volume expands on down days.",
    };
    const biotechRadar = (data.radar?.biotech || []).find((row) => normalizedTicker(row.ticker) === ticker) || {};
    technical.catalyst = sourceRow.catalyst?.description || sourceRow.catalyst || biotechRadar.catalyst || "Missing";
    technical.catalyst_timing = sourceRow.catalyst?.timing || sourceRow.catalyst_timing || biotechRadar.expected_timing || "Missing";
    technical.binary_risk = sourceRow.binary_risk || biotechRadar.binary_risk || "Missing";
    return { ...sourceRow, ticker, company: selection.company || sourceRow.company || ticker, domain, category: domain === "biotech" ? "Biotech" : "AI",
      watchlist_sources: selection.sources, market_data: snapshot, watchlist_commentary: commentary, watchlist_technical: technical };
  }).sort((a, b) => b.watchlist_sources.length - a.watchlist_sources.length || a.ticker.localeCompare(b.ticker));
}

function renderWatchlist(data) {
  const rows = hydratedWatchlistRows(data);
  document.getElementById("my-watchlist").innerHTML = rows.map((row) => {
    const commentary = row.watchlist_commentary || {};
    const technical = row.watchlist_technical || {};
    const currency = row.market_data?.currency || "USD";
    const zone = technical.entry_zone || {};
    const targets = technical.targets || {};
    const isBiotech = row.category === "Biotech";
    const formatTechnicalPrice = (value) => decisionPrice(value, currency);
    const zoneText = zone.low === null || zone.low === undefined || zone.high === null || zone.high === undefined
      ? "Unavailable" : `${formatTechnicalPrice(zone.low)} – ${formatTechnicalPrice(zone.high)}`;
    const biotechFields = isBiotech ? `<div><dt>+10% Level</dt><dd>${escapeHtml(formatTechnicalPrice(targets.plus_10))}</dd></div>
      <div><dt>+15% Level</dt><dd>${escapeHtml(formatTechnicalPrice(targets.plus_15))}</dd></div><div><dt>+20% Level</dt><dd>${escapeHtml(formatTechnicalPrice(targets.plus_20))}</dd></div>
      <div><dt>Catalyst</dt><dd>${escapeHtml(technical.catalyst || row.catalyst || "Missing")}${technical.catalyst_timing && technical.catalyst_timing !== "Missing" ? ` · ${escapeHtml(technical.catalyst_timing)}` : ""}</dd></div>
      <div><dt>Binary Risk</dt><dd>${escapeHtml(technical.binary_risk || "Missing")}</dd></div>` : "";
    const sources = row.watchlist_sources || ["Manual"];
    const sourcePrefix = sources.length > 1 ? "Sources" : "Source";
    const manualAdded = sources.includes("Manual");
    return `<details class="watchlist-card"><summary class="watchlist-summary"><span class="position-identity"><span class="stock-category">${escapeHtml(row.category)}</span><span class="watchlist-source">${sourcePrefix}: ${escapeHtml(sources.join(" + "))}</span><strong>${escapeHtml(tickerPriceLabel(row.ticker, row.market_data))}</strong><small>${escapeHtml(row.company)}</small></span>
      <span><small>Trend</small><strong>${escapeHtml(technical.trend || "Data unavailable")}</strong></span><span><small>Buy Status</small><strong class="watch-buy-status watch-buy-${classKey(technical.buy_status || "wait")}">${escapeHtml(technical.buy_status || "WAIT")}</strong></span><span class="opportunity-expand" aria-hidden="true"></span></summary>
      <div class="watchlist-detail"><section class="watchlist-commentary"><h4>Watchlist Commentary</h4><p><strong>Why it is here:</strong> ${escapeHtml(commentary.why_on_watchlist || row.why || "Missing")}</p><p><strong>Strategy context:</strong> ${escapeHtml(commentary.selection_source || `${sourcePrefix}: ${sources.join(" + ")}`)}</p><p><strong>What the chart is doing:</strong> ${escapeHtml(commentary.chart || "Technical interpretation unavailable.")}</p><p><strong>Entry situation:</strong> ${escapeHtml(commentary.entry || "Entry interpretation unavailable.")}</p><p><strong>What still needs to happen:</strong> ${escapeHtml(commentary.waiting_for || "Missing")}</p><p><strong>Setup strengthens if:</strong> ${escapeHtml(commentary.stronger || "Missing")}</p><p><strong>Setup weakens if:</strong> ${escapeHtml(commentary.weaker || "Missing")}</p></section>
      <dl class="watchlist-technical-grid"><div><dt>Current Price</dt><dd>${escapeHtml(formatTechnicalPrice(technical.current_price))}</dd></div><div><dt>MA20</dt><dd>${escapeHtml(formatTechnicalPrice(technical.ma20))}</dd></div><div><dt>MA50</dt><dd>${escapeHtml(formatTechnicalPrice(technical.ma50))}</dd></div>
      <div><dt>Price vs MA20 / MA50</dt><dd>${escapeHtml(formatChange(technical.price_vs_ma20_pct))} / ${escapeHtml(formatChange(technical.price_vs_ma50_pct))}</dd></div><div><dt>Support</dt><dd>${escapeHtml(formatTechnicalPrice(technical.support))}</dd></div><div><dt>Resistance</dt><dd>${escapeHtml(formatTechnicalPrice(technical.resistance))}</dd></div>
      <div><dt>Volume / Volume Trend</dt><dd>${escapeHtml(technical.volume_trend || (technical.volume_vs_20d_average === null || technical.volume_vs_20d_average === undefined ? "Unavailable" : `${formatMarketValue(technical.volume_vs_20d_average)}x`))}</dd></div><div><dt>Trend</dt><dd>${escapeHtml(technical.trend || "Missing")}</dd></div><div><dt>Bottom Formation</dt><dd>${escapeHtml(technical.bottom_formation || "Missing")}</dd></div>
      <div><dt>Reversal Status</dt><dd>${escapeHtml(technical.reversal_status || "Missing")}</dd></div><div><dt>Entry Zone</dt><dd>${escapeHtml(zoneText)}</dd></div><div><dt>Buy Status</dt><dd>${escapeHtml(technical.buy_status || "WAIT")}</dd></div><div><dt>Invalidation Level</dt><dd>${escapeHtml(formatTechnicalPrice(technical.invalidation_level))}</dd></div>${biotechFields}</dl>
      ${isBiotech && technical.target_basis ? `<p class="watchlist-basis-note">${escapeHtml(technical.target_basis)}; these are planning levels before a brokerage trade, not actual-position P/L targets.</p>` : ""}<div class="watchlist-controls">${manualAdded ? `<button type="button" class="watchlist-action watchlist-remove" data-watchlist-remove data-ticker="${escapeHtml(row.ticker)}">Remove Manual Addition</button>` : `<span class="watchlist-managed-note">Automatically managed by current strategy selections</span>`}</div></div></details>`;
  }).join("") || `<p class="loading-state">No stocks are currently selected for active monitoring.</p>`;
}

function changeClass(value) { const number = Number.parseFloat(value); return number > 0 ? "change-up" : number < 0 ? "change-down" : "change-flat"; }
function formatChange(value) { const number = Number.parseFloat(value); return Number.isFinite(number) ? `${number > 0 ? "+" : ""}${number.toFixed(2)}%` : "N/A"; }
function renderMarkets(markets = []) {
  document.getElementById("market-cards").innerHTML = markets.map((market) => `<article class="market-card"><div><h3>${escapeHtml(market.name)}</h3><span class="market-value">${escapeHtml(market.value)}</span></div><span class="${changeClass(market.daily)}">${formatChange(market.daily)} <small>today</small></span><div class="market-periods"><span>1W<strong class="${changeClass(market.weekly)}">${formatChange(market.weekly)}</strong></span><span>1M<strong class="${changeClass(market.monthly)}">${formatChange(market.monthly)}</strong></span></div></article>`).join("");
}

function initTabs() {
  const tabs = [...document.querySelectorAll("[data-stock-tab]")];
  tabs.forEach((tab) => tab.addEventListener("click", () => {
    tabs.forEach((item) => item.setAttribute("aria-selected", String(item === tab)));
    document.querySelectorAll(".stock-panel").forEach((panel) => { panel.hidden = panel.id !== `stock-panel-${tab.dataset.stockTab}`; });
  }));
}

function renderSafely(render, fallbackId) {
  try {
    render();
  } catch (error) {
    const target = document.getElementById(fallbackId);
    if (target) target.innerHTML = `<p class="loading-state error-state">This section could not be displayed. The rest of the dashboard remains available.</p>`;
    console.error(`GeneDr dashboard section ${fallbackId}:`, error);
  }
}

function setWatchlistStatus(message, type = "") {
  const target = document.getElementById("watchlist-add-status");
  if (!target) return;
  target.textContent = message;
  target.className = `watchlist-add-status${type ? ` is-${type}` : ""}`;
}

function refreshWatchlistUi() {
  if (!currentDashboardData) return;
  renderSafely(() => renderWatchlist(currentDashboardData), "my-watchlist");
  document.querySelectorAll("[data-watchlist-add]").forEach((button) => {
    button.disabled = true;
    button.textContent = "✓ Auto Watchlist";
  });
}

function addWatchlistItem({ ticker, company, source, domain }) {
  const key = normalizedTicker(ticker);
  if (source !== "Manual") {
    setWatchlistStatus(`${key} is automatically managed by ${source}.`, "success");
    return false;
  }
  if (watchlistState.manual_items.some((item) => normalizedTicker(item.ticker) === key)) {
    setWatchlistStatus(`${key} is already preserved as a Manual addition.`, "error");
    return false;
  }
  const snapshot = sharedMarketSecurities[key];
  if (!snapshot) {
    setWatchlistStatus(`${key} is not available in the current shared daily market feed, so it was not added. No unverified quote was substituted.`, "error");
    return false;
  }
  const resolvedDomain = domain || snapshot.domains?.[0] || "ai";
  watchlistState.manual_items.push({ ticker: key, company: company || key, domain: resolvedDomain,
    reason: "Manually selected for active technical monitoring.",
    added_at: new Date().toISOString() });
  writeWatchlistState();
  const combined = currentAutomaticWatchlistTickers.has(key) ? " Its Manual source was added to the existing strategy sources." : "";
  setWatchlistStatus(`${key} was added manually.${combined} Daily data refreshes will update its technicals without removing the Manual selection.`, "success");
  refreshWatchlistUi();
  return true;
}

function removeWatchlistItem(ticker) {
  const key = normalizedTicker(ticker);
  watchlistState.manual_items = watchlistState.manual_items.filter((item) => normalizedTicker(item.ticker) !== key);
  writeWatchlistState();
  const remainsAutomatic = currentAutomaticWatchlistTickers.has(key);
  setWatchlistStatus(remainsAutomatic ? `${key}'s Manual source was removed; it remains because a current strategy still selects it.` : `${key} was removed from the Watchlist.`, "success");
  refreshWatchlistUi();
}

document.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-watchlist-add]");
  if (addButton) {
    event.preventDefault(); event.stopPropagation();
    addWatchlistItem({ ticker: addButton.dataset.ticker, company: addButton.dataset.company,
      source: addButton.dataset.source, domain: addButton.dataset.domain });
    return;
  }
  const removeButton = event.target.closest("[data-watchlist-remove]");
  if (removeButton) { event.preventDefault(); removeWatchlistItem(removeButton.dataset.ticker); }
});

const watchlistForm = document.getElementById("watchlist-add-form");
if (watchlistForm) watchlistForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("watchlist-ticker");
  const ticker = normalizedTicker(input?.value);
  if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) {
    setWatchlistStatus("Enter a valid U.S.-listed ticker using letters, numbers, a period, or a hyphen.", "error");
    return;
  }
  const snapshot = sharedMarketSecurities[ticker];
  const added = addWatchlistItem({ ticker, company: ticker, source: "Manual", domain: snapshot?.domains?.[0] });
  if (added && input) input.value = "";
});

function renderDashboard(data) {
  if (!data || typeof data !== "object") throw new Error("Dashboard JSON is not an object.");
  currentDashboardData = data;
  sharedMarketSecurities = data.market_data?.securities || {};
  initializeWatchlistState(data);
  const updated = new Date(data.updated_at);
  setText("last-updated", Number.isNaN(updated.valueOf()) ? data.updated_at : updated.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }));
  setText("ai-news-summary-copy", data.summaries && data.summaries.ai);
  setText("biotech-news-summary-copy", data.summaries && data.summaries.biotech);
  setText("ai-summary", data.summaries && data.summaries.ai); setText("biotech-summary", data.summaries && data.summaries.biotech); setText("market-movers", data.summaries && data.summaries.market_movers);
  renderDashboardCommentary(data.commentary);
  renderSafely(() => renderTopNews(data.top_investment_news && data.top_investment_news.ai_technology), "ai-top-news");
  renderSafely(() => renderBiotechNews(data.top_investment_news && data.top_investment_news.biotech_healthcare), "biotech-top-news");
  renderSafely(() => renderAiRadar(aiRadarRows(data)), "ai-radar");
  renderSafely(() => renderBiotechRadar(biotechRadarRows(data)), "biotech-radar");
  renderSafely(() => renderOpportunities("ai-opportunities", data.monthly_picks && data.monthly_picks.ai), "ai-opportunities");
  renderSafely(() => renderOpportunities("biotech-opportunities", data.monthly_picks && data.monthly_picks.biotech), "biotech-opportunities");
  renderSafely(() => renderSwingTrades(data.swing_trade_opportunities), "swing-opportunities");
  renderSafely(() => renderWatchlist(data), "my-watchlist");
  renderSafely(() => renderMarkets(data.markets), "market-cards");
}

initTabs();
fetch(DATA_URL, { cache: "no-store", headers: { Accept: "application/json" } }).then((response) => {
  if (!response.ok) throw new Error(`Dashboard data request failed with HTTP ${response.status}.`);
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) throw new Error(`Dashboard data returned ${contentType || "an unknown content type"} instead of JSON.`);
  return response.json();
}).then(renderDashboard).catch((error) => {
  setText("last-updated", "Dashboard temporarily unavailable");
  document.querySelectorAll(".loading-state").forEach((element) => { element.textContent = "The daily data feed could not be loaded. Please try again shortly."; });
  console.error("GeneDr Investment Intelligence dashboard:", error);
});
