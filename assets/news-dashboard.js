const scriptSource = document.currentScript && document.currentScript.src ? document.currentScript.src : document.baseURI;
const dataUrl = new URL("../data/news-dashboard.json", scriptSource);
dataUrl.searchParams.set("_", Date.now().toString());
const DATA_URL = dataUrl.href;

const escapeHtml = (value = "") => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#039;");
const setText = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value ?? "No update available."; };

const PLACEHOLDER_SCORES = [88, 84, 81, 78, 75, 72, 69, 66, 63, 60];
const stageFor = (score) => score >= 85 ? "Hot" : score >= 76 ? "Heating Up" : score >= 66 ? "Emerging" : "Cooling";
const stageClass = (stage = "") => String(stage).toLowerCase().replace(/\s+/g, "-");
const detailItem = (label, value, placeholder = false) => `<div class="detail-item${placeholder ? " detail-placeholder" : ""}"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`;

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

function renderAiBeneficiaries(rows = []) {
  const items = rows.map((item) => `<li><strong>${escapeHtml(companyTickerLabel(item))}</strong> — ${escapeHtml(item.category)} — relevance ${escapeHtml(item.beneficiary_relevance)}/100 · completeness ${escapeHtml(item.data_completeness)}%</li>`).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>Evidence-Supported Beneficiaries</dt><dd><ul>${items || "<li>Missing / insufficient evidence.</li>"}</ul></dd></div>`;
}

function renderAiHistory(row) {
  const history = (row.score_history || []).slice(-5).reverse().map((item) => `<li>${escapeHtml(formatNewsDate(item.as_of))}: Trend ${escapeHtml(item.trend_strength ?? "Missing")} · Opportunity ${escapeHtml(item.opportunity_score ?? "Missing")} · Completeness ${escapeHtml(item.data_completeness)}% · ${escapeHtml(item.confidence)}</li>`).join("");
  return `<div class="detail-item detail-wide radar-sources"><dt>Evidence / Score History</dt><dd><p>${escapeHtml(row.why_changed || "Missing")}</p><ul>${history || "<li>No prior snapshot.</li>"}</ul></dd></div>`;
}

function renderAiRadar(rows) {
  document.getElementById("ai-radar").innerHTML = rows.map((row) => `<details class="radar-item ai-radar-item"><summary>
      <span class="radar-name"><strong>${escapeHtml(row.trend)}</strong><small>Technology trend</small></span>${renderScore(row.trend_strength, "Trend Strength")}
      <span class="direction"><i aria-hidden="true">${row.direction === "Contradicting" ? "↘" : row.direction === "Mixed" ? "↔" : "↗"}</i>${escapeHtml(row.direction)}</span><span><b class="stage ${stageClass(row.adoption_stage || "missing")}">${escapeHtml(row.stage)}</b></span>
      <span class="radar-copy">${escapeHtml(row.why_now)}</span><span class="beneficiaries">${escapeHtml(row.potential_beneficiaries)}</span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid">
      ${detailItem("What It Means", row.what_it_means)}${detailItem("Key Intelligence", row.key_intelligence)}${detailItem("Demand Drivers", row.demand_drivers)}${detailItem("Current Bottleneck", row.current_bottleneck)}${detailItem("Next Likely Bottleneck", row.next_likely_bottleneck)}
      ${detailItem("Beneficiaries", row.beneficiaries)}${detailItem("Market Expectation / Priced In", row.market_expectation, true)}
      ${detailItem("Risks / Invalidation", row.risks, true)}${detailItem("What to Watch Next", row.watch_next)}
      ${renderAiFactorBreakdown(row)}${renderAiHorizons(row.horizons)}${renderAiEvidence("Confirming Evidence", row.confirming_evidence)}${renderAiEvidence("Mixed Evidence", row.mixed_evidence)}${renderAiEvidence("Contradicting Evidence", row.contradicting_evidence)}${renderAiBeneficiaries(row.beneficiary_records)}${renderAiHistory(row)}
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
  return `<span class="news-score"><small>${escapeHtml(label)}</small><strong>${score === null ? "Missing" : escapeHtml(score)}</strong>${score === null ? "" : "<i>/100</i>"}</span>`;
}

function companyTickerLabel(row = {}) {
  const company = row.company || "Company missing";
  const ticker = row.ticker && row.ticker !== "Missing" ? ` · ${row.ticker}` : "";
  return `${company}${ticker}`;
}

function relatedTickerLabel(row = {}) {
  return Array.isArray(row.related_tickers) && row.related_tickers.length ? `Related: ${row.related_tickers.join(", ")}` : "";
}

