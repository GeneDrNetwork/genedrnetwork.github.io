const DATA_URL = "../data/news-dashboard.json";

const escapeHtml = (value = "") => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const setText = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value || "No update available."; };

const PLACEHOLDER_SCORES = [88, 84, 81, 78, 75, 72, 69, 66, 63, 60];
const stageFor = (score) => score >= 85 ? "Hot" : score >= 76 ? "Heating Up" : score >= 66 ? "Emerging" : "Cooling";
const stageClass = (stage) => stage.toLowerCase().replaceAll(" ", "-");
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
  const leaders = new Map((data.biotech?.leaders || []).map((item) => [item.company, item]));
  const tickers = new Map((data.watchlists?.biotech || []).map((item) => [item.company, item.ticker]));
  return (data.biotech?.emerging || []).map((item, index) => {
    const score = PLACEHOLDER_SCORES[index] || Math.max(50, 88 - index * 3);
    const leader = leaders.get(item.company);
    return {
      ticker: tickers.get(item.company) || leader?.ticker || "—", company: item.company, catalyst: item.catalysts,
      catalyst_score: score, expected_timing: "Timing pending", stage: stageFor(score), why_important: item.lead_programs,
      opportunity_status: index < 3 ? "Priority watch" : "Monitoring", clinical_evidence: `Lead programs: ${item.lead_programs}`,
      upcoming_catalyst: item.catalysts, previous_results: "Trial-history analysis will be supplied by the future Radar Engine.",
      regulatory_status: "The existing FDA feed continues to update daily; company-level mapping is pending.",
      commercial_potential: `${item.technology} platform; ${item.market_cap || "market-cap context pending"}.`,
      market_expectation: "Pricing analysis will be supplied by the future Radar Engine.",
      positioning: "Positioning and short-interest data are not yet connected.",
      risks: `${item.risk || "Unscored"} research risk; detailed invalidation analysis pending.`, watch_next: item.catalysts
    };
  });
}

function renderScore(score, label) {
  const safeScore = Math.max(0, Math.min(100, Number(score) || 0));
  return `<div class="score" aria-label="${escapeHtml(label)} ${safeScore} out of 100"><strong>${safeScore}</strong><span>/100</span><i><b style="width:${safeScore}%"></b></i></div>`;
}

function renderAiRadar(rows) {
  document.getElementById("ai-radar").innerHTML = rows.map((row) => `<details class="radar-item ai-radar-item"><summary>
      <span class="radar-name"><strong>${escapeHtml(row.trend)}</strong><small>Technology trend</small></span>${renderScore(row.heat_score, "Heat score")}
      <span class="direction"><i aria-hidden="true">↗</i>${escapeHtml(row.direction)}</span><span><b class="stage ${stageClass(row.stage)}">${escapeHtml(row.stage)}</b></span>
      <span class="radar-copy">${escapeHtml(row.why_now)}</span><span class="beneficiaries">${escapeHtml(row.potential_beneficiaries)}</span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid">
      ${detailItem("Key Intelligence", row.key_intelligence)}${detailItem("Demand Drivers", row.demand_drivers)}${detailItem("Bottleneck", row.bottleneck, true)}
      ${detailItem("Beneficiaries", row.beneficiaries)}${detailItem("Market Expectation / Priced In", row.market_expectation, true)}
      ${detailItem("Risks / Invalidation", row.risks, true)}${detailItem("What to Watch Next", row.watch_next)}
    </dl></details>`).join("") || `<p class="loading-state">No AI trends are available.</p>`;
}

function renderBiotechRadar(rows) {
  document.getElementById("biotech-radar").innerHTML = rows.map((row) => `<details class="radar-item biotech-radar-item"><summary>
      <span class="radar-name"><strong>${escapeHtml(row.company)}</strong><small>${escapeHtml(row.ticker)} · ${escapeHtml(row.catalyst)}</small></span>${renderScore(row.catalyst_score, "Catalyst score")}
      <span class="timing">${escapeHtml(row.expected_timing)}</span><span><b class="stage ${stageClass(row.stage)}">${escapeHtml(row.stage)}</b></span>
      <span class="radar-copy">${escapeHtml(row.why_important)}</span><span class="status-badge">${escapeHtml(row.opportunity_status)}</span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid biotech-details">
      ${detailItem("Clinical Evidence", row.clinical_evidence)}${detailItem("Upcoming Catalyst", row.upcoming_catalyst)}${detailItem("Previous Trial Results", row.previous_results, true)}
      ${detailItem("FDA / Regulatory Status", row.regulatory_status, true)}${detailItem("Commercial Potential", row.commercial_potential)}
      ${detailItem("Market Expectation / Priced In", row.market_expectation, true)}${detailItem("Positioning / Short Interest", row.positioning, true)}
      ${detailItem("Risks", row.risks)}${detailItem("What to Watch Next", row.watch_next)}
    </dl></details>`).join("") || `<p class="loading-state">No biotech opportunities are available.</p>`;
}

function renderOpportunities(targetId, rows = []) {
  document.getElementById(targetId).innerHTML = rows.map((row) => `<article class="opportunity-card"><div class="opportunity-rank">${escapeHtml(row.rank)}</div>
    <div><div class="opportunity-top"><h4>${escapeHtml(row.company)}</h4><span class="risk risk-${String(row.risk).toLowerCase()}">${escapeHtml(row.risk)} risk</span></div>
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

function renderDashboard(data) {
  const updated = new Date(data.updated_at);
  setText("last-updated", Number.isNaN(updated.valueOf()) ? data.updated_at : updated.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }));
  setText("ai-summary", data.summaries?.ai); setText("biotech-summary", data.summaries?.biotech); setText("market-movers", data.summaries?.market_movers);
  renderAiRadar(aiRadarRows(data)); renderBiotechRadar(biotechRadarRows(data));
  renderOpportunities("ai-opportunities", data.monthly_picks?.ai); renderOpportunities("biotech-opportunities", data.monthly_picks?.biotech);
  renderWatchlist(data); renderMarkets(data.markets);
}

initTabs();
fetch(DATA_URL, { cache: "no-store" }).then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); }).then(renderDashboard).catch((error) => {
  setText("last-updated", "Dashboard temporarily unavailable");
  document.querySelectorAll(".loading-state").forEach((element) => { element.textContent = "The daily data feed could not be loaded. Please try again shortly."; });
  console.error("GeneDr Investment Intelligence dashboard:", error);
});