function renderNewsCard(story) {
  const sourceUrl = safeSourceUrl(story.source_link);
  const trendTags = (story.affected_trends || []).map((trend) => `<span>${escapeHtml(trend)}</span>`).join("");
  const evidenceSources = (story.evidence_sources || []).map((item) => {
    const url = safeSourceUrl(item.url);
    const label = `${item.primary ? "Primary" : "Corroborating"}: ${item.source}${item.date ? ` · ${formatNewsDate(item.date)}` : ""}`;
    return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>` : escapeHtml(label)}</li>`;
  }).join("");
  return `<article class="top-news-card">
    <div class="news-card-meta"><span>${escapeHtml(formatNewsDate(story.published_at))}</span><span>${escapeHtml(story.source || "Source missing")}</span><b class="news-status ${stageClass(story.status)}">${escapeHtml(story.status || "Status missing")}</b></div>
    <div class="news-card-meta"><span>${escapeHtml(companyTickerLabel(story))}</span>${relatedTickerLabel(story) ? `<span>${escapeHtml(relatedTickerLabel(story))}</span>` : ""}</div>
    <h3>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(story.headline)}</a>` : escapeHtml(story.headline)}</h3>
    <div class="news-score-row">${newsScore("Importance", story.news_importance_score)}</div>
    <div class="news-why"><strong>What changed</strong><p>${escapeHtml(story.new_information || "Missing")}</p></div>
    <dl class="news-detail-grid"><div><dt>Event type</dt><dd>${escapeHtml(story.event_type || "Missing")}</dd></div><div><dt>Direction</dt><dd>${escapeHtml(story.direction || "Missing")}</dd></div><div><dt>Affected trends</dt><dd class="news-trend-tags">${trendTags || "Missing"}</dd></div><div><dt>Relevant impacts</dt><dd>${escapeHtml(story.impact_chain || "Missing")}</dd></div></dl>
    ${evidenceSources ? `<div class="news-evidence-sources"><strong>Sources &amp; evidence</strong><ul>${evidenceSources}</ul></div>` : ""}
    ${sourceUrl ? `<a class="news-source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read source <span aria-hidden="true">↗</span></a>` : `<span class="news-source-link missing-value">Source link missing</span>`}
  </article>`;
}

function renderTopNews(section = {}) {
  const stories = Array.isArray(section.stories) ? section.stories : [];
  const archive = Array.isArray(section.important_news_archive) ? section.important_news_archive : [];
  setText("ai-news-selection-status", section.selection_status || "AI Technology News V1 active");
  setText("ai-news-archive-count", archive.length);
  document.getElementById("ai-top-news").innerHTML = stories.map(renderNewsCard).join("") || `<p class="loading-state">No source-qualified AI or technology stories are available yet. The daily updater will preserve prior selections when feeds are unavailable.</p>`;
  document.getElementById("ai-news-archive").innerHTML = archive.map((story) => {
    const url = safeSourceUrl(story.source_link);
    return `<article class="news-archive-item"><div><span>${escapeHtml(formatNewsDate(story.published_at))} · ${escapeHtml(companyTickerLabel(story))} · ${escapeHtml(story.event_type || "Event type missing")} · ${escapeHtml(story.direction || "Direction missing")}</span>
      <h4>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(story.headline)}</a>` : escapeHtml(story.headline)}</h4></div>
      <span class="news-status ${stageClass(story.status)}">${escapeHtml(story.status || "Status missing")}</span><strong>${escapeHtml(story.news_importance_score)}<small>/100</small></strong></article>`;
  }).join("") || `<p class="loading-state">The archive will populate as important stories rotate out of Top Investment News.</p>`;
}

function renderBiotechNewsCard(story) {
  const sourceUrl = safeSourceUrl(story.source_link);
  const factorTags = (story.affected_radar_factors || []).map((factor) => `<span>${escapeHtml(factor)}</span>`).join("");
  const subsectorTags = (story.subsectors || []).map((subsector) => `<span>${escapeHtml(subsector)}</span>`).join("");
  const evidenceSources = (story.evidence_sources || []).map((item) => {
    const url = safeSourceUrl(item.url);
    const label = `${item.primary ? "Primary" : "Corroborating"}: ${item.source}${item.date ? ` · ${formatNewsDate(item.date)}` : ""}`;
    return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>` : escapeHtml(label)}</li>`;
  }).join("");
  const companyLabel = companyTickerLabel(story);
  return `<article class="top-news-card biotech-news-card">
    <div class="news-card-meta"><span>${escapeHtml(formatNewsDate(story.published_at))}</span><span>${escapeHtml(story.source || "Source missing")}</span><b class="news-status ${stageClass(story.status)}">${escapeHtml(story.status || "Status missing")}</b></div>
    <div class="news-card-meta"><span>${escapeHtml(companyLabel)}</span><span>${escapeHtml(story.drug_program || "Program missing")}</span>${relatedTickerLabel(story) ? `<span>${escapeHtml(relatedTickerLabel(story))}</span>` : ""}</div>
    <h3>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(story.headline)}</a>` : escapeHtml(story.headline)}</h3>
    <div class="news-score-row">${newsScore("Importance", story.news_importance_score)}</div>
    <div class="news-why"><strong>What changed</strong><p>${escapeHtml(story.new_information || "Missing")}</p></div>
    <dl class="news-detail-grid"><div><dt>Event type</dt><dd>${escapeHtml(story.event_type || "Missing")}</dd></div><div><dt>Development stage / evidence level</dt><dd>${escapeHtml(story.development_stage || "Missing")}</dd></div><div><dt>Indication</dt><dd>${escapeHtml(story.indication || "Missing")}</dd></div><div><dt>Previous → new state</dt><dd>${escapeHtml(story.previous_state || "Missing")} → ${escapeHtml(story.new_state || "Missing")}</dd></div><div><dt>Direction</dt><dd>${escapeHtml(story.direction || "Missing")}</dd></div><div><dt>Affected Radar factors</dt><dd class="news-trend-tags">${factorTags || "Missing"}</dd></div><div><dt>Subsector</dt><dd class="news-trend-tags">${subsectorTags || "Missing"}</dd></div></dl>
    ${evidenceSources ? `<div class="news-evidence-sources"><strong>Sources &amp; evidence</strong><ul>${evidenceSources}</ul></div>` : ""}
    ${sourceUrl ? `<a class="news-source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read source <span aria-hidden="true">↗</span></a>` : `<span class="news-source-link missing-value">Source link missing</span>`}
  </article>`;
}

function renderBiotechNews(section = {}) {
  const stories = Array.isArray(section.stories) ? section.stories : [];
  const archive = Array.isArray(section.important_news_archive) ? section.important_news_archive : [];
  setText("biotech-news-selection-status", section.selection_status || "Biotech News V1 active");
  setText("biotech-news-archive-count", archive.length);
  document.getElementById("biotech-top-news").innerHTML = stories.map(renderBiotechNewsCard).join("") || `<p class="loading-state">No biotech events currently meet the prominent-news threshold. Qualified events remain available in Evidence History.</p>`;
  document.getElementById("biotech-news-archive").innerHTML = archive.map((story) => {
    const url = safeSourceUrl(story.source_link);
    const company = companyTickerLabel(story);
    return `<article class="news-archive-item"><div><span>${escapeHtml(formatNewsDate(story.published_at))} · ${escapeHtml(company)} · ${escapeHtml(story.event_type || "Event type missing")} · ${escapeHtml(story.direction || "Direction missing")}</span>
      <h4>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(story.headline)}</a>` : escapeHtml(story.headline)}</h4></div>
      <span class="news-status ${stageClass(story.status)}">${escapeHtml(story.status || "Status missing")}</span><strong>${escapeHtml(story.news_importance_score)}<small>/100</small></strong></article>`;
  }).join("") || `<p class="loading-state">Evidence History will populate when events score 65–79 or rotate out of prominent news.</p>`;
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
      <span class="radar-name"><strong>${escapeHtml(row.company)}</strong><small>${escapeHtml(row.ticker)} · ${escapeHtml(row.program)} · ${escapeHtml(row.indication)} · ${escapeHtml(row.catalyst)}</small></span>${renderScore(row.opportunity_score, "Opportunity Score")}
      <span class="timing">${escapeHtml(row.expected_timing)}</span><span><b class="stage ${stageClass(row.stage)}">${escapeHtml(row.stage)}</b></span>
      <span class="radar-copy">${escapeHtml(row.why_important)}</span><span class="status-badge ${stageClass(row.opportunity_status)}">${escapeHtml(row.opportunity_status)}</span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid biotech-details">
      ${detailItem("Company → Program → Indication → Catalyst", `${row.company} (${row.ticker}) → ${row.program} → ${row.indication} → ${row.catalyst}`)}
      ${detailItem("Clinical Evidence", row.clinical_evidence, String(row.clinical_evidence).startsWith("Missing"))}${detailItem("Upcoming Catalyst", row.upcoming_catalyst)}${detailItem("Previous Trial Results", row.previous_results, String(row.previous_results).startsWith("Missing"))}
      ${detailItem("FDA / Regulatory Status", row.regulatory_status)}${detailItem("Commercial Potential", row.commercial_potential)}
      ${detailItem("Market Expectation / Priced In", row.market_expectation, String(row.market_expectation).startsWith("Missing"))}${detailItem("Positioning / Short Interest", row.positioning, String(row.positioning).startsWith("Missing"))}
      ${detailItem("Risks", row.risks)}${detailItem("What to Watch Next", row.watch_next)}
      ${detailItem("Scientific Evidence", row.scientific_evidence_score === null ? "Missing" : `${row.scientific_evidence_score} / 30`)}${detailItem("Catalyst Impact / Company Sensitivity", `${row.catalyst_impact_score} / 25. ${row.company_sensitivity}`)}${detailItem("Expectation Gap", row.expectation_gap_score === null ? "Missing" : `${row.expectation_gap_score} / 20`)}
      ${detailItem("Binary Risk", `${row.binary_risk}. ${row.binary_risk_rationale}`)}${detailItem("Data Completeness / Confidence", `${row.data_completeness}% / ${row.confidence}`)}${detailItem("Evidence Gate", `${row.evidence_gate.passed ? "Passed" : "Not passed"}. ${row.evidence_gate.rule}`)}
      ${detailItem("Evidence Integrity Gate", `${row.evidence_integrity_gate.concern_identified ? "Concern identified; confidence capped." : "No explicit integrity concern identified in connected evidence."} ${row.evidence_integrity_gate.rule}`)}
      ${renderScoreBreakdown(row.score_components, row.data_completeness)}${renderSources(row.sources, row.score_as_of)}
      ${renderBiotechEvidenceGroup("Confirming Evidence", row.confirming_evidence)}${renderBiotechEvidenceGroup("Mixed Evidence", row.mixed_evidence)}${renderBiotechEvidenceGroup("Contradicting Evidence", row.contradicting_evidence)}${renderBiotechHistory(row)}
    </dl></details>`).join("") || `<p class="loading-state">No biotech opportunities are available.</p>`;
}

function renderOpportunities(targetId, rows = []) {
  document.getElementById(targetId).innerHTML = rows.map((row) => `<article class="opportunity-card"><div class="opportunity-rank">${escapeHtml(row.rank)}</div>
    <div><div class="opportunity-top"><h4>${escapeHtml(companyTickerLabel(row))}</h4><span class="risk risk-${String(row.risk).toLowerCase()}">${escapeHtml(row.risk)} risk</span></div>
    <p>${escapeHtml(row.thesis)}</p><dl><div><dt>Catalyst</dt><dd>${escapeHtml(row.catalyst)}</dd></div><div><dt>Long-term</dt><dd>${escapeHtml(row.opportunity)}</dd></div></dl></div></article>`).join("") || `<p class="loading-state">No opportunities are available.</p>`;
}

function renderWatchlist(data) {
  const rows = [...(data.watchlists?.ai || []).map((row) => ({ ...row, category: "AI" })), ...(data.watchlists?.biotech || []).map((row) => ({ ...row, category: "Biotech" }))];
  setText("watchlist-count", rows.length);
  document.getElementById("my-watchlist").innerHTML = rows.map((row) => `<article class="stock-row"><div><span class="stock-category">${escapeHtml(row.category)}</span><strong>${escapeHtml(row.ticker)}</strong><small>${escapeHtml(row.company)}</small></div><p>${escapeHtml(row.why)}</p><div><span>Next catalyst</span><strong>${escapeHtml(row.catalyst)}</strong></div><span class="risk risk-${String(row.risk).toLowerCase()}">${escapeHtml(row.risk)} risk</span></article>`).join("");
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

function renderDashboard(data) {
  if (!data || typeof data !== "object") throw new Error("Dashboard JSON is not an object.");
  const updated = new Date(data.updated_at);
  setText("last-updated", Number.isNaN(updated.valueOf()) ? data.updated_at : updated.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }));
  setText("ai-summary", data.summaries && data.summaries.ai); setText("biotech-summary", data.summaries && data.summaries.biotech); setText("market-movers", data.summaries && data.summaries.market_movers);
  renderSafely(() => renderTopNews(data.top_investment_news && data.top_investment_news.ai_technology), "ai-top-news");
  renderSafely(() => renderBiotechNews(data.top_investment_news && data.top_investment_news.biotech_healthcare), "biotech-top-news");
  renderSafely(() => renderAiRadar(aiRadarRows(data)), "ai-radar");
  renderSafely(() => renderBiotechRadar(biotechRadarRows(data)), "biotech-radar");
  renderSafely(() => renderOpportunities("ai-opportunities", data.monthly_picks && data.monthly_picks.ai), "ai-opportunities");
  renderSafely(() => renderOpportunities("biotech-opportunities", data.monthly_picks && data.monthly_picks.biotech), "biotech-opportunities");
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
