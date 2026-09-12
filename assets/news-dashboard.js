const scriptSource = document.currentScript && document.currentScript.src ? document.currentScript.src : document.baseURI;
const dataUrl = new URL("../data/news-dashboard.json", scriptSource);
dataUrl.searchParams.set("_", Date.now().toString());
const DATA_URL = dataUrl.href;

const escapeHtml = (value = "") => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#039;");
const setText = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value ?? "No update available."; };
const formatMarketDataThrough = (value) => {
  const text = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return text || "Unavailable";
  const date = new Date(`${text}T00:00:00Z`);
  return Number.isNaN(date.valueOf()) ? text : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(date);
};
let sharedMarketSecurities = {};
let currentDashboardData = null;
let watchlistState = null;
let currentAutomaticWatchlistTickers = new Set();
let positionState = null;
let pendingOrderState = null;
const WATCHLIST_STORAGE_KEY = "genedr-investment-watchlist-v2";
const LEGACY_WATCHLIST_STORAGE_KEY = "genedr-investment-watchlist-v1";
const POSITION_STORAGE_KEY = "genedr-investment-positions-v1";
const PENDING_ORDER_STORAGE_KEY = "genedr-investment-pending-orders-v1";

function normalizedTicker(value) {
  return String(value || "").trim().toUpperCase();
}

function yahooFinanceTicker(value) {
  const ticker = normalizedTicker(value);
  return ticker && !["PRIVATE", "N/A", "MISSING"].includes(ticker) ? ticker : "";
}

function yahooFinanceUrl(value) {
  const ticker = yahooFinanceTicker(value);
  return ticker ? `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}/` : "";
}

function tickerLink(value, label = null) {
  const ticker = yahooFinanceTicker(value);
  const text = label === null ? ticker || "Ticker missing" : String(label);
  if (!ticker) return escapeHtml(text);
  return `<a class="ticker-link" href="${escapeHtml(yahooFinanceUrl(ticker))}" target="_blank" rel="noopener noreferrer" aria-label="Open ${escapeHtml(ticker)} on Yahoo Finance">${escapeHtml(text)}</a>`;
}

function writeWatchlistState() {
  try { localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(watchlistState)); } catch (_) { /* Browser storage may be disabled. */ }
}

function initializePositionState() {
  if (positionState) return positionState;
  try {
    const saved = JSON.parse(localStorage.getItem(POSITION_STORAGE_KEY) || "null");
    if (saved?.version === 1 && Array.isArray(saved.positions)) positionState = saved;
  } catch (_) { positionState = null; }
  if (!positionState) positionState = { version: 1, positions: [] };
  return positionState;
}

function writePositionState() {
  try { localStorage.setItem(POSITION_STORAGE_KEY, JSON.stringify(positionState)); } catch (_) { /* Browser storage may be disabled. */ }
}

function initializePendingOrderState() {
  if (pendingOrderState) return pendingOrderState;
  try {
    const saved = JSON.parse(localStorage.getItem(PENDING_ORDER_STORAGE_KEY) || "null");
    if (saved?.version === 1 && Array.isArray(saved.orders)) pendingOrderState = saved;
  } catch (_) { pendingOrderState = null; }
  if (!pendingOrderState) pendingOrderState = { version: 1, orders: [] };
  return pendingOrderState;
}

function writePendingOrderState() {
  try { localStorage.setItem(PENDING_ORDER_STORAGE_KEY, JSON.stringify(pendingOrderState)); } catch (_) { /* Browser storage may be disabled. */ }
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
  const productionItems = data?.manual_watchlist?.items || [];
  const productionTickers = new Set(productionItems.map((item) => normalizedTicker(item.ticker)).filter(Boolean));
  const retainedManualItems = watchlistState.manual_items.filter((item) =>
    !item.repository_managed || productionTickers.has(normalizedTicker(item.ticker)));
  let productionSynchronized = retainedManualItems.length !== watchlistState.manual_items.length;
  watchlistState.manual_items = retainedManualItems;
  for (const productionItem of productionItems) {
    const ticker = normalizedTicker(productionItem.ticker);
    if (!ticker) continue;
    const existing = watchlistState.manual_items.find((item) => normalizedTicker(item.ticker) === ticker);
    const synchronized = { ticker, company: productionItem.company || existing?.company || ticker,
      domain: productionItem.domain || existing?.domain || "ai",
      reason: existing?.reason || "Repository-selected for active technical monitoring.",
      validation_status: productionItem.data_status === "current" ? "validated-shared-market-data" : "pending-market-data",
      repository_managed: true, added_at: existing?.added_at || null };
    if (existing) Object.assign(existing, synchronized);
    else watchlistState.manual_items.push(synchronized);
    productionSynchronized = true;
  }
  const seenManualTickers = new Set();
  let normalizedManualStorage = false;
  const deduplicatedManualItems = watchlistState.manual_items.filter((item) => {
    const ticker = normalizedTicker(item.ticker);
    if (!ticker || seenManualTickers.has(ticker)) { normalizedManualStorage = true; return false; }
    seenManualTickers.add(ticker);
    if (item.ticker !== ticker) normalizedManualStorage = true;
    item.ticker = ticker;
    return true;
  });
  if (productionSynchronized || normalizedManualStorage || deduplicatedManualItems.length !== watchlistState.manual_items.length) {
    watchlistState.manual_items = deduplicatedManualItems;
    writeWatchlistState();
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
const detailItemMarkup = (label, markup, placeholder = false) => `<div class="detail-item${placeholder ? " detail-placeholder" : ""}"><dt>${escapeHtml(label)}</dt><dd>${markup}</dd></div>`;

function renderNumberedMessages(targetId, rows = []) {
  const target = document.getElementById(targetId);
  if (!target) return;
  target.innerHTML = rows.map((row) => `<li>${escapeHtml(row)}</li>`).join("") || `<li>No evidence-supported conclusion is available.</li>`;
}

function renderDashboardCommentary(commentary = {}) {
  const aiNews = commentary.news?.ai_technology || commentary.news || {};
  const biotechNews = commentary.news?.biotech_healthcare || commentary.news || {};
  const aiRadar = commentary.radar?.ai_technology || {};
  const biotechRadar = commentary.radar?.biotech_healthcare || {};
  const cryptoRadar = commentary.radar?.crypto_stablecoin || {};
  renderNumberedMessages("news-takeaways", aiNews.take_home_messages);
  renderNumberedMessages("biotech-news-takeaways", biotechNews.take_home_messages);
  setText("ai-radar-summary-copy", aiRadar.summary);
  renderNumberedMessages("ai-radar-takeaways", aiRadar.take_home_messages);
  setText("biotech-radar-summary-copy", biotechRadar.summary);
  renderNumberedMessages("biotech-radar-takeaways", biotechRadar.take_home_messages);
  setText("crypto-radar-summary-copy", cryptoRadar.summary);
  renderNumberedMessages("crypto-radar-takeaways", cryptoRadar.take_home_messages);
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

function cryptoRadarRows(data) {
  if (Array.isArray(data.radar?.crypto)) return data.radar.crypto;
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

function tickerPriceMarkup(ticker, snapshot = null) {
  const normalized = yahooFinanceTicker(ticker);
  if (!normalized) return tickerLink(ticker);
  const price = currentPriceLabel(normalized, snapshot);
  return `${tickerLink(normalized)}${price ? ` ${escapeHtml(price)}` : ""}`;
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
  const rows = evidence.map((item) => `<li><strong>${companyTickerMarkup(item)}</strong> · ${escapeHtml(item.age_band || "Age missing")} · ${escapeHtml(formatNewsDate(item.event_date))}<br>${escapeHtml(item.new_information || "Evidence detail missing")}</li>`).join("");
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
  const items = rows.map((item) => `<li><strong>${companyTickerMarkup(item)}</strong> — ${escapeHtml(item.opportunity_stage || "Stage unavailable")} · ${escapeHtml(item.category)} — relevance ${escapeHtml(item.beneficiary_relevance)}/100 · completeness ${escapeHtml(item.data_completeness)}%
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

function conciseRadarText(value, limit = 220) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  if (!clean) return "Evidence detail is unavailable.";
  const sentence = clean.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim() || clean;
  return sentence.length <= limit ? sentence : `${sentence.slice(0, limit - 1).replace(/\s+\S*$/, "")}…`;
}

function aiStockRadarRows(trends = []) {
  const rows = [];
  const seen = new Set();
  for (const trend of trends) {
    for (const beneficiary of trend.beneficiary_records || []) {
      const ticker = normalizedTicker(beneficiary.ticker);
      if (!ticker || ["PRIVATE", "N/A", "MISSING"].includes(ticker) || beneficiary.listing_status !== "Public") continue;
      const key = `${trend.trend}|${ticker}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const thesis = beneficiary.thesis_evidence?.[0]?.basis;
      const confirmation = beneficiary.confirmation_evidence?.[0]?.basis;
      const companyNarrative = beneficiary.company_narrative || {};
      const category = `${trend.trend} · ${beneficiary.category || "Beneficiary"}`;
      const whySelected = conciseRadarText(companyNarrative.why_selected || thesis || confirmation || `${beneficiary.company} is mapped as a ${beneficiary.category || "potential"} beneficiary of ${trend.trend} because the current industry-chain evidence connects it to this opportunity.`);
      const riskUnproven = companyNarrative.risk_unproven || (beneficiary.confirmation_missing
        ? "Commercial confirmation remains incomplete; orders, customer adoption, guidance, or revenue evidence is still unproven."
        : "Connected confirmation exists, but durability, revenue sensitivity, execution, and valuation still require monitoring.");
      rows.push({ trend, beneficiary, ticker, category,
        opportunity_score: beneficiary.bottleneck_opportunity_score,
        multibagger_score: beneficiary.multibagger_potential_score,
        price_discovery_stage: beneficiary.price_discovery_stage || "Emerging",
        already_priced_in: beneficiary.already_priced_in || "NO",
        entry_stage: beneficiary.entry_stage?.stage || "Unavailable",
        why_selected: whySelected, risk_unproven: riskUnproven });
    }
  }
  return rows.sort((a, b) => (b.beneficiary.radar_rank_score ?? -1) - (a.beneficiary.radar_rank_score ?? -1)
    || (b.opportunity_score ?? -1) - (a.opportunity_score ?? -1)
    || a.ticker.localeCompare(b.ticker));
}

function renderEarlyRadarBreakdown(label, components = [], completeness) {
  const rows = components.map((component) => `<li class="${component.score === null || component.score === undefined ? "score-component-missing" : ""}">
    <span>${escapeHtml(component.label)}</span><strong>${component.score === null || component.score === undefined ? "Missing" : `${escapeHtml(component.score)} / ${escapeHtml(component.weight)}`}</strong></li>`).join("");
  return `<div class="detail-item detail-wide score-breakdown"><dt>${escapeHtml(label)}</dt><dd><ul>${rows || "<li>Score evidence is unavailable.</li>"}</ul><p>Data completeness: ${escapeHtml(completeness ?? "Missing")}% · missing inputs are excluded rather than scored as zero.</p></dd></div>`;
}

function decisionNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function hasValidCompanyCatalyst(row = {}) {
  return row.catalyst_validation?.valid === true || row.catalyst_evidence?.valid === true ||
    (row.catalyst?.credible === true && row.catalyst?.status === "COMPANY-SPECIFIC CATALYST");
}

function catalystStatus(row = {}) {
  return hasValidCompanyCatalyst(row) ? "COMPANY-SPECIFIC CATALYST" : "THEME ONLY / UNVERIFIED";
}

function aiRadarAction(row = {}) {
  const stage = String(row.entry_stage?.stage || row.entry_stage || "Unavailable");
  const pricedIn = String(row.already_priced_in || "NO").toUpperCase();
  const discovery = String(row.price_discovery_stage || "");
  const opportunity = decisionNumber(row.bottleneck_opportunity_score ?? row.opportunity_score);
  const multibagger = decisionNumber(row.multibagger_potential_score);
  const readiness = decisionNumber(row.entry_stage?.entry_timing_score);
  if ((opportunity !== null && opportunity < 50) || (multibagger !== null && multibagger < 45)) return "PASS";
  if (stage === "Extended" || pricedIn === "YES") return "DO NOT CHASE";
  if (!hasValidCompanyCatalyst(row)) return "WATCH / WAIT FOR VALID CATALYST";
  if (discovery === "Already Ran" || (pricedIn === "PARTIALLY" && stage === "Breakout")) return "WAIT FOR PULLBACK";
  if (stage === "Breakout") return opportunity !== null && opportunity >= 65 ? "BUY" : "WATCH";
  if (stage === "Entry Zone") return opportunity === null || multibagger === null ? "WATCH"
    : pricedIn === "PARTIALLY" || multibagger < 65 ? "SCALE IN" : "BUY";
  if (stage === "Reversal") return pricedIn === "NO" && opportunity !== null && opportunity >= 65 && (readiness === null || readiness >= 55) ? "SCALE IN" : "WATCH";
  if (stage === "Bottoming") return "WATCH";
  return stage === "Falling" ? "WAIT" : "WATCH";
}

function biotechRadarAction(row = {}) {
  const stage = String(row.entry_stage?.stage || "Unavailable");
  const pricedIn = String(row.already_priced_in || "NO").toUpperCase();
  const score = decisionNumber(row.biotech_opportunity_score ?? row.opportunity_score);
  const risk = String(row.binary_risk || "Missing").toLowerCase();
  const catalyst = `${row.catalyst || ""} ${row.upcoming_catalyst || ""} ${row.expected_timing || ""}`.toLowerCase();
  const runway = String(row.cash_runway_dilution || "Missing").toLowerCase();
  const probability = String(row.probability_of_success || "Missing").toLowerCase();
  const evidencePassed = row.evidence_gate?.passed === true;
  const integrityConcern = row.evidence_integrity_gate?.concern_identified === true;
  const catalystAvailable = catalyst.trim() && !/missing|unavailable|not connected/.test(catalyst);
  const constrained = /high|extreme/.test(risk) || integrityConcern || /dilution|missing|insufficient/.test(runway) || /low|missing|insufficient/.test(probability);
  if (score !== null && score < 50) return "PASS";
  if (!evidencePassed || integrityConcern) return catalystAvailable ? "WAIT FOR CATALYST" : "PASS";
  if (stage === "Extended" || pricedIn === "YES") return "WAIT FOR PULLBACK";
  if (!hasValidCompanyCatalyst(row)) return "WATCH / WAIT FOR VALID CATALYST";
  if (stage === "Entry Zone" || stage === "Breakout") return constrained ? "SMALL POSITION" : "BUY";
  if (stage === "Reversal") return constrained ? "SMALL POSITION" : "SCALE IN";
  if (stage === "Bottoming" || stage === "Falling") return catalystAvailable ? "WAIT FOR CATALYST" : "WATCH";
  return "WATCH";
}

function cryptoRadarAction(row = {}) {
  const stage = String(row.entry_stage?.stage || "Unavailable");
  const pricedIn = String(row.already_priced_in || "NO").toUpperCase();
  const discovery = String(row.price_discovery_stage || "");
  const opportunity = decisionNumber(row.crypto_opportunity_score);
  const multibagger = decisionNumber(row.multibagger_potential_score);
  const btcRelative = decisionNumber(row.market_data?.relative_strength?.btc?.one_month);
  const isBitcoin = normalizedTicker(row.ticker) === "BTC-USD";
  if ((opportunity !== null && opportunity < 50) || (multibagger !== null && multibagger < 45)) return "PASS";
  if (stage === "Extended" || pricedIn === "YES") return "DO NOT CHASE";
  if (discovery === "Already Ran" || (pricedIn === "PARTIALLY" && stage === "Breakout")) return "WAIT FOR PULLBACK";
  if (stage === "Breakout") return isBitcoin || (btcRelative !== null && btcRelative >= 0) ? "BUY" : "WATCH";
  if (stage === "Entry Zone") return opportunity === null || multibagger === null ? "WATCH"
    : opportunity >= 70 && multibagger >= 65 ? "BUY" : "SCALE IN";
  if (stage === "Reversal") return isBitcoin || (btcRelative !== null && btcRelative >= 0) ? "SCALE IN" : "WATCH";
  if (stage === "Bottoming") return "WATCH";
  return stage === "Falling" ? "WAIT" : "WATCH";
}

function renderAiRadar(rows, targetId = "ai-radar") {
  const stockRows = aiStockRadarRows(rows);
  document.getElementById(targetId).innerHTML = stockRows.map(({ trend, beneficiary, ticker, category, opportunity_score, multibagger_score, price_discovery_stage, already_priced_in, entry_stage, why_selected, risk_unproven }) => {
    const action = aiRadarAction(beneficiary);
    const companyNarrative = beneficiary.company_narrative || {};
    return `<details class="radar-item ai-stock-radar-item"><summary>
      <span class="ai-stock-identity"><strong>${tickerLink(ticker)}</strong><small>${escapeHtml(beneficiary.company)} · ${escapeHtml(currentPriceLabel(ticker, beneficiary.market_data) || "Price unavailable")}</small></span>
      ${renderScore(opportunity_score, "Bottleneck Opportunity")}${renderScore(multibagger_score, "Multibagger Potential")}
      <span><b class="radar-stage-pill">${escapeHtml(price_discovery_stage)}</b></span><span><b class="radar-stage-pill priced-${classKey(already_priced_in)}">${escapeHtml(already_priced_in)}</b></span><span><b class="radar-stage-pill entry-${classKey(entry_stage)}">${escapeHtml(entry_stage)}</b><small class="decision-action-label">Action</small><b class="decision-action">${escapeHtml(action)}</b></span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid ai-stock-details">
      ${detailItem("Why Selected", why_selected)}${detailItem("Risk / What Remains Unproven", risk_unproven)}
      ${detailItem("Category / Beneficiary Type", category)}${detailItem("Discovery Maturity", beneficiary.opportunity_stage || "Missing")}
      ${detailItem("Price Discovery / Priced In", `${price_discovery_stage} · ${already_priced_in}. ${beneficiary.price_discovery_rationale || "Evidence unavailable."}`)}
      ${detailItem("Entry Stage", `${entry_stage}. ${beneficiary.entry_stage?.rationale || "Detailed technical evidence remains in Swing Trade Opportunity."}`)}${detailItem("Action", action)}
      ${detailItem("Catalyst Validation", catalystStatus(beneficiary))}
      ${detailItem("Company-Specific Catalyst", beneficiary.company_specific_catalyst || "Missing: no validated company-specific catalyst.", !beneficiary.company_specific_catalyst)}
      ${detailItem("Industry / Theme Catalyst", beneficiary.industry_theme_catalyst || "Missing", !beneficiary.industry_theme_catalyst)}
      ${detailItem("Ranking Penalty", `${beneficiary.priced_in_penalty ?? 0} points applied to ranking and Multibagger Potential.`)}
      ${detailItem("Early-Opportunity Ranking", beneficiary.radar_rank_score === null || beneficiary.radar_rank_score === undefined ? "Missing" : `${beneficiary.radar_rank_score} / 100`)}
      ${detailItem("Beneficiary Relevance", beneficiary.beneficiary_relevance === null || beneficiary.beneficiary_relevance === undefined ? "Missing" : `${beneficiary.beneficiary_relevance} / 100 · ${beneficiary.data_completeness ?? "Missing"}% complete`)}
      ${detailItem("Company Evidence Completeness", `${beneficiary.company_evidence_completeness ?? 0}% · ${beneficiary.company_confirmation_confidence || "Low / Theme Only"}${beneficiary.company_score_cap ? ` · company-confirmation score cap ${beneficiary.company_score_cap}` : ""}`)}
      ${detailItem("Shared Theme Context", trend.what_it_means)}${detailItem("Key Intelligence", companyNarrative.key_intelligence || "Missing / Not Yet Confirmed")}${detailItem("Demand Drivers / Company Position", companyNarrative.demand_drivers || "Missing / Not Yet Confirmed")}${detailItem("Current Bottleneck / Company Position", companyNarrative.current_bottleneck || "Missing / Not Yet Confirmed")}${detailItem("Next Likely Bottleneck / Company Position", companyNarrative.next_likely_bottleneck || "Missing / Not Yet Confirmed")}
      ${detailItem("Market Expectation / Priced In", trend.market_expectation, true)}${detailItem("What to Watch Next", companyNarrative.watch_next || "Missing / Not Yet Confirmed")}
      ${renderMarketSnapshot(beneficiary.market_data, "qqq")}
      <div class="detail-item detail-wide"><dt>Thesis Evidence</dt><dd>${renderDiscoveryEvidence("Evidence", beneficiary.thesis_evidence || [], "Missing / logical beneficiary thesis has not been structured.")}</dd></div>
      <div class="detail-item detail-wide"><dt>Ticker-Specific Confirmation Evidence</dt><dd>${renderDiscoveryEvidence("Evidence", beneficiary.confirmation_evidence || [], "Missing / Not Yet Confirmed: no company-specific commercial evidence is connected.")}</dd></div>
      ${renderEarlyRadarBreakdown("Bottleneck Opportunity Score", beneficiary.bottleneck_score_components, beneficiary.early_discovery_completeness?.bottleneck_opportunity)}
      ${renderEarlyRadarBreakdown("Multibagger Potential Score", beneficiary.multibagger_score_components, beneficiary.early_discovery_completeness?.multibagger_potential)}
      ${renderAiHorizons(companyNarrative.horizons || {})}${renderAiEvidence("Shared Theme Evidence (not company confirmation)", trend.confirming_evidence)}${renderAiEvidence("Contradicting Trend Evidence", trend.contradicting_evidence)}${renderAiHistory(trend)}
      <div class="detail-item detail-wide"><dt>Active Monitoring</dt><dd>${watchlistAction(ticker, beneficiary.company, "Radar", "ai")}</dd></div>
    </dl></details>`;
  }).join("") || `<p class="loading-state">No public AI or technology stocks have sufficient beneficiary evidence for this view.</p>`;
}

function renderAiReaccelerationAlerts(section = {}) {
  const alerts = Array.isArray(section.alerts) ? section.alerts : [];
  const target = document.getElementById("ai-reacceleration-alerts");
  if (!target) return;
  target.innerHTML = alerts.map((alert) => {
    const price = alert.current_price === null || alert.current_price === undefined
      ? "Price unavailable" : currentPriceLabel(alert.ticker, { current_price: alert.current_price, currency: alert.currency });
    const signal = alert.reacceleration_signal || (Array.isArray(alert.reasons) ? alert.reasons[0] : null) || "Alert reason unavailable.";
    const action = hasValidCompanyCatalyst(alert) ? (alert.action || "WATCH") : "WATCH / WAIT FOR VALID CATALYST";
    return `<article class="reacceleration-card">
      <div class="reacceleration-identity"><strong>${tickerLink(alert.ticker)}</strong><small>${escapeHtml(alert.company || "Company missing")} · ${escapeHtml(price)}</small></div>
      <div class="reacceleration-reason"><strong>Re-Acceleration Signal</strong><p>${escapeHtml(signal)}</p></div>
      <div class="reacceleration-stage"><small>Entry Stage</small><b class="radar-stage-pill entry-${classKey(alert.entry_stage)}">${escapeHtml(alert.entry_stage || "Unavailable")}</b><small>Catalyst</small><b class="radar-stage-pill entry-${classKey(alert.entry_stage)}">${escapeHtml(catalystStatus(alert))}</b><small>Action</small><b class="radar-stage-pill entry-${classKey(alert.entry_stage)}">${escapeHtml(action)}</b></div>
      <div class="reacceleration-context"><small>Price Discovery</small><span>${escapeHtml(alert.price_discovery_stage || "Missing")} · Priced In ${escapeHtml(alert.already_priced_in || "Missing")}</span></div>
    </article>`;
  }).join("") || `<p class="loading-state">No known AI beneficiary currently meets a re-acceleration trigger.</p>`;
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

function companyTickerMarkup(row = {}) {
  const company = escapeHtml(row.company || "Company missing");
  const ticker = yahooFinanceTicker(row.ticker);
  return ticker ? `${company} · ${tickerPriceMarkup(ticker, row.market_data)}` : company;
}

function relatedTickerMarkup(row = {}) {
  const tickers = Array.isArray(row.related_tickers) ? row.related_tickers.filter(yahooFinanceTicker) : [];
  return tickers.length ? `Related: ${tickers.map((ticker) => tickerPriceMarkup(ticker)).join(", ")}` : "";
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

function newsDetailMarkup(label, markup) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${markup || "Missing"}</dd></div>`;
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
        ${newsDetailMarkup("Company / ticker", companyTickerMarkup(story))}
        ${newsDetail("Confirmation status", story.status)}
      </dl>
      ${relatedTickerMarkup(story) ? `<p class="news-related-tickers">${relatedTickerMarkup(story)}</p>` : ""}
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

function renderBiotechRadar(rows, targetId = "biotech-radar") {
  document.getElementById(targetId).innerHTML = rows.map((row) => {
    const action = biotechRadarAction(row);
    return `<details class="radar-item biotech-radar-item"><summary>
      <span class="radar-name"><strong>${tickerLink(row.ticker)}</strong><small>${escapeHtml(row.company)} · ${escapeHtml(currentPriceLabel(row.ticker, row.market_data) || "Price unavailable")}</small></span>
      ${renderScore(row.biotech_opportunity_score ?? row.opportunity_score, "Biotech Opportunity")}${renderScore(row.multibagger_potential_score, "Multibagger Potential")}
      <span><b class="radar-stage-pill">${escapeHtml(row.price_discovery_stage || "Emerging")}</b></span><span><b class="radar-stage-pill priced-${classKey(row.already_priced_in || "NO")}">${escapeHtml(row.already_priced_in || "NO")}</b></span><span><b class="radar-stage-pill entry-${classKey(row.entry_stage?.stage || "Unavailable")}">${escapeHtml(row.entry_stage?.stage || "Unavailable")}</b><small class="decision-action-label">Action</small><b class="decision-action">${escapeHtml(action)}</b></span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid biotech-details">
      ${detailItemMarkup("Company → Program → Indication → Catalyst", `${escapeHtml(row.company)} (${tickerPriceMarkup(row.ticker, row.market_data)}) → ${escapeHtml(row.program)} → ${escapeHtml(row.indication)} → ${escapeHtml(row.catalyst)}`)}
      ${detailItem("Why Selected", row.why_important)}${detailItem("Risk / What Remains Unproven", row.risks)}
      ${detailItem("Price Discovery / Priced In", `${row.price_discovery_stage || "Emerging"} · ${row.already_priced_in || "NO"}. ${row.price_discovery_rationale || "Evidence unavailable."}`)}
      ${detailItem("Entry Stage", `${row.entry_stage?.stage || "Unavailable"}. ${row.entry_stage?.rationale || "Detailed technical evidence remains in Swing Trade Opportunity."}`)}${detailItem("Action", action)}
      ${detailItem("Catalyst Validation", catalystStatus(row))}${detailItem("Company-Specific Catalyst", row.company_specific_catalyst || "Missing: no validated company-specific catalyst.", !row.company_specific_catalyst)}${detailItem("Industry / Theme Catalyst", row.industry_theme_catalyst || "Missing", !row.industry_theme_catalyst)}
      ${detailItem("Ranking Penalty", `${row.priced_in_penalty ?? 0} points applied to ranking and Multibagger Potential.`)}
      ${detailItem("Early-Opportunity Ranking", row.radar_rank_score === null || row.radar_rank_score === undefined ? "Missing" : `${row.radar_rank_score} / 100`)}
      ${detailItem("Clinical Evidence", row.clinical_evidence, String(row.clinical_evidence).startsWith("Missing"))}${detailItem("Upcoming Catalyst", row.upcoming_catalyst)}${detailItem("Previous Trial Results", row.previous_results, String(row.previous_results).startsWith("Missing"))}
      ${detailItem("FDA / Regulatory Status", row.regulatory_status)}${detailItem("Commercial Potential", row.commercial_potential)}
      ${detailItem("Market Expectation / Priced In", row.market_expectation, String(row.market_expectation).startsWith("Missing"))}${detailItem("Positioning / Short Interest", row.positioning, String(row.positioning).startsWith("Missing"))}
      ${detailItem("Risks", row.risks)}${detailItem("What to Watch Next", row.watch_next)}
      ${detailItem("Scientific Evidence", row.scientific_evidence_score === null ? "Missing" : `${row.scientific_evidence_score} / 30`)}${detailItem("Catalyst Impact / Company Sensitivity", `${row.catalyst_impact_score} / 25. ${row.company_sensitivity}`)}${detailItem("Expectation Gap", row.expectation_gap_score === null ? "Missing" : `${row.expectation_gap_score} / 20`)}
      ${detailItem("Binary Risk", `${row.binary_risk}. ${row.binary_risk_rationale}`)}${detailItem("Data Completeness / Confidence", `${row.data_completeness}% / ${row.confidence}`)}${detailItem("Evidence Gate", `${row.evidence_gate.passed ? "Passed" : "Not passed"}. ${row.evidence_gate.rule}`)}
      ${detailItem("Evidence Integrity Gate", `${row.evidence_integrity_gate.concern_identified ? "Concern identified; confidence capped." : "No explicit integrity concern identified in connected evidence."} ${row.evidence_integrity_gate.rule}`)}
      ${detailItem("Market Cap / Size", row.market_cap === null || row.market_cap === undefined ? "Missing" : `${row.market_cap_bucket} · ${Number(row.market_cap).toLocaleString()}`)}${detailItem("Probability of Success", row.probability_of_success)}${detailItem("Cash Runway / Dilution", row.cash_runway_dilution)}
      ${renderMarketSnapshot(row.market_data, "xbi")}${renderMarketSnapshot(row.sector_market_data, "sp500")}
      ${renderEarlyRadarBreakdown("Multibagger Potential Score", row.multibagger_score_components, row.multibagger_data_completeness)}
      ${renderScoreBreakdown(row.score_components, row.data_completeness)}${renderSources(row.sources, row.score_as_of)}
      ${renderBiotechEvidenceGroup("Confirming Evidence", row.confirming_evidence)}${renderBiotechEvidenceGroup("Mixed Evidence", row.mixed_evidence)}${renderBiotechEvidenceGroup("Contradicting Evidence", row.contradicting_evidence)}${renderBiotechHistory(row)}
      <div class="detail-item detail-wide"><dt>Active Monitoring</dt><dd>${watchlistAction(row.ticker, row.company, "Radar", "biotech")}</dd></div>
    </dl></details>`;
  }).join("") || `<p class="loading-state">No biotech opportunities are available.</p>`;
}

function renderCryptoRadar(rows, targetId = "crypto-radar") {
  document.getElementById(targetId).innerHTML = rows.map((row) => {
    const action = cryptoRadarAction(row);
    return `<details class="radar-item crypto-radar-item"><summary>
      <span class="radar-name"><strong>${tickerLink(row.ticker)}</strong><small>${escapeHtml(row.company)} · ${escapeHtml(currentPriceLabel(row.ticker, row.market_data) || "Price unavailable")}</small></span>
      ${renderScore(row.crypto_opportunity_score, "Crypto Opportunity")}${renderScore(row.multibagger_potential_score, "Multibagger Potential")}
      <span><b class="radar-stage-pill">${escapeHtml(row.price_discovery_stage || "Emerging")}</b></span><span><b class="radar-stage-pill priced-${classKey(row.already_priced_in || "NO")}">${escapeHtml(row.already_priced_in || "NO")}</b></span><span><b class="radar-stage-pill entry-${classKey(row.entry_stage?.stage || "Unavailable")}">${escapeHtml(row.entry_stage?.stage || "Unavailable")}</b><small class="decision-action-label">Action</small><b class="decision-action">${escapeHtml(action)}</b></span><span class="expand-control" aria-hidden="true">+</span>
    </summary><dl class="detail-grid crypto-details">
      ${detailItemMarkup("Asset / Company", `${escapeHtml(row.company)} (${tickerPriceMarkup(row.ticker, row.market_data)}) · ${escapeHtml(row.asset_type || "Type missing")}`)}
      ${detailItem("Thesis", row.thesis)}${detailItem("Major Catalysts", row.catalysts)}${detailItem("Major Risks", row.risks)}
      ${detailItem("Price Discovery / Priced In", `${row.price_discovery_stage || "Emerging"} · ${row.already_priced_in || "NO"}. ${row.price_discovery_rationale || "Evidence unavailable."}`)}
      ${detailItem("Entry Stage", `${row.entry_stage?.stage || "Unavailable"}. ${row.entry_stage?.rationale || "Detailed technical evidence is unavailable."}`)}${detailItem("Action", action)}
      ${detailItem("Ranking Penalty", `${row.priced_in_penalty ?? 0} points applied to ranking and Multibagger Potential.`)}
      ${detailItem("Early-Opportunity Ranking", row.radar_rank_score === null || row.radar_rank_score === undefined ? "Missing" : `${row.radar_rank_score} / 100`)}
      ${detailItem("Data Completeness / Confidence", `${row.data_completeness ?? "Missing"}% / ${row.confidence || "Missing"}`)}
      ${detailItem("Missing Data", (row.missing_data || []).join(", ") || "None in the defined V1 score; review evidence dates and limitations.")}
      ${renderMarketSnapshot(row.market_data, "btc")}
      ${renderScoreBreakdown(row.score_components, row.data_completeness)}
      ${renderEarlyRadarBreakdown("Multibagger Potential Score", row.multibagger_score_components, row.multibagger_data_completeness)}
      ${renderSources(row.sources, row.score_as_of)}
      <div class="detail-item detail-wide radar-sources"><dt>Evidence / Score History</dt><dd><p>${escapeHtml(row.why_changed || "Missing")}</p><ul>${(row.score_history || []).slice(-5).reverse().map((item) => `<li>${escapeHtml(item.as_of)}: Opportunity ${escapeHtml(item.crypto_opportunity_score ?? "Missing")} · Multibagger ${escapeHtml(item.multibagger_potential_score ?? "Missing")} · Rank ${escapeHtml(item.radar_rank_score ?? "Missing")}</li>`).join("") || "<li>No prior snapshot.</li>"}</ul></dd></div>
    </dl></details>`;
  }).join("") || `<p class="loading-state">No crypto or stablecoin opportunities are available.</p>`;
}

function radarAnalysisMatches(data, ticker) {
  const aiTrends = data.radar?.ai || [];
  const ai = [];
  const seen = new Set();
  for (const trend of aiTrends) {
    for (const beneficiary of trend.beneficiary_records || []) {
      if (normalizedTicker(beneficiary.ticker) !== ticker) continue;
      const key = `${trend.trend}|${ticker}`;
      if (!seen.has(key)) ai.push({ trend, beneficiary });
      seen.add(key);
    }
  }
  for (const candidate of data.radar?.ai_manual_analysis_candidates || []) {
    const beneficiary = candidate.beneficiary || {};
    if (normalizedTicker(beneficiary.ticker) !== ticker) continue;
    const trend = aiTrends.find((row) => row.trend === candidate.trend) || { trend: candidate.trend };
    const key = `${trend.trend}|${ticker}`;
    if (!seen.has(key)) ai.push({ trend, beneficiary });
    seen.add(key);
  }
  ai.sort((a, b) => (b.beneficiary.radar_rank_score ?? -1) - (a.beneficiary.radar_rank_score ?? -1));
  const biotech = (data.radar?.biotech || []).filter((row) => normalizedTicker(row.ticker) === ticker)
    .sort((a, b) => (b.radar_rank_score ?? -1) - (a.radar_rank_score ?? -1));
  const crypto = (data.radar?.crypto || []).filter((row) => normalizedTicker(row.ticker) === ticker)
    .sort((a, b) => (b.radar_rank_score ?? -1) - (a.radar_rank_score ?? -1));
  return { ai, biotech, crypto };
}

function renderMarketOnlyRadarAnalysis(ticker, domain, context) {
  const market = context?.market_data || sharedMarketSecurities[ticker];
  const discovery = context?.price_discovery_stage || "Unavailable";
  const priced = context?.already_priced_in || "Unavailable";
  const entry = context?.entry_stage?.stage || "Unavailable";
  document.getElementById("radar-analyze-details").innerHTML = `<details class="radar-item ai-stock-radar-item"><summary>
    <span class="ai-stock-identity"><strong>${tickerLink(ticker)}</strong><small>${escapeHtml(currentPriceLabel(ticker, market) || "Price unavailable")} · ${escapeHtml(domain === "biotech" ? "Biotechnology" : "AI / Technology")}</small></span>
    ${renderScore(null, "Opportunity Score")}${renderScore(null, "Multibagger Potential")}
    <span><b class="radar-stage-pill">${escapeHtml(discovery)}</b></span><span><b class="radar-stage-pill">${escapeHtml(priced)}</b></span><span><b class="radar-stage-pill">${escapeHtml(entry)}</b></span><span class="expand-control" aria-hidden="true">+</span>
  </summary><dl class="detail-grid"><div class="detail-item detail-wide"><dt>Evidence Boundary</dt><dd>${escapeHtml(context?.score_note || "No company-specific Radar thesis is connected, so Opportunity and Multibagger scores remain missing.")}</dd></div>
    ${detailItem("Price Discovery / Priced In", context?.rationale || "Missing")}${detailItem("Entry Stage", `${entry}. ${context?.entry_stage?.rationale || "Missing"}`)}${renderMarketSnapshot(market, domain === "biotech" ? "xbi" : domain === "crypto" ? "btc" : "qqq")}
  </dl></details>`;
}

function renderRadarAnalysis(data, ticker, requestedDomain) {
  const matches = radarAnalysisMatches(data, ticker);
  const market = sharedMarketSecurities[ticker];
  let domain = requestedDomain;
  if (domain === "auto") domain = matches.crypto.length ? "crypto" : matches.biotech.length ? "biotech" : matches.ai.length ? "ai" :
    (market?.domains?.includes("crypto") ? "crypto" : market?.domains?.includes("biotech") ? "biotech" : "ai");
  const result = document.getElementById("radar-analyze-result");
  const status = document.getElementById("radar-analyze-status");
  result.hidden = false;
  if (domain === "ai" && matches.ai.length) {
    const { trend, beneficiary } = matches.ai[0];
    const why = beneficiary.thesis_evidence?.[0]?.basis || beneficiary.classification_reason || "Company-specific thesis evidence is missing.";
    setText("radar-analyze-summary", `${beneficiary.company} (${ticker}) is analyzed under ${trend.trend}. Bottleneck Opportunity is ${beneficiary.bottleneck_opportunity_score ?? "Missing"}/100 and Multibagger Potential is ${beneficiary.multibagger_potential_score ?? "Missing"}/100; price discovery is ${beneficiary.price_discovery_stage}, priced-in status is ${beneficiary.already_priced_in}, and Entry Stage is ${beneficiary.entry_stage?.stage || "Unavailable"}.`);
    renderNumberedMessages("radar-analyze-takeaways", [conciseRadarText(why), `The ranking penalty is ${beneficiary.priced_in_penalty ?? 0} points; this manual review does not alter automatic Radar ranking.`, beneficiary.confirmation_missing ? "Commercial confirmation remains unproven; monitor orders, backlog, customers, guidance, or revenue evidence." : "Commercial confirmation is connected, but durability and valuation still require monitoring."]);
    renderAiRadar([{ ...trend, beneficiary_records: [beneficiary] }], "radar-analyze-details");
    status.textContent = `${ticker} analyzed with existing AI/Technology Radar evidence. It was not added to automatic rankings.`;
    status.className = "radar-analyze-status is-success";
    return;
  }
  if (domain === "biotech" && matches.biotech.length) {
    const row = matches.biotech[0];
    setText("radar-analyze-summary", `${row.company} (${ticker}) is analyzed at the ${row.program} / ${row.indication} catalyst level. Biotech Opportunity is ${row.biotech_opportunity_score ?? row.opportunity_score ?? "Missing"}/100 and Multibagger Potential is ${row.multibagger_potential_score ?? "Missing"}/100; price discovery is ${row.price_discovery_stage}, priced-in status is ${row.already_priced_in}, and Entry Stage is ${row.entry_stage?.stage || "Unavailable"}.`);
    renderNumberedMessages("radar-analyze-takeaways", [conciseRadarText(row.why_important), `Scientific Evidence is ${row.scientific_evidence_score ?? "Missing"}/30 and Binary Risk is ${row.binary_risk || "Missing"}.`, `The ranking penalty is ${row.priced_in_penalty ?? 0} points; this manual review does not alter automatic Radar ranking.`]);
    renderBiotechRadar([row], "radar-analyze-details");
    status.textContent = `${ticker} analyzed with existing Biotech Radar evidence. It was not added to automatic rankings.`;
    status.className = "radar-analyze-status is-success";
    return;
  }
  if (domain === "crypto" && matches.crypto.length) {
    const row = matches.crypto[0];
    setText("radar-analyze-summary", `${row.company} (${ticker}) is analyzed with the Crypto & Stablecoin model. Crypto Opportunity is ${row.crypto_opportunity_score ?? "Missing"}/100 and Multibagger Potential is ${row.multibagger_potential_score ?? "Missing"}/100; price discovery is ${row.price_discovery_stage}, priced-in status is ${row.already_priced_in}, and Entry Stage is ${row.entry_stage?.stage || "Unavailable"}.`);
    renderNumberedMessages("radar-analyze-takeaways", [conciseRadarText(row.thesis), `The ranking penalty is ${row.priced_in_penalty ?? 0} points; this manual review does not alter automatic Radar ranking.`, row.missing_data?.length ? `Missing inputs: ${row.missing_data.join(", ")}.` : "All defined V1 factors have evidence, but source age and model limitations still require review."]);
    renderCryptoRadar([row], "radar-analyze-details");
    status.textContent = `${ticker} analyzed with existing Crypto & Stablecoin Radar evidence. It was not added to automatic rankings.`;
    status.className = "radar-analyze-status is-success";
    return;
  }
  const context = data.radar?.manual_market_context?.[ticker]?.[domain];
  if (market && context) {
    setText("radar-analyze-summary", `${ticker} has current shared market and technical data, but no ${domain === "biotech" ? "company–program–catalyst" : domain === "crypto" ? "crypto/stablecoin adoption" : "category-specific beneficiary"} evidence in today's Radar analysis universe. Opportunity and Multibagger scores therefore remain missing.`);
    renderNumberedMessages("radar-analyze-takeaways", [`Price Discovery Stage is ${context.price_discovery_stage}; Already Priced In is ${context.already_priced_in}; Entry Stage is ${context.entry_stage?.stage || "Unavailable"}.`, "Market data alone cannot create a Radar thesis or opportunity score.", "The ticker remains outside automatic Radar rankings unless the daily evidence pipeline independently qualifies it."]);
    renderMarketOnlyRadarAnalysis(ticker, domain, context);
    status.textContent = `${ticker} market analysis is available; company-specific Radar evidence is missing.`;
    status.className = "radar-analyze-status";
    return;
  }
  result.hidden = true;
  status.textContent = `${ticker} is syntactically valid but is not available in today's shared market/Radar dataset. No score or quote was fabricated.`;
  status.className = "radar-analyze-status is-error";
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

function highConvictionAction(row = {}) {
  const confirmation = row.market_confirmation || {};
  const entry = row.high_conviction_entry || {};
  const mountain = String(entry.mountain_position || row.mountain_position || "Unconfirmed");
  const entryQuality = String(entry.entry_quality || row.entry_quality || "Unavailable").toUpperCase();
  const remainingUpside = decisionNumber((entry.remaining_upside || row.remaining_upside || {}).percent);
  if (confirmation.confirmed !== true || mountain === "Unconfirmed") return "PASS";
  if (remainingUpside !== null && remainingUpside <= 0) return "PASS";
  if (mountain === "Extended") return "DO NOT CHASE";
  if (mountain === "Upper Mountain") return "WAIT FOR PULLBACK";
  if (!hasValidCompanyCatalyst(row)) return "WATCH / WAIT FOR VALID CATALYST";
  if (mountain === "Mid Mountain") return entryQuality === "ACCEPTABLE" && remainingUpside !== null && remainingUpside >= 15 ? "SMALL SCALE IN" : "WATCH";
  if (remainingUpside === null) return "WATCH";
  if (mountain === "Lower Mountain") return "SCALE IN";
  return mountain === "Confirmed Early" ? "BUY" : "WATCH";
}

function renderHighConvictionDecision(row) {
  const confirmation = row.market_confirmation || {};
  const entry = row.high_conviction_entry || {};
  const suggested = entry.suggested_entry || row.suggested_entry || {};
  const upside = entry.remaining_upside || row.remaining_upside || {};
  const currency = row.market_data?.currency || "USD";
  const priceValue = (value) => value === null || value === undefined ? "Unavailable" : decisionPrice(value, currency);
  const action = highConvictionAction(row);
  const suggestedText = suggested.low === null || suggested.low === undefined || suggested.high === null || suggested.high === undefined
    ? "Unavailable" : `${priceValue(suggested.low)} – ${priceValue(suggested.high)}`;
  return `<section class="high-conviction-decision">
    <div class="high-conviction-decision-heading"><span>Confirmed thesis and entry position</span><strong>${escapeHtml(action)}</strong></div>
    <dl class="high-conviction-decision-grid">
      <div><dt>Conviction Score</dt><dd>${row.conviction_score === null || row.conviction_score === undefined ? "Missing" : `${escapeHtml(row.conviction_score)}/100`}</dd></div>
      <div><dt>Market Confirmation</dt><dd>${escapeHtml(confirmation.status || "Insufficient Data")}${confirmation.score === null || confirmation.score === undefined ? "" : ` · ${escapeHtml(confirmation.score)}/100`}${confirmation.newly_confirmed ? " · Newly Confirmed" : ""}</dd></div>
      <div><dt>Mountain Position</dt><dd>${escapeHtml(entry.mountain_position || row.mountain_position || "Unconfirmed")}</dd></div>
      <div><dt>Remaining Upside</dt><dd>${upside.percent === null || upside.percent === undefined ? "Unavailable" : `${escapeHtml(upside.percent)}%`}<small>${escapeHtml(upside.basis || "")}</small></dd></div>
      <div><dt>Entry Quality</dt><dd>${escapeHtml(entry.entry_quality || row.entry_quality || "Unavailable")}</dd></div>
      <div><dt>Catalyst Validation</dt><dd>${escapeHtml(catalystStatus(row))}</dd></div>
      <div class="opportunity-wide"><dt>Company-Specific Catalyst</dt><dd>${escapeHtml(row.company_specific_catalyst || "Missing: no validated company-specific catalyst.")}</dd></div>
      <div class="opportunity-wide"><dt>Industry / Theme Catalyst</dt><dd>${escapeHtml(row.industry_theme_catalyst || "Missing")}</dd></div>
      <div><dt>Suggested Entry</dt><dd>${escapeHtml(suggestedText)}<small>${escapeHtml(suggested.basis || "")}</small></dd></div>
      <div><dt>Stop / Invalidation</dt><dd>${escapeHtml(priceValue(entry.stop_invalidation ?? row.stop_invalidation))}</dd></div>
      <div><dt>T1 / T2</dt><dd>${escapeHtml(priceValue(entry.target_1 ?? row.target_1))} / ${escapeHtml(priceValue(entry.target_2 ?? row.target_2))}</dd></div>
      <div class="opportunity-wide"><dt>Confirmation Evidence</dt><dd>${escapeHtml((confirmation.evidence || []).join("; ") || confirmation.rationale || "Unavailable")}</dd></div>
      <div class="opportunity-wide"><dt>Candidate Sources</dt><dd>${escapeHtml((row.candidate_sources || []).join(" · ") || "Current research universe")}</dd></div>
    </dl>
  </section>`;
}

function qualifiedHighConvictionRows(data, domain) {
  const canonical = data.high_conviction_engine?.qualified?.[domain];
  const rows = Array.isArray(canonical) ? canonical : (data.monthly_picks?.[domain] || []);
  return rows.filter((row) => row.classification_key === "high-conviction" &&
    row.proven_quality_eligible === true &&
    (row.gates || []).every((gate) => gate.passed === true));
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
    const action = highConvictionAction(row);
    const score = row.final_score === null || row.final_score === undefined ? "Missing" : `${row.final_score}/100`;
    return `<details class="opportunity-card opportunity-${escapeHtml(row.classification_key || "unclassified")}"><summary class="opportunity-summary"><span class="opportunity-rank">${escapeHtml(row.rank)}</span>
      <div><div class="opportunity-top"><h4>${companyTickerMarkup(row)}</h4><span class="opportunity-classification">${escapeHtml(row.classification || "Classification missing")}</span></div>
      <div class="opportunity-score-line"><strong>${escapeHtml(score)}</strong><span>${escapeHtml(row.mountain_position || "Unconfirmed")}</span><span class="opportunity-timing-pill buy-status-${stageClass(action)}">${escapeHtml(action)}</span></div></div><span class="opportunity-expand" aria-hidden="true"></span></summary>
      <div class="opportunity-detail">
      ${renderWhyThisStock(row)}
      ${watchlistAction(row.ticker, row.company, "High Conviction", isBiotech ? "biotech" : "ai")}
      ${renderHighConvictionDecision(row)}
      ${renderBuyDecision(row, isBiotech, decision)}
      <p class="opportunity-why"><strong>Why selected:</strong> ${escapeHtml(row.why_selected || row.thesis || "Missing")}</p>
      <ul class="opportunity-factors">${factors || "<li class=\"factor-missing\"><span>Factor scores</span><strong>Missing</strong></li>"}</ul>
      <dl><div><dt>Company Quality</dt><dd><strong>${quality.company_quality_score === null || quality.company_quality_score === undefined ? "Missing" : `${escapeHtml(quality.company_quality_score)}/100`}</strong> · ${escapeHtml(quality.data_completeness ?? 0)}% complete · ${escapeHtml(quality.confidence || "Low")} confidence${quality.latest_period_end ? ` · period ${escapeHtml(quality.latest_period_end)}` : ""}</dd></div><div><dt>Expectation state</dt><dd>${escapeHtml(row.expectation_state || row.expectation?.state || "Data Insufficient")}</dd></div><div><dt>Technical / entry status</dt><dd><strong>${escapeHtml(technical.signal || "Insufficient Data")}</strong> · ${escapeHtml(technical.rationale || "Market inputs missing.")}</dd></div>${isBiotech ? "" : `<div><dt>Catalyst</dt><dd>${escapeHtml(row.catalyst || "Missing")}${row.catalyst_timing ? ` · ${escapeHtml(row.catalyst_timing)}` : ""}</dd></div>`}<div><dt>Action</dt><dd>${escapeHtml(action)}</dd></div><div class="opportunity-wide"><dt>Thesis invalidation</dt><dd>${escapeHtml(row.thesis_invalidation || "Missing")}</dd></div></dl>
      <ul class="opportunity-gates" aria-label="High-conviction gates">${gates}</ul>
      <details class="entry-timing-details"><summary><span><small>Entry Timing Score</small>${escapeHtml(entry.state || "Entry timing unavailable")}</span><strong>${entry.entry_timing_score === null || entry.entry_timing_score === undefined ? "Missing" : `${escapeHtml(entry.entry_timing_score)}/100`}</strong><small>${escapeHtml(entry.data_completeness ?? 0)}% complete</small></summary><div class="entry-timing-body"><p>${escapeHtml(entry.entry_guidance || "Entry guidance unavailable because technical inputs are missing.")}</p><dl><div><dt>Resistance / breakout</dt><dd>${entry.resistance_level === null || entry.resistance_level === undefined ? "Missing" : formatMarketValue(entry.resistance_level)}${entry.price_date ? ` · as of ${escapeHtml(entry.price_date)}` : ""}</dd></div><div><dt>Technical invalidation</dt><dd>${entry.invalidation_level === null || entry.invalidation_level === undefined ? "Missing" : formatMarketValue(entry.invalidation_level)}</dd></div></dl><ul class="entry-factor-list">${entryFactors}</ul><ul class="opportunity-gates" aria-label="Entry timing gates">${entryGates}</ul></div></details></div></details>`;
  }).join("") || `<p class="loading-state">No opportunities are available.</p>`;
}

function swingTradeAction(row = {}) {
  const technical = row.technical || {};
  const catalystPassed = row.catalyst?.credible === true;
  const stage = String(row.classification || technical.state || "Unavailable");
  const current = decisionNumber(technical.current_price);
  const support = decisionNumber(technical.support);
  const resistance = decisionNumber(technical.resistance);
  const risk = current !== null && support !== null && current > support ? current - support : null;
  const reward = current !== null && resistance !== null && resistance > current ? resistance - current : null;
  const riskReward = risk && reward !== null ? reward / risk : null;
  if (/Technical Deterioration/i.test(stage)) return "STOP OUT";
  if (/Failed Reversal/i.test(stage)) return "EXIT";
  if (technical.extended || stage === "Extended") return "TAKE PROFIT";
  if (!catalystPassed) return "WATCH / WAIT FOR VALID CATALYST";
  if (stage === "Breakout") return (decisionNumber(technical.volume_vs_20d_average) ?? -1) >= 1.2 ? "BUY" : "HOLD";
  if (stage === "Entry Zone") return riskReward === null || riskReward < 1.5 ? "WATCH" : "BUY";
  if (stage === "Early Reversal") return row.stage_transition?.fresh_favorable_transition ? "SCALE IN" : "ENTER ON BREAKOUT";
  return "WATCH";
}

function renderSwingTrades(section = {}) {
  const reasoning = section.reasoning || [];
  const takeaways = section.take_home_messages || [];
  document.getElementById("swing-reasoning").innerHTML = reasoning.map((item) => `<p>${escapeHtml(item)}</p>`).join("") || `<p>No swing-trade strategy reasoning is available.</p>`;
  document.getElementById("swing-takeaways").innerHTML = takeaways.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || `<li>No qualifying swing-trade conclusions are available.</li>`;
  const rows = [...(section.opportunities || []), ...(section.unverified_setups || [])];
  document.getElementById("swing-opportunities").innerHTML = rows.map((row) => {
    const technical = row.technical || {};
    const catalyst = row.catalyst || {};
    const why = row.why_this_swing_trade_opportunity || {};
    const market = row.market_data || {};
    const transition = row.stage_transition || {};
    const daysSince = transition.days_since_change === null || transition.days_since_change === undefined
      ? "change date unavailable" : transition.days_since_change === 0 ? "changed today" : `${transition.days_since_change} day${transition.days_since_change === 1 ? "" : "s"} since change`;
    const transitionLabel = `${transition.previous_stage || "Unavailable"} → ${transition.current_stage || row.classification || "Unavailable"} · ${daysSince}`;
    const sourceUrl = safeSourceUrl(catalyst.source_link);
    const formatPrice = (value) => value === null || value === undefined ? "Unavailable" : decisionPrice(value, market.currency || "USD");
    const action = swingTradeAction(row);
    return `<details class="swing-card"><summary class="swing-summary"><span class="opportunity-rank">${escapeHtml(row.rank ?? "—")}</span><div><h4>${tickerPriceMarkup(row.ticker, market)}</h4><small>${escapeHtml(row.company)} · Technical ${escapeHtml(technical.technical_setup_score ?? "Missing")}/100</small><small class="swing-transition${transition.fresh_favorable_transition ? " swing-transition-fresh" : ""}">${escapeHtml(transitionLabel)}</small></div><span class="swing-state swing-state-${classKey(row.classification)}">${escapeHtml(row.classification)}<small class="decision-action-label">Action</small><b class="decision-action">${escapeHtml(action)}</b></span><span class="opportunity-expand" aria-hidden="true"></span></summary>
      <div class="swing-detail"><section class="swing-why"><h4>Why This Swing Trade Opportunity</h4><ol>
        <li>${escapeHtml(why.why_chart_selected || "Technical selection reasoning unavailable.")}</li>
        <li>${escapeHtml(why.bottom_reversal_stage || "Bottom/reversal stage unavailable.")}</li>
        <li>${escapeHtml(why.why_still_early || "Entry-timing interpretation unavailable.")}</li>
        <li>${escapeHtml(why.catalyst_support || "Catalyst support unavailable.")}</li>
        <li>${escapeHtml(why.invalidation || "Invalidation condition unavailable.")}</li>
      </ol></section>
      <dl class="swing-technical-grid"><div><dt>Stage Change</dt><dd>${escapeHtml(transitionLabel)}</dd></div><div><dt>Action</dt><dd><strong>${escapeHtml(action)}</strong></dd></div><div><dt>Transition Evidence</dt><dd>${escapeHtml((transition.signals || []).join("; ") || "No fresh transition evidence available.")}</dd></div><div><dt>Current Price</dt><dd>${escapeHtml(formatPrice(technical.current_price))}</dd></div><div><dt>MA20 / MA50</dt><dd>${escapeHtml(formatPrice(technical.ma20))} / ${escapeHtml(formatPrice(technical.ma50))}</dd></div>
        <div><dt>Price vs MA20 / MA50</dt><dd>${escapeHtml(formatChange(technical.price_vs_ma20_pct))} / ${escapeHtml(formatChange(technical.price_vs_ma50_pct))}</dd></div><div><dt>Decline from 52W High</dt><dd>${escapeHtml(formatChange(technical.drawdown_from_high_pct))}</dd></div><div><dt>Recent Low</dt><dd>${escapeHtml(formatPrice(technical.recent_low))}</dd></div><div><dt>Distance From Bottom</dt><dd>${escapeHtml(formatChange(technical.distance_from_bottom_pct))}</dd></div>
        <div><dt>Bottom Formation</dt><dd>${technical.bottom_stabilized ? "Stabilization rule passed" : "Still forming / not confirmed"}${technical.base_duration_sessions ? ` · ${escapeHtml(technical.base_duration_sessions)} sessions` : ""}</dd></div><div><dt>Early Reversal</dt><dd>${technical.early_reversal_confirmed ? "Confirmed by available momentum rules" : "Not yet confirmed"}</dd></div><div><dt>RSI / MACD</dt><dd>${escapeHtml(technical.rsi_14 ?? "Missing")} / ${escapeHtml(technical.macd?.histogram ?? "Missing")}</dd></div><div><dt>Volume vs 20D Average</dt><dd>${technical.volume_vs_20d_average === null || technical.volume_vs_20d_average === undefined ? "Unavailable" : `${escapeHtml(technical.volume_vs_20d_average)}x`}</dd></div>
        <div><dt>Support</dt><dd>${escapeHtml(formatPrice(technical.support))}</dd></div><div><dt>Resistance</dt><dd>${escapeHtml(formatPrice(technical.resistance))}</dd></div><div><dt>Invalidation</dt><dd>${escapeHtml(formatPrice(technical.invalidation_level))}</dd></div><div><dt>Extended?</dt><dd>${technical.extended ? "Yes — do not chase" : "No"}</dd></div></dl>
      <section class="swing-catalyst"><h5>Step 2 · Credible Catalyst Check</h5><p><strong>${escapeHtml(catalyst.status || catalystStatus(row))}</strong></p><p><strong>Company-Specific Catalyst:</strong> ${escapeHtml(catalyst.company_specific_catalyst || "Missing: no validated company-specific catalyst.")}</p><p><strong>Industry / Theme Catalyst:</strong> ${escapeHtml(catalyst.industry_theme_catalyst || (!hasValidCompanyCatalyst(row) ? catalyst.description : null) || "Missing")}</p><p>Timing: ${escapeHtml(catalyst.timing || "Missing")} · Source: ${escapeHtml(catalyst.source || "Missing")}${catalyst.date ? ` · ${escapeHtml(catalyst.date)}` : ""}</p><p>${escapeHtml(catalyst.basis || catalyst.validation_reason || "Missing")}</p>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read Source</a>` : ""}</section>
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
  for (const domain of ["ai", "biotech"]) {
    for (const row of data.watchlists?.[domain] || []) {
      const sources = row.watchlist_sources || [];
      for (const source of sources) add(row, source, domain, row.why,
        (row.strategy_contexts || []).join(" "));
    }
  }
  currentAutomaticWatchlistTickers = new Set(selected.keys());
  return selected;
}

function watchlistTechnical(snapshot = {}, domain = "ai") {
  const price = snapshot.current_price; const averages = snapshot.moving_averages || {}; const inputs = snapshot.entry_inputs || {}; const macd = snapshot.macd || {};
  const readiness = snapshot.watchlist_entry_readiness?.[domain] || {};
  const readinessDecision = readiness.buy_decision || {};
  const ma20 = averages.ma20; const ma50 = averages.ma50;
  const distance = (reference) => Number.isFinite(Number(price)) && Number.isFinite(Number(reference)) && Number(reference) > 0 ? Math.round((price / reference - 1) * 10000) / 100 : null;
  const vs20 = distance(ma20); const vs50 = distance(ma50); const proximity = inputs.breakout_proximity_pct;
  const volumeRatio = snapshot.volume_vs_20d_average; const rsi = snapshot.rsi_14;
  const extended = (Number.isFinite(Number(rsi)) && rsi >= 75) || (Number.isFinite(Number(inputs.distance_from_recent_low_pct)) && inputs.distance_from_recent_low_pct >= 35);
  let buyStatus = readinessDecision.status || "WAIT";
  if (!readinessDecision.status && extended) buyStatus = "EXTENDED / TOO LATE";
  const resistance = inputs.resistance_level;
  const entryZone = Number.isFinite(Number(resistance)) ? { low: Math.round(resistance * .99 * 100) / 100, high: Math.round(resistance * 1.01 * 100) / 100, reference: resistance } : { low: null, high: null, reference: null };
  const supportCandidates = [inputs.base_low, ma20, ma50, inputs.invalidation_level]
    .filter((value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) && Number(value) < Number(price));
  const support = supportCandidates.length ? Math.max(...supportCandidates) : null;
  const trend = vs20 === null || vs50 === null ? "Data unavailable" : vs20 >= 0 && vs50 >= 0 ? "Constructive uptrend" : vs20 < 0 && vs50 < 0 ? "Weak/downtrend" : "Mixed / transition";
  const bottom = inputs.base_duration_sessions ? `${inputs.base_duration_sessions}-session consolidation detected; this is a range rule, not proof of a durable bottom.` : "No qualifying 42/63-session consolidation; bottom formation is not confirmed.";
  const reversal = macd.crossover === "bullish" ? "Bullish MACD crossover detected." : macd.improving ? "Momentum is improving, but reversal confirmation is incomplete." : macd.histogram === null || macd.histogram === undefined ? "Reversal data unavailable." : "No confirmed momentum reversal in the available MACD data.";
  const volumeTrend = volumeRatio === null || volumeRatio === undefined ? "Unavailable" : `${formatMarketValue(volumeRatio)}x 20-day average${inputs.up_down_volume_ratio_20d === null || inputs.up_down_volume_ratio_20d === undefined ? "" : ` · up/down volume ${formatMarketValue(inputs.up_down_volume_ratio_20d)}x`}`;
  const tightRange = inputs.tight_range_20d_pct;
  const chartPattern = inputs.base_duration_sessions ? `${inputs.base_duration_sessions}-session base/range under the existing close-range rule.`
    : Number.isFinite(Number(tightRange)) && tightRange <= 8 ? `Tight 20-session range (${tightRange}%).` : "No rules-based base or constructive chart pattern is confirmed.";
  const earlyReversal = macd.crossover === "bullish" && vs20 !== null && vs20 >= 0 ? "Early reversal confirmed by a bullish MACD crossover and price recovery above MA20."
    : macd.improving ? "Early reversal is developing but not fully confirmed." : "No early reversal is confirmed by the available momentum data.";
  const breakoutVolume = inputs.breakout_volume_ratio;
  const volumeConfirmation = Number.isFinite(Number(breakoutVolume)) && breakoutVolume >= 1.2 ? `Confirmed at ${breakoutVolume}x 20-day volume.`
    : Number.isFinite(Number(breakoutVolume)) ? `Not confirmed; current ratio is ${breakoutVolume}x.` : "Volume confirmation is unavailable.";
  const accumulation = inputs.up_down_volume_ratio_20d;
  const accumulationSignal = Number.isFinite(Number(accumulation)) && accumulation >= 1.1 ? `Constructive accumulation-like signal (${accumulation}x up/down volume).`
    : Number.isFinite(Number(accumulation)) ? `No constructive accumulation signal (${accumulation}x up/down volume).` : "Accumulation signal is unavailable.";
  const targets = domain === "biotech" && entryZone.reference ? { plus_10: Math.round(entryZone.reference * 1.1 * 100) / 100, plus_15: Math.round(entryZone.reference * 1.15 * 100) / 100, plus_20: Math.round(entryZone.reference * 1.2 * 100) / 100 } : null;
  return { current_price: price, ma20, ma50, price_vs_ma20_pct: vs20, price_vs_ma50_pct: vs50, support, resistance,
    volume_vs_20d_average: volumeRatio, volume_trend: volumeTrend, trend, bottom_formation: bottom, reversal_status: reversal,
    entry_zone: entryZone, buy_status: buyStatus, invalidation_level: inputs.invalidation_level, targets,
    target_basis: targets ? "Planned watchlist entry reference" : null, chart_pattern: chartPattern,
    early_reversal: earlyReversal, volume_confirmation: volumeConfirmation, accumulation_signal: accumulationSignal,
    technical_entry_readiness_score: readiness.entry_timing_score ?? null, entry_timing_state: readiness.state || null,
    extended: readiness.state_key === "extended" || extended };
}

function waitingCondition(technical) {
  if (technical.buy_status === "READY TO BUY") return "No additional trigger under the current technical rules; confirm the move continues to hold above the entry area.";
  if (technical.buy_status === "IN ENTRY ZONE") return "Wait for confirming volume and price acceptance above the entry reference before treating the setup as ready.";
  if (technical.buy_status === "APPROACHING ENTRY") return "Price still needs to reach and hold the entry area with improving momentum and volume.";
  if (technical.buy_status === "EXTENDED / TOO LATE") return "Do not chase; wait for extension to normalize and a new base or controlled pullback to form.";
  return "A tighter base, improving momentum, and price confirmation near resistance are still missing.";
}

const CONSTRUCTIVE_WATCHLIST_STATUSES = ["READY TO BUY", "IN ENTRY ZONE", "APPROACHING ENTRY"];
const WATCHLIST_STATUS_PRIORITY = { "READY TO BUY": 3, "IN ENTRY ZONE": 2, "APPROACHING ENTRY": 1 };

function hydrateWatchlistSelection(selection, data, manual = false) {
  const sourcePriority = { "Swing Trade": 3, "High Conviction": 2, Radar: 1, Manual: 0 };
  const ticker = selection.ticker;
  const primaryRecord = [...selection.records].sort((a, b) => sourcePriority[b.source] - sourcePriority[a.source])[0] || { row: {} };
  const sourceRow = primaryRecord.row;
  const snapshot = sharedMarketSecurities[ticker] || sourceRow.market_data || {};
  const domain = selection.domain || snapshot.domains?.[0] || sourceRow.domain || "ai";
  const technical = watchlistTechnical(snapshot, domain);
  const reasons = selection.records.map((record) => record.why).filter(Boolean);
  const reason = reasons.join(" ") || (manual ? "Personally selected for technical entry monitoring." : "Selected for active technical monitoring.");
  const sourceLabel = selection.sources.join(" + ");
  const commentary = {
    why_on_watchlist: reason,
    selection_source: `${selection.sources.length > 1 ? "Sources" : "Source"}: ${sourceLabel}. ${selection.contexts.join(" ")}`,
    chart: `${technical.trend}. Price is ${technical.price_vs_ma20_pct ?? "an unknown distance"}% versus MA20 and ${technical.price_vs_ma50_pct ?? "an unknown distance"}% versus MA50.`,
    bottom_base: technical.bottom_formation,
    early_reversal: technical.early_reversal,
    chart_pattern: technical.chart_pattern,
    volume_confirmation: technical.volume_confirmation,
    accumulation_signal: technical.accumulation_signal,
    entry: `Buy status is ${technical.buy_status}. ${waitingCondition(technical)}`,
    waiting_for: waitingCondition(technical),
    stronger: "Stronger if price holds above MA20/MA50, MACD improves, and volume confirms a move through resistance.",
    weaker: "Weaker or invalidated if price loses documented support/invalidation, relative strength fades, or volume expands on down days.",
    extension: technical.extended ? "Extended / too late under the current do-not-chase gate." : "Not currently blocked by the extension gate.",
  };
  const biotechRadar = (data.radar?.biotech || []).find((row) => normalizedTicker(row.ticker) === ticker) || {};
  technical.catalyst = sourceRow.catalyst?.description || sourceRow.catalyst || biotechRadar.catalyst || "Missing";
  technical.catalyst_timing = sourceRow.catalyst?.timing || sourceRow.catalyst_timing || biotechRadar.expected_timing || "Missing";
  technical.binary_risk = sourceRow.binary_risk || biotechRadar.binary_risk || "Missing";
  const currentManualData = snapshot.data_status === "current" && snapshot.current_price !== null && snapshot.current_price !== undefined;
  return { ...sourceRow, ticker, company: selection.company || sourceRow.company || ticker, domain,
    category: domain === "biotech" ? "Biotech" : "AI", watchlist_sources: selection.sources,
    market_data: snapshot, watchlist_commentary: commentary, watchlist_technical: technical,
    manual_validation_status: manual ? (currentManualData ? "validated-shared-market-data" : "pending-market-data") : null,
    watchlist_section: manual ? "manually-entered" : "website-selected" };
}

function hydratedWatchlistRows(data) {
  const automatic = [...automaticWatchlistSelections(data).values()]
    .map((selection) => hydrateWatchlistSelection(selection, data, false))
    .sort((a, b) => (a.website_selected_rank ?? Number.MAX_SAFE_INTEGER) - (b.website_selected_rank ?? Number.MAX_SAFE_INTEGER)
      || WATCHLIST_STATUS_PRIORITY[b.watchlist_technical.buy_status] - WATCHLIST_STATUS_PRIORITY[a.watchlist_technical.buy_status]
      || (b.watchlist_technical.technical_entry_readiness_score ?? -1) - (a.watchlist_technical.technical_entry_readiness_score ?? -1)
      || a.ticker.localeCompare(b.ticker));
  let upgradedValidation = false;
  const manual = initializeWatchlistState(data).manual_items.map((item) => {
    const ticker = normalizedTicker(item.ticker);
    const refreshedSnapshot = sharedMarketSecurities[ticker];
    if (refreshedSnapshot?.data_status === "current" && refreshedSnapshot.current_price !== null && refreshedSnapshot.current_price !== undefined && item.validation_status !== "validated-shared-market-data") {
      item.validation_status = "validated-shared-market-data";
      item.domain = item.domain || refreshedSnapshot.domains?.[0] || "ai";
      upgradedValidation = true;
    }
    const candidate = (data.candidate_discovery?.candidates || []).find((row) => normalizedTicker(row.ticker) === ticker)
      || { company: item.company || ticker, ticker };
    return hydrateWatchlistSelection({ ticker, company: item.company || candidate.company || ticker,
      domain: item.domain || sharedMarketSecurities[ticker]?.domains?.[0] || "ai", sources: ["Manual"],
      validation_status: item.validation_status,
      records: [{ source: "Manual", row: candidate, why: item.reason || "Personally selected for technical entry monitoring." }],
      contexts: ["Personally added; strategy qualification and the automatic technical-entry screen are not required."] }, data, true);
  }).sort((a, b) => a.ticker.localeCompare(b.ticker));
  if (upgradedValidation) writeWatchlistState();
  return { websiteSelected: automatic,
    topEntry: automatic.filter((row) => row.watchlist_group === "top-entry"),
    developing: automatic.filter((row) => row.watchlist_group === "developing"),
    manuallyEntered: manual };
}

function watchlistDecisionAction(technical = {}, dataUnavailable = false) {
  if (dataUnavailable || String(technical.trend || "").toLowerCase() === "data unavailable") return "DATA UNAVAILABLE";
  const buyStatus = String(technical.buy_status || "WAIT");
  const stage = String(technical.entry_timing_state || "");
  if (technical.extended || buyStatus === "EXTENDED / TOO LATE") return "DO NOT CHASE";
  if (buyStatus === "READY TO BUY") return "BUY";
  if (buyStatus === "IN ENTRY ZONE") return "SCALE IN";
  if (buyStatus === "APPROACHING ENTRY") return "WATCH";
  if (/breakout/i.test(stage)) return "WAIT FOR PULLBACK";
  if (/near buy|reversal|base building/i.test(stage)) return "WATCH";
  if (/deterioration|falling/i.test(stage) || String(technical.trend || "").toLowerCase().includes("weak/downtrend")) return "PASS";
  return "WAIT";
}

function renderWatchlistCard(row, manualAdded) {
  const commentary = row.watchlist_commentary || {};
  const technical = row.watchlist_technical || {};
  const currency = row.market_data?.currency || "USD";
  const zone = technical.entry_zone || {};
  const targets = technical.targets || {};
  const isBiotech = row.category === "Biotech";
  const formatTechnicalPrice = (value) => value === null || value === undefined || value === "" ? "Unavailable" : decisionPrice(value, currency);
  const zoneText = zone.low === null || zone.low === undefined || zone.high === null || zone.high === undefined
    ? "Unavailable" : `${formatTechnicalPrice(zone.low)} – ${formatTechnicalPrice(zone.high)}`;
  const biotechFields = isBiotech ? `<div><dt>+10% Level</dt><dd>${escapeHtml(formatTechnicalPrice(targets.plus_10))}</dd></div>
    <div><dt>+15% Level</dt><dd>${escapeHtml(formatTechnicalPrice(targets.plus_15))}</dd></div><div><dt>+20% Level</dt><dd>${escapeHtml(formatTechnicalPrice(targets.plus_20))}</dd></div>
    <div><dt>Catalyst</dt><dd>${escapeHtml(technical.catalyst || row.catalyst || "Missing")}${technical.catalyst_timing && technical.catalyst_timing !== "Missing" ? ` · ${escapeHtml(technical.catalyst_timing)}` : ""}</dd></div>
    <div><dt>Binary Risk</dt><dd>${escapeHtml(technical.binary_risk || "Missing")}</dd></div>` : "";
  const sources = row.watchlist_sources || ["Manual"];
  const sourcePrefix = sources.length > 1 ? "Sources" : "Source";
  const dataUnavailable = manualAdded && row.manual_validation_status === "pending-market-data";
  const unavailableLabel = dataUnavailable ? "Data Unavailable" : "Unavailable";
  const readinessScore = technical.technical_entry_readiness_score === null || technical.technical_entry_readiness_score === undefined ? unavailableLabel : `${technical.technical_entry_readiness_score}/100`;
  const entryStage = technical.entry_timing_state || unavailableLabel;
  const extendedStage = !dataUnavailable && (technical.extended || /extended/i.test(entryStage));
  const buyStatus = dataUnavailable ? "Data Unavailable" : extendedStage ? "EXTENDED / TOO LATE" : technical.buy_status || "WAIT";
  const action = watchlistDecisionAction({ ...technical, buy_status: buyStatus, extended: extendedStage }, dataUnavailable);
  const validationNote = dataUnavailable ? `<p class="watchlist-pending-note"><strong>Data Unavailable:</strong> this Manual selection remains saved. The page will retry against the refreshed shared market-data and Entry Readiness pipeline on every load; no quote or score is fabricated.</p>` : "";
  const manualIdentity = `<span class="position-identity"><span class="stock-category">${escapeHtml(row.category)}</span><span class="watchlist-source">${sourcePrefix}: ${escapeHtml(sources.join(" + "))}</span><strong>${tickerLink(row.ticker)}</strong><small>${escapeHtml(row.company)}</small><small>Current Price: ${escapeHtml(dataUnavailable ? "Data Unavailable" : formatTechnicalPrice(technical.current_price))}</small></span>`;
  const automaticIdentity = `<span class="position-identity"><span class="stock-category">${escapeHtml(row.category)}</span><span class="watchlist-source">${sourcePrefix}: ${escapeHtml(sources.join(" + "))}</span><strong>${tickerPriceMarkup(row.ticker, row.market_data)}</strong><small>${escapeHtml(row.company)}</small></span>`;
  const summary = manualAdded
    ? `<summary class="watchlist-summary manual-watchlist-summary">${manualIdentity}<span><small>Entry Readiness</small><strong>${escapeHtml(readinessScore)}</strong></span><span><small>Entry Stage</small><strong>${escapeHtml(entryStage)}</strong></span><span><small>Buy Status</small><strong class="watch-buy-status watch-buy-${classKey(buyStatus)}">${escapeHtml(buyStatus)}</strong></span><span><small>Action</small><b class="decision-action">${escapeHtml(action)}</b></span><button type="button" class="watchlist-action watchlist-remove manual-watchlist-remove" data-watchlist-remove data-ticker="${escapeHtml(row.ticker)}" aria-label="Remove ${escapeHtml(row.ticker)} from Manually Entered">Remove</button><span class="opportunity-expand" aria-hidden="true"></span></summary>`
    : `<summary class="watchlist-summary">${automaticIdentity}<span><small>Entry Readiness</small><strong>${escapeHtml(readinessScore)}</strong></span><span><small>Entry Stage</small><strong>${escapeHtml(entryStage)}</strong></span><span><small>Buy Status</small><strong class="watch-buy-status watch-buy-${classKey(buyStatus)}">${escapeHtml(buyStatus)}</strong></span><span><small>Action</small><b class="decision-action">${escapeHtml(action)}</b></span><span class="opportunity-expand" aria-hidden="true"></span></summary>`;
  return `<details class="watchlist-card${manualAdded ? " manual-watchlist-card" : ""}">${summary}
    <div class="watchlist-detail">${validationNote}<section class="watchlist-commentary"><h4>Watchlist Commentary</h4><p><strong>Why it is here:</strong> ${escapeHtml(commentary.why_on_watchlist || row.why || "Missing")}</p><p><strong>Selection source:</strong> ${escapeHtml(commentary.selection_source || `${sourcePrefix}: ${sources.join(" + ")}`)}</p><p><strong>What the chart is doing:</strong> ${escapeHtml(commentary.chart || "Technical interpretation unavailable.")}</p><p><strong>Bottom / base:</strong> ${escapeHtml(commentary.bottom_base || technical.bottom_formation || "Missing")}</p><p><strong>Early reversal:</strong> ${escapeHtml(commentary.early_reversal || technical.early_reversal || "Missing")}</p><p><strong>Chart pattern:</strong> ${escapeHtml(commentary.chart_pattern || technical.chart_pattern || "Missing")}</p><p><strong>Volume confirmation:</strong> ${escapeHtml(commentary.volume_confirmation || technical.volume_confirmation || "Missing")}</p><p><strong>Accumulation:</strong> ${escapeHtml(commentary.accumulation_signal || technical.accumulation_signal || "Missing")}</p><p><strong>Entry situation:</strong> ${escapeHtml(commentary.entry || "Entry interpretation unavailable.")}</p><p><strong>What still needs to happen:</strong> ${escapeHtml(commentary.waiting_for || "Missing")}</p><p><strong>Setup strengthens if:</strong> ${escapeHtml(commentary.stronger || "Missing")}</p><p><strong>Invalidation / weaker if:</strong> ${escapeHtml(commentary.weaker || "Missing")}</p><p><strong>Extension check:</strong> ${escapeHtml(commentary.extension || "Missing")}</p></section>
    <dl class="watchlist-technical-grid"><div><dt>Current Price</dt><dd>${escapeHtml(formatTechnicalPrice(technical.current_price))}</dd></div><div><dt>MA20</dt><dd>${escapeHtml(formatTechnicalPrice(technical.ma20))}</dd></div><div><dt>MA50</dt><dd>${escapeHtml(formatTechnicalPrice(technical.ma50))}</dd></div>
    <div><dt>Technical Entry Readiness</dt><dd>${escapeHtml(technical.technical_entry_readiness_score === null || technical.technical_entry_readiness_score === undefined ? "Unavailable" : `${technical.technical_entry_readiness_score}/100 · ${technical.entry_timing_state || "State unavailable"}`)}</dd></div><div><dt>Price vs MA20 / MA50</dt><dd>${escapeHtml(formatChange(technical.price_vs_ma20_pct))} / ${escapeHtml(formatChange(technical.price_vs_ma50_pct))}</dd></div><div><dt>Support</dt><dd>${escapeHtml(formatTechnicalPrice(technical.support))}</dd></div><div><dt>Resistance</dt><dd>${escapeHtml(formatTechnicalPrice(technical.resistance))}</dd></div>
    <div><dt>Volume / Volume Trend</dt><dd>${escapeHtml(technical.volume_trend || (technical.volume_vs_20d_average === null || technical.volume_vs_20d_average === undefined ? "Unavailable" : `${formatMarketValue(technical.volume_vs_20d_average)}x`))}</dd></div><div><dt>Volume Confirmation</dt><dd>${escapeHtml(technical.volume_confirmation || "Missing")}</dd></div><div><dt>Accumulation Signal</dt><dd>${escapeHtml(technical.accumulation_signal || "Missing")}</dd></div><div><dt>Trend</dt><dd>${escapeHtml(technical.trend || "Missing")}</dd></div><div><dt>Bottom / Base Formation</dt><dd>${escapeHtml(technical.bottom_formation || "Missing")}</dd></div>
    <div><dt>Early Reversal</dt><dd>${escapeHtml(technical.early_reversal || "Missing")}</dd></div><div><dt>Chart Pattern</dt><dd>${escapeHtml(technical.chart_pattern || "Missing")}</dd></div><div><dt>Reversal Status</dt><dd>${escapeHtml(technical.reversal_status || "Missing")}</dd></div><div><dt>Entry Zone</dt><dd>${escapeHtml(zoneText)}</dd></div><div><dt>Buy Status</dt><dd>${escapeHtml(buyStatus)}</dd></div><div><dt>Action</dt><dd><strong>${escapeHtml(action)}</strong></dd></div><div><dt>Invalidation Level</dt><dd>${escapeHtml(formatTechnicalPrice(technical.invalidation_level))}</dd></div>${biotechFields}</dl>
    ${isBiotech && technical.target_basis ? `<p class="watchlist-basis-note">${escapeHtml(technical.target_basis)}; these are planning levels before a brokerage trade, not actual-position P/L targets.</p>` : ""}<div class="watchlist-controls"><button type="button" class="position-action" data-pending-order-prefill data-ticker="${escapeHtml(row.ticker)}">Create Pending Order</button><button type="button" class="position-action" data-position-prefill data-ticker="${escapeHtml(row.ticker)}" data-company="${escapeHtml(row.company)}" data-domain="${escapeHtml(row.domain || "ai")}" data-sources="${escapeHtml(sources.join(" + "))}">Bought / Move to My Stock</button>${manualAdded ? `<button type="button" class="watchlist-action watchlist-remove" data-watchlist-remove data-ticker="${escapeHtml(row.ticker)}">Delete / Remove</button>` : `<span class="watchlist-managed-note">Automatically managed by strategy selection plus the technical-entry screen</span>`}</div></div></details>`;
}

function renderWatchlist(data) {
  const rows = hydratedWatchlistRows(data);
  const topTarget = document.getElementById("top-entry-watchlist");
  const developingTarget = document.getElementById("developing-watchlist");
  const manualTarget = document.getElementById("manually-entered-watchlist");
  topTarget.innerHTML = rows.topEntry.map((row) => renderWatchlistCard(row, false)).join("")
    || `<p class="loading-state">No strategy-derived stock currently passes the strongest actionable-entry screen.</p>`;
  developingTarget.innerHTML = rows.developing.map((row) => renderWatchlistCard(row, false)).join("")
    || `<p class="loading-state">No additional strategy-derived setup is currently developing constructively.</p>`;
  manualTarget.innerHTML = rows.manuallyEntered.map((row) => renderWatchlistCard(row, true)).join("")
    || `<p class="loading-state">No tickers have been manually entered.</p>`;
}

function pendingOrderAnalysis(order) {
  const snapshot = sharedMarketSecurities[order.ticker] || {};
  const domain = order.domain || snapshot.domains?.[0] || "ai";
  const technical = watchlistTechnical(snapshot, domain);
  const inputs = snapshot.entry_inputs || {};
  const limitPrice = Number(order.limit_price);
  const shares = Number(order.shares);
  const currentPrice = Number(snapshot.current_price);
  const validPrice = (value) => Number.isFinite(Number(value)) && Number(value) > 0;
  const rawEntryStage = technical.entry_timing_state || technical.buy_status || "Unavailable";
  const stageKey = String(rawEntryStage).toLowerCase();
  const reversalConfirmed = snapshot.macd?.crossover === "bullish" || ["READY TO BUY", "IN ENTRY ZONE"].includes(technical.buy_status);
  const technicallyFalling = stageKey.includes("falling") || stageKey.includes("technical deterioration")
    || (String(technical.trend).toLowerCase().includes("weak/downtrend") && !reversalConfirmed);
  const approachingEntry = technical.buy_status === "APPROACHING ENTRY" || stageKey.includes("near buy") || stageKey.includes("entry zone") || stageKey.includes("breakout");
  const entryCandidates = [technical.support, inputs.recent_low_63d, technical.ma20, technical.ma50, inputs.resistance_level]
    .filter(validPrice).map(Number);
  let suggestedEntry = null; let suggestedEntryReason = "WAIT — No technical entry recommended yet.";
  if (!technicallyFalling && (reversalConfirmed || approachingEntry)) {
    if ((approachingEntry || ["READY TO BUY", "IN ENTRY ZONE"].includes(technical.buy_status)) && validPrice(inputs.resistance_level)) {
      suggestedEntry = Number(inputs.resistance_level);
      suggestedEntryReason = "Suggested entry is anchored to the existing resistance/entry trigger because the setup is approaching or confirming entry.";
    } else {
      const supportsAtOrBelowPrice = entryCandidates.filter((value) => !validPrice(currentPrice) || value <= currentPrice);
      if (supportsAtOrBelowPrice.length) {
        suggestedEntry = Math.max(...supportsAtOrBelowPrice);
        suggestedEntryReason = "Suggested entry is anchored to the closest available support, recent low, or MA20/MA50 level after reversal confirmation.";
      }
    }
  }
  const validBelowLimit = (value) => Number.isFinite(Number(value)) && Number(value) > 0 && Number(value) < limitPrice;
  const invalidation = validBelowLimit(inputs.invalidation_level) ? Number(inputs.invalidation_level) : null;
  const structuralSupports = [inputs.base_low, inputs.recent_low_63d, technical.support].filter(validBelowLimit).map(Number);
  const structuralStop = structuralSupports.length ? Math.max(...structuralSupports) : null;
  const atr = [snapshot.atr_14, inputs.atr_14, snapshot.volatility?.atr_14].map(Number).find((value) => Number.isFinite(value) && value > 0) || null;
  let suggestedEntryLow = suggestedEntry; let suggestedEntryHigh = suggestedEntry;
  if (suggestedEntry !== null && atr) {
    suggestedEntryLow = Math.max(.01, suggestedEntry - (.5 * atr));
    suggestedEntryHigh = suggestedEntry + (.5 * atr);
    suggestedEntryReason += " The displayed zone spans one ATR around that technical anchor.";
  } else if (suggestedEntry !== null) {
    const nearestDistinct = entryCandidates.filter((value) => Math.abs(value - suggestedEntry) > .000001)
      .sort((a, b) => Math.abs(a - suggestedEntry) - Math.abs(b - suggestedEntry))[0];
    if (validPrice(nearestDistinct)) {
      suggestedEntryLow = Math.min(suggestedEntry, nearestDistinct);
      suggestedEntryHigh = Math.max(suggestedEntry, nearestDistinct);
      suggestedEntryReason += " With ATR unavailable, the zone uses the nearest distinct existing technical level rather than an invented volatility band.";
    } else {
      suggestedEntryReason += " ATR and a second technical boundary are unavailable, so a single suggested price is shown.";
    }
  }
  const suggestedEntryMid = suggestedEntryLow !== null && suggestedEntryHigh !== null ? (suggestedEntryLow + suggestedEntryHigh) / 2 : null;
  const limitDifference = suggestedEntryMid !== null ? limitPrice - suggestedEntryMid : null;
  const limitDifferencePct = suggestedEntryMid > 0 ? (limitDifference / suggestedEntryMid) * 100 : null;
  let limitRecommendation = "WAIT";
  if (!technicallyFalling && suggestedEntryLow !== null && suggestedEntryHigh !== null) {
    limitRecommendation = limitPrice < suggestedEntryLow ? "RAISE LIMIT" : limitPrice > suggestedEntryHigh ? "LOWER LIMIT" : "GOOD LIMIT";
  }
  const atrStop = atr && limitPrice - (2 * atr) > 0 ? limitPrice - (2 * atr) : null;
  const stop = invalidation ?? structuralStop ?? atrStop;
  const stopBasis = invalidation !== null ? "Existing technical invalidation below the planned limit price."
    : structuralStop !== null ? "Closest available support from the existing base/recent-low analysis below the planned limit price."
      : atrStop !== null ? "Two ATRs below the planned limit price because no structural invalidation was available."
        : "Unavailable: no support, recent-low, invalidation, or ATR input supports a non-fabricated stop.";
  const riskPerShare = stop !== null ? limitPrice - stop : null;
  const resistance = Number.isFinite(Number(inputs.resistance_level)) && Number(inputs.resistance_level) > limitPrice ? Number(inputs.resistance_level) : null;
  const target1 = resistance ?? (riskPerShare > 0 ? limitPrice + riskPerShare : null);
  const target2 = riskPerShare > 0 ? Math.max(limitPrice + (2 * riskPerShare), target1 !== null ? target1 + riskPerShare : 0) : null;
  const targetBasis = resistance !== null ? "Target 1 uses existing resistance; Target 2 extends by the same technically defined per-share risk."
    : riskPerShare > 0 ? "No resistance above the limit was available; targets use 1R and 2R from the technically derived stop."
      : "Unavailable because a defensible technical stop/risk unit could not be calculated.";
  const maxLoss = riskPerShare > 0 && shares > 0 ? riskPerShare * shares : null;
  const potentialProfit1 = target1 !== null && shares > 0 ? (target1 - limitPrice) * shares : null;
  const potentialProfit2 = target2 !== null && shares > 0 ? (target2 - limitPrice) * shares : null;
  const riskReward = maxLoss > 0 && potentialProfit2 !== null ? potentialProfit2 / maxLoss : null;
  const hasSuggestedEntry = suggestedEntryLow !== null && suggestedEntryHigh !== null;
  const hasStop = stop !== null && Number.isFinite(Number(stop));
  const hasTarget = target1 !== null && Number.isFinite(Number(target1));
  const otocoIncomplete = !hasSuggestedEntry || !hasStop || !hasTarget;
  const otocoStatus = technicallyFalling || limitRecommendation === "WAIT" ? "WAIT"
    : otocoIncomplete ? "INCOMPLETE DATA" : limitRecommendation === "GOOD LIMIT" ? "READY" : "WAIT";
  const actionableOtoco = otocoStatus === "READY";
  const hasCurrentPrice = Number.isFinite(currentPrice) && currentPrice > 0;
  const fillReady = hasCurrentPrice && currentPrice <= limitPrice;
  const nearLimit = hasCurrentPrice && currentPrice > limitPrice && ((currentPrice / limitPrice) - 1) <= .02;
  const status = !hasCurrentPrice ? "MARKET DATA UNAVAILABLE" : fillReady && limitRecommendation === "WAIT" ? "AT/BELOW LIMIT — TECHNICAL WAIT"
    : fillReady ? "AT/BELOW LIMIT — VERIFY FILL" : nearLimit ? "NEAR LIMIT" : "WAITING";
  const action = technicallyFalling || (riskReward !== null && riskReward < 1) ? "CANCEL / REASSESS"
    : !hasCurrentPrice || otocoIncomplete ? "WAIT"
      : limitRecommendation === "LOWER LIMIT" ? "LOWER LIMIT"
        : limitRecommendation === "RAISE LIMIT" ? "RAISE LIMIT"
          : otocoStatus === "READY" ? "READY" : "WAIT";
  return { ...order, snapshot, domain, technical, current_price: hasCurrentPrice ? currentPrice : null,
    entry_stage: rawEntryStage, suggested_entry: suggestedEntry, suggested_entry_low: suggestedEntryLow,
    suggested_entry_high: suggestedEntryHigh, suggested_entry_reason: suggestedEntryReason,
    limit_difference: limitDifference, limit_difference_pct: limitDifferencePct, limit_recommendation: limitRecommendation,
    stop, stop_basis: stopBasis,
    target_1: target1, target_2: target2, target_basis: targetBasis, max_loss: maxLoss,
    potential_profit_1: potentialProfit1, potential_profit_2: potentialProfit2, risk_reward: riskReward,
    reference_resistance: validPrice(inputs.resistance_level) ? Number(inputs.resistance_level) : null,
    otoco_status: otocoStatus, action, actionable_otoco: actionableOtoco, order_status: status, fill_ready: fillReady };
}

function renderPendingOrderCard(row) {
  const currency = row.snapshot.currency || "USD";
  const suggestedEntryText = row.suggested_entry_low === null ? "Unavailable"
    : Math.abs(row.suggested_entry_high - row.suggested_entry_low) < .000001 ? positionPrice(row.suggested_entry_low, currency)
      : `${positionPrice(row.suggested_entry_low, currency)} – ${positionPrice(row.suggested_entry_high, currency)}`;
  const differenceText = row.limit_difference === null ? "Unavailable"
    : `${row.limit_difference >= 0 ? "+" : "−"}${positionPrice(Math.abs(row.limit_difference), currency)} (${row.limit_difference_pct >= 0 ? "+" : ""}${row.limit_difference_pct.toFixed(2)}%)`;
  return `<details class="pending-order-card"><summary class="pending-order-summary"><span class="pending-order-company"><strong>${tickerLink(row.ticker)}</strong><small>${escapeHtml(row.company || row.ticker)}</small><button type="button" class="position-action position-remove pending-order-summary-remove" data-pending-order-remove data-ticker="${escapeHtml(row.ticker)}" aria-label="Remove ${escapeHtml(row.ticker)} from Pending Orders">Remove</button></span><span><small>Current Price</small><strong>${escapeHtml(positionPrice(row.current_price, currency))}</strong></span><span><small>Your Limit</small><strong>${escapeHtml(positionPrice(row.limit_price, currency))}</strong></span><span><small>Shares</small><strong>${escapeHtml(row.shares)}</strong></span><span><small>Entry Stage</small><strong>${escapeHtml(row.entry_stage)}</strong></span><span><small>Order Status</small><strong class="pending-order-status pending-order-status-${classKey(row.order_status)}">${escapeHtml(row.order_status)}</strong><small class="decision-action-label">Action</small><b class="decision-action">${escapeHtml(row.action)}</b></span><span class="opportunity-expand" aria-hidden="true"></span></summary>
    <div class="pending-order-detail"><div class="pending-order-workflow" aria-label="Pending order price workflow"><div><small>Current Price</small><strong>${escapeHtml(positionPrice(row.current_price, currency))}</strong></div><span>→</span><div><small>Your Limit</small><strong>${escapeHtml(positionPrice(row.limit_price, currency))}</strong></div><span>→</span><div><small>Suggested Entry</small><strong>${escapeHtml(suggestedEntryText)}</strong></div><span>→</span><div><small>Stop Loss</small><strong>${escapeHtml(positionPrice(row.stop, currency))}</strong></div><span>→</span><div><small>Target 1</small><strong>${escapeHtml(positionPrice(row.actionable_otoco ? row.target_1 : null, currency))}</strong></div><span>→</span><div><small>Target 2</small><strong>${escapeHtml(positionPrice(row.actionable_otoco ? row.target_2 : null, currency))}</strong></div></div>
    <div class="pending-order-decision"><span><small>Limit vs Suggested Entry</small><strong>${escapeHtml(differenceText)}</strong></span><span><small>Recommendation</small><strong class="pending-order-recommendation recommendation-${classKey(row.limit_recommendation)}">${escapeHtml(row.limit_recommendation)}</strong></span>${row.limit_recommendation === "WAIT" ? `<p>WAIT — No technical entry recommended yet. Reversal confirmation is missing or the setup is deteriorating.</p>` : ""}</div>
    <section class="pending-order-otoco"><div class="pending-order-otoco-heading"><h4>OTOCO Recommendation</h4><strong class="otoco-status otoco-status-${classKey(row.otoco_status)}">${escapeHtml(row.otoco_status)}</strong></div><dl class="pending-order-metrics"><div><dt>Suggested Entry / Zone</dt><dd>${escapeHtml(suggestedEntryText)}</dd></div><div><dt>Recommended Stop Loss</dt><dd>${escapeHtml(positionPrice(row.stop, currency))}</dd></div><div><dt>Target 1</dt><dd>${escapeHtml(positionPrice(row.actionable_otoco ? row.target_1 : null, currency))}</dd></div><div><dt>Target 2</dt><dd>${escapeHtml(positionPrice(row.actionable_otoco ? row.target_2 : null, currency))}</dd></div>${!row.actionable_otoco && row.reference_resistance !== null ? `<div><dt>Reference Resistance</dt><dd>${escapeHtml(positionPrice(row.reference_resistance, currency))}</dd></div>` : ""}<div><dt>Max Loss $</dt><dd>${escapeHtml(positionDollars(row.actionable_otoco ? row.max_loss : null, currency))}</dd></div><div><dt>Potential Profit $</dt><dd>${row.actionable_otoco ? `${escapeHtml(positionDollars(row.potential_profit_1, currency))} at Target 1${row.potential_profit_2 === null ? "" : `<br>${escapeHtml(positionDollars(row.potential_profit_2, currency))} at Target 2`}` : "Unavailable — OTOCO is not ready"}</dd></div><div><dt>Risk / Reward</dt><dd>${escapeHtml(row.actionable_otoco && row.risk_reward !== null ? `1 : ${row.risk_reward.toFixed(2)}` : "Unavailable — OTOCO is not ready")}</dd></div><div><dt>Entry Stage</dt><dd>${escapeHtml(row.entry_stage)}</dd></div><div><dt>Action</dt><dd><strong>${escapeHtml(row.action)}</strong></dd></div><div><dt>Order Status</dt><dd>${escapeHtml(row.order_status)}</dd></div></dl></section>
    <div class="pending-order-notes"><p><strong>Entry reason:</strong> ${escapeHtml(row.suggested_entry_reason)}</p><p><strong>Stop reason:</strong> ${escapeHtml(row.stop_basis)}</p><p><strong>Target reason:</strong> ${escapeHtml(row.target_basis)}</p><p><strong>Fill note:</strong> This dashboard does not connect to a broker. “At/below limit” means verify the actual fill before moving the order to My Stock.</p></div>
    <div class="pending-order-actions"><button type="button" class="position-action" data-pending-order-edit data-ticker="${escapeHtml(row.ticker)}">Edit</button><button type="button" class="position-action position-remove" data-pending-order-remove data-ticker="${escapeHtml(row.ticker)}">Delete Pending Order</button>${row.fill_ready ? `<button type="button" class="position-action" data-pending-order-fill data-ticker="${escapeHtml(row.ticker)}">Filled — Move to My Stock</button>` : ""}</div></div></details>`;
}

function renderPendingOrders() {
  const target = document.getElementById("pending-order-cards");
  if (!target) return;
  const rows = initializePendingOrderState().orders.map(pendingOrderAnalysis).sort((a, b) => a.ticker.localeCompare(b.ticker));
  target.innerHTML = rows.map(renderPendingOrderCard).join("") || `<p class="loading-state">No pending orders have been entered.</p>`;
}

function setPendingOrderFormStatus(message, type = "") {
  const target = document.getElementById("pending-order-form-status");
  if (!target) return;
  target.textContent = message;
  target.className = `pending-order-form-status${type ? ` is-${type}` : ""}`;
}

function resetPendingOrderForm() {
  const form = document.getElementById("pending-order-form");
  if (!form) return;
  form.reset(); form.dataset.editingTicker = "";
  document.getElementById("pending-order-save").textContent = "Add Pending Order";
  document.getElementById("pending-order-cancel").hidden = true;
}

function prefillPendingOrderForm(ticker, edit = false) {
  const key = normalizedTicker(ticker);
  const existing = initializePendingOrderState().orders.find((item) => normalizedTicker(item.ticker) === key);
  resetPendingOrderForm();
  document.getElementById("pending-order-ticker").value = key;
  if (existing) {
    document.getElementById("pending-order-limit-price").value = existing.limit_price;
    document.getElementById("pending-order-shares").value = existing.shares;
    document.getElementById("pending-order-form").dataset.editingTicker = key;
    document.getElementById("pending-order-save").textContent = "Update Pending Order";
    document.getElementById("pending-order-cancel").hidden = false;
  }
  document.getElementById("pending-orders")?.scrollIntoView({ behavior: "smooth", block: "start" });
  document.getElementById(existing || edit ? "pending-order-limit-price" : "pending-order-ticker")?.focus();
  setPendingOrderFormStatus(existing ? `${key} is ready to edit.` : `Enter a limit buy price and shares for ${key}.`, "success");
}

function savePendingOrderForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const ticker = normalizedTicker(document.getElementById("pending-order-ticker").value);
  const limitPrice = Number(document.getElementById("pending-order-limit-price").value);
  const shares = Number(document.getElementById("pending-order-shares").value);
  if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) return setPendingOrderFormStatus("Enter a valid ticker.", "error");
  if (!sharedMarketSecurities[ticker]) return setPendingOrderFormStatus(`${ticker} is not in the current shared market feed, so a technically analyzed pending order cannot be created.`, "error");
  if (!(limitPrice > 0) || !(shares > 0)) return setPendingOrderFormStatus("Limit buy price and shares must be greater than zero.", "error");
  const originalTicker = normalizedTicker(form.dataset.editingTicker);
  const existingIndex = pendingOrderState.orders.findIndex((item) => normalizedTicker(item.ticker) === (originalTicker || ticker));
  if (!originalTicker && pendingOrderState.orders.some((item) => normalizedTicker(item.ticker) === ticker)) return setPendingOrderFormStatus(`${ticker} already has a pending order. Edit the existing order instead.`, "error");
  const record = { ticker, company: positionCompany(ticker, currentDashboardData), limit_price: limitPrice, shares,
    domain: sharedMarketSecurities[ticker]?.domains?.[0] || "ai", updated_at: new Date().toISOString() };
  if (existingIndex >= 0) pendingOrderState.orders[existingIndex] = record; else pendingOrderState.orders.push(record);
  writePendingOrderState(); renderPendingOrders(); resetPendingOrderForm();
  setPendingOrderFormStatus(`${ticker} pending order ${existingIndex >= 0 ? "updated" : "added"}.`, "success");
}

function removePendingOrder(ticker, confirmRemoval = true) {
  const key = normalizedTicker(ticker);
  if (confirmRemoval && !window.confirm(`Delete the pending ${key} order?`)) return;
  const state = initializePendingOrderState();
  state.orders = state.orders.filter((item) => normalizedTicker(item.ticker) !== key);
  pendingOrderState = state;
  writePendingOrderState(); renderPendingOrders();
  setPendingOrderFormStatus(`${key} was deleted from Pending Orders.`, "success");
}

const POSITION_STATUSES = ["HOLD", "ADD", "TRIM", "TAKE PROFIT", "EXIT"];

function positionSourceNames(value) {
  const allowed = new Set(["Radar", "High Conviction", "Swing Trade", "Manual"]);
  const values = (Array.isArray(value) ? value : String(value || "Manual").split("+")).map((item) => item.trim()).filter((item) => allowed.has(item));
  return [...new Set(values.length ? values : ["Manual"])];
}

function positionCompany(ticker, data) {
  const key = normalizedTicker(ticker);
  const candidate = (data.candidate_discovery?.candidates || []).find((row) => normalizedTicker(row.ticker) === key);
  if (candidate?.company) return candidate.company;
  for (const domain of ["ai", "biotech"]) {
    const pick = (data.monthly_picks?.[domain] || []).find((row) => normalizedTicker(row.ticker) === key);
    if (pick?.company) return pick.company;
  }
  const biotech = (data.radar?.biotech || []).find((row) => normalizedTicker(row.ticker) === key);
  if (biotech?.company) return biotech.company;
  for (const trend of data.radar?.ai || []) {
    const beneficiary = (trend.beneficiary_records || []).find((row) => normalizedTicker(row.ticker) === key);
    if (beneficiary?.company) return beneficiary.company;
  }
  return key;
}

function positionStrategyEvidence(ticker, sources, data) {
  const key = normalizedTicker(ticker);
  const matches = { Radar: [], "High Conviction": [], "Swing Trade": [] };
  for (const trend of data.radar?.ai || []) {
    for (const row of trend.beneficiary_records || []) if (normalizedTicker(row.ticker) === key) matches.Radar.push({
      row, thesis: row.thesis_evidence?.[0]?.basis || trend.what_it_means || trend.why_now,
      invalidation: trend.risks, catalyst: trend.watch_next, domain: "ai",
    });
  }
  for (const row of data.radar?.biotech || []) if (normalizedTicker(row.ticker) === key) matches.Radar.push({
    row, thesis: row.why_important || row.clinical_evidence, invalidation: row.risks,
    catalyst: `${row.catalyst || "Catalyst unavailable"}${row.expected_timing ? ` · ${row.expected_timing}` : ""}`, domain: "biotech",
  });
  for (const domain of ["ai", "biotech"]) for (const row of data.monthly_picks?.[domain] || []) if (normalizedTicker(row.ticker) === key) matches["High Conviction"].push({
    row, thesis: row.why_this_stock?.summary || row.why_selected, invalidation: row.thesis_invalidation,
    catalyst: row.catalyst, domain,
  });
  for (const row of data.swing_trade_opportunities?.opportunities || []) if (normalizedTicker(row.ticker) === key) matches["Swing Trade"].push({
    row, thesis: row.why_this_swing_trade_opportunity?.why_chart_selected,
    invalidation: row.why_this_swing_trade_opportunity?.invalidation,
    catalyst: row.catalyst?.description, domain: row.domain || "ai",
  });
  const requested = positionSourceNames(sources);
  const active = requested.filter((source) => source === "Manual" || matches[source]?.length);
  const records = requested.flatMap((source) => matches[source] || []);
  const explicitBroken = records.some(({ row }) => /thesis broken|avoid/i.test(`${row.classification || ""} ${row.opportunity_status || ""}`));
  const nonManual = requested.filter((source) => source !== "Manual");
  const thesisStatus = explicitBroken ? "Broken by an explicit current strategy status."
    : nonManual.length && active.some((source) => source !== "Manual") ? "Intact under at least one current strategy evidence path."
    : nonManual.length ? "Current website strategy evidence no longer confirms the original source; review required, but this alone does not prove the thesis is broken."
    : "Manual position: no website strategy thesis is required or assumed.";
  return {
    requested, active, records, explicit_broken: explicitBroken, thesis_status: thesisStatus,
    thesis: records.map((item) => item.thesis).filter(Boolean).join(" ") || "No structured website thesis is connected; manage from the available technical evidence and the user's own thesis.",
    thesis_invalidation: records.map((item) => item.invalidation).filter(Boolean).join(" ") || "Missing: no explicit thesis-invalidation statement is connected.",
    catalyst: records.map((item) => item.catalyst).filter(Boolean).join(" ") || "Missing: no source-backed catalyst is connected.",
    domain: records.find((item) => item.domain === "biotech")?.domain || records[0]?.domain || null,
  };
}

function targetRecord(label, price, buyPrice, basis) {
  const valid = Number.isFinite(Number(price)) && Number(price) > 0;
  return { label, price: valid ? Number(price) : null,
    gain_pct: valid && buyPrice > 0 ? Math.round((Number(price) / buyPrice - 1) * 10000) / 100 : null, basis };
}

function positionTargets(position, snapshot, technical, evidence) {
  const buy = Number(position.buy_price);
  const custom = (position.custom_targets || []).map((value) => Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : null);
  let suggested = [];
  let basis = "No reliable target is available; missing targets are not estimated.";
  if (evidence.requested.includes("Swing Trade")) {
    suggested = [buy * 1.10, buy * 1.15, buy * 1.20];
    basis = "Mechanical +10% / +15% / +20% swing-planning levels from average buy price; not valuation targets.";
  } else {
    const resistance = technical.resistance;
    const analystTarget = snapshot.expectation_data?.valuation?.one_year_target;
    suggested = [resistance, analystTarget].filter((value, index, values) => Number.isFinite(Number(value)) && Number(value) > buy && values.indexOf(value) === index).sort((a, b) => a - b);
    basis = evidence.requested.includes("High Conviction")
      ? "Long-term planning uses available technical resistance and dated analyst-consensus context; swing percentages are not applied."
      : "Planning uses available technical resistance and dated expectation context; unavailable levels remain missing.";
  }
  const targets = [0, 1, 2].map((index) => targetRecord(`Target ${index + 1}`, custom[index] ?? suggested[index] ?? null, buy,
    custom[index] ? "User-entered target." : suggested[index] ? basis : "Unavailable."));
  return { targets, basis };
}

function positionStop(position, snapshot, technical, evidence) {
  const current = Number(snapshot.current_price);
  const buy = Number(position.buy_price);
  const inputs = snapshot.entry_inputs || {};
  const isBiotech = position.domain === "biotech" || evidence.domain === "biotech";
  let level = null; let basis = "Missing: no technically meaningful support or invalidation level is available.";
  if (isBiotech && Number.isFinite(Number(inputs.base_low)) && Number(inputs.base_low) > 0 && Number(inputs.base_low) < current) {
    level = Number(inputs.base_low); basis = "Biotech technical invalidation uses the documented multiweek base low to avoid an arbitrarily tight stop.";
  } else if (Number.isFinite(Number(inputs.invalidation_level)) && Number(inputs.invalidation_level) > 0) {
    level = Number(inputs.invalidation_level); basis = "Existing Phase 7 technical invalidation level derived from base support and MA50.";
  } else if (Number.isFinite(Number(technical.support)) && Number(technical.support) > 0) {
    level = Number(technical.support); basis = "Closest available technically derived support below current price.";
  }
  return { level, basis,
    downside_from_current_pct: level && current > 0 ? Math.round((level / current - 1) * 10000) / 100 : null,
    downside_from_buy_pct: level && buy > 0 ? Math.round((level / buy - 1) * 10000) / 100 : null,
    thesis_invalidation: evidence.thesis_invalidation };
}

function positionStatus(position, snapshot, technical, evidence, targets, stop, gainPct) {
  const current = Number(snapshot.current_price);
  const targetPrices = targets.targets.map((item) => item.price);
  const ma50 = snapshot.moving_averages?.ma50;
  const macdHistogram = snapshot.macd?.histogram;
  const stopBroken = stop.level && current < stop.level;
  const deteriorating = (Number.isFinite(Number(ma50)) && current < ma50 && Number.isFinite(Number(macdHistogram)) && macdHistogram < 0);
  const distribution = Number.isFinite(Number(snapshot.entry_inputs?.up_down_volume_ratio_20d)) && snapshot.entry_inputs.up_down_volume_ratio_20d < .8;
  if (evidence.explicit_broken || stopBroken) return "EXIT";
  if ((targetPrices[1] && current >= targetPrices[1]) || (targetPrices[2] && current >= targetPrices[2])) return "TAKE PROFIT";
  if ((targetPrices[0] && current >= targetPrices[0]) || (technical.extended && gainPct >= 10) || deteriorating || (distribution && gainPct < 0)) return "TRIM";
  const nearSupport = technical.support && current >= technical.support && (current / technical.support - 1) <= .03;
  if (evidence.requested.includes("High Conviction") && nearSupport && /Constructive/.test(technical.trend) && !technical.extended) return "ADD";
  if (["READY TO BUY", "IN ENTRY ZONE"].includes(technical.buy_status) && gainPct <= 5 && !technical.extended && !evidence.explicit_broken) return "ADD";
  return "HOLD";
}

function positionDaysHeld(purchaseDate) {
  const purchased = new Date(`${purchaseDate}T00:00:00Z`);
  if (Number.isNaN(purchased.valueOf())) return null;
  const today = new Date();
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.max(0, Math.floor((todayUtc - purchased.valueOf()) / 86400000));
}

function hydratePosition(position, data) {
  const ticker = normalizedTicker(position.ticker);
  const snapshot = sharedMarketSecurities[ticker] || {};
  const evidence = positionStrategyEvidence(ticker, position.strategy_sources, data);
  const domain = position.domain || evidence.domain || snapshot.domains?.[0] || "ai";
  const technical = watchlistTechnical(snapshot, domain);
  const current = Number(snapshot.current_price);
  const buy = Number(position.buy_price);
  const shares = position.shares === null || position.shares === undefined || position.shares === "" ? null : Number(position.shares);
  const cost = buy > 0 && shares > 0 ? buy * shares : null;
  const marketValue = current > 0 && shares > 0 ? current * shares : null;
  const gainLoss = marketValue !== null && cost !== null ? marketValue - cost : null;
  const gainPct = current > 0 && buy > 0 ? (current / buy - 1) * 100 : null;
  const targets = positionTargets(position, snapshot, technical, evidence);
  const stop = positionStop({ ...position, domain }, snapshot, technical, evidence);
  const status = positionStatus(position, snapshot, technical, evidence, targets, stop, gainPct);
  const momentum = snapshot.macd?.crossover === "bullish" ? "Strengthening: bullish MACD crossover."
    : snapshot.macd?.improving ? "Strengthening, but no complete crossover confirmation." : Number.isFinite(Number(snapshot.macd?.histogram)) && snapshot.macd.histogram < 0 ? "Weakening: MACD histogram is negative." : "Momentum confirmation is unavailable or mixed.";
  const volume = technical.volume_confirmation;
  const accumulation = technical.accumulation_signal;
  const riskIncreasing = ["TRIM", "EXIT"].includes(status) || technical.extended;
  const partialTrigger = targets.targets[0].price ? `Consider partial profit-taking if price reaches ${targets.targets[0].label}, rejects resistance, or becomes extended with weakening volume.` : "No numeric partial-profit trigger is available; monitor resistance and extension with volume.";
  const fullExitTrigger = `Full exit requires ${evidence.explicit_broken ? "the currently broken thesis status to remain unresolved" : "an explicit thesis break"}${stop.level ? ` or a confirmed loss of technical invalidation at ${stop.level}` : " or a confirmed technical breakdown"}.`;
  const exitSignalReason = status === "EXIT" ? (evidence.explicit_broken ? "The connected strategy evidence explicitly marks the thesis as broken." : `Current price is below the technical invalidation level${stop.level ? ` at ${positionPrice(stop.level, snapshot.currency || "USD")}` : ""}.`)
    : status === "TAKE PROFIT" ? "Price has reached an upper profit-planning target; review a full or substantial exit."
      : status === "TRIM" ? "A first target, extension, deterioration, or distribution rule supports reducing risk."
        : `No full-exit rule is active. Exit if the thesis breaks or price confirms a loss of ${stop.level ? `technical invalidation at ${positionPrice(stop.level, snapshot.currency || "USD")}` : "technically meaningful support"}.`;
  return { ...position, ticker, company: position.company || positionCompany(ticker, data), domain, snapshot, technical,
    shares, days_held: positionDaysHeld(position.purchase_date), cost, market_value: marketValue, gain_loss: gainLoss, gain_loss_pct: gainPct, targets, stop, status, evidence,
    commentary: {
      trend: technical.trend,
      relative_to_buy: gainPct === null ? "Current P/L is unavailable because a current price is missing." : `The position is ${gainPct >= 0 ? "up" : "down"} ${Math.abs(gainPct).toFixed(2)}% from the average buy price.`,
      structure: `${technical.bottom_formation} ${technical.chart_pattern}`,
      support_resistance: `Support: ${technical.support ?? "Unavailable"}. Resistance: ${technical.resistance ?? "Unavailable"}. MA20: ${technical.ma20 ?? "Unavailable"}; MA50: ${technical.ma50 ?? "Unavailable"}.`,
      momentum, volume, accumulation, thesis: evidence.thesis_status,
      extension: technical.extended ? "The position is extended under the existing do-not-chase framework." : "The position is not currently classified as extended.",
      risk: riskIncreasing ? "Risk is increasing under the current technical/thesis checks." : "No current rule identifies a material increase in position risk; continue monitoring.",
    },
    sell_plan: { partial_trigger: partialTrigger, full_exit_trigger: fullExitTrigger, exit_signal_reason: exitSignalReason },
  };
}

function positionPrice(value, currency = "USD") {
  return value === null || value === undefined || !Number.isFinite(Number(value)) ? "Unavailable" : decisionPrice(Number(value), currency);
}

function positionDollars(value, currency = "USD") {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "Unavailable";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD", maximumFractionDigits: 2 }).format(Number(value));
}

function renderPositionCard(row) {
  const currency = row.snapshot.currency || "USD";
  const gainClass = row.gain_loss_pct > 0 ? "position-gain" : row.gain_loss_pct < 0 ? "position-loss" : "";
  const targetRows = row.targets.targets.map((target) => `<li><strong>${escapeHtml(target.label)}:</strong> ${escapeHtml(positionPrice(target.price, currency))}${target.gain_pct === null ? "" : ` · ${escapeHtml(formatChange(target.gain_pct))} from buy`}<br><small>${escapeHtml(target.basis)}</small></li>`).join("");
  const sources = positionSourceNames(row.strategy_sources).join(" + ");
  return `<details class="position-card"><summary class="position-summary"><span class="position-company"><strong>${tickerLink(row.ticker)} · ${escapeHtml(row.company)}</strong><small>${escapeHtml(sources)}</small></span><span><small>Current Price</small><strong>${escapeHtml(positionPrice(row.snapshot.current_price, currency))}</strong></span><span><small>Buy Price</small><strong>${escapeHtml(positionPrice(row.buy_price, currency))}</strong></span><span><small>Gain / Loss</small><strong class="${gainClass}">${escapeHtml(row.gain_loss_pct === null ? "Unavailable" : formatChange(row.gain_loss_pct))}</strong></span><span><small>Action</small><strong class="position-status position-status-${classKey(row.status)}">${escapeHtml(row.status)}</strong></span><span class="opportunity-expand" aria-hidden="true"></span></summary>
    <div class="position-detail"><section class="position-commentary"><h4>Position Commentary</h4><p><strong>Current trend:</strong> ${escapeHtml(row.commentary.trend)}</p><p><strong>Relative to buy price:</strong> ${escapeHtml(row.commentary.relative_to_buy)}</p><p><strong>Technical structure:</strong> ${escapeHtml(row.commentary.structure)}</p><p><strong>Support / resistance / averages:</strong> ${escapeHtml(row.commentary.support_resistance)}</p><p><strong>Momentum:</strong> ${escapeHtml(row.commentary.momentum)}</p><p><strong>Volume confirmation:</strong> ${escapeHtml(row.commentary.volume)}</p><p><strong>Accumulation / distribution:</strong> ${escapeHtml(row.commentary.accumulation)}</p><p><strong>Original thesis:</strong> ${escapeHtml(row.commentary.thesis)}</p><p><strong>Extension:</strong> ${escapeHtml(row.commentary.extension)}</p><p><strong>Risk:</strong> ${escapeHtml(row.commentary.risk)}</p></section>
    <dl class="position-metrics"><div><dt>Current Price</dt><dd>${escapeHtml(positionPrice(row.snapshot.current_price, currency))}</dd></div><div><dt>Average Buy Price</dt><dd>${escapeHtml(positionPrice(row.buy_price, currency))}</dd></div><div><dt>Shares</dt><dd>${escapeHtml(row.shares === null ? "Not entered" : row.shares)}</dd></div><div><dt>Purchase Date</dt><dd>${escapeHtml(row.purchase_date)}</dd></div><div><dt>Days Held</dt><dd>${escapeHtml(row.days_held === null ? "Unavailable" : row.days_held)}</dd></div><div><dt>Position Cost</dt><dd>${escapeHtml(positionDollars(row.cost, currency))}</dd></div><div><dt>Current Market Value</dt><dd>${escapeHtml(positionDollars(row.market_value, currency))}</dd></div><div><dt>Unrealized Gain/Loss $</dt><dd class="${gainClass}">${escapeHtml(positionDollars(row.gain_loss, currency))}</dd></div><div><dt>Unrealized Gain/Loss %</dt><dd class="${gainClass}">${escapeHtml(row.gain_loss_pct === null ? "Unavailable" : formatChange(row.gain_loss_pct))}</dd></div><div><dt>Strategy Source</dt><dd>${escapeHtml(sources)}</dd></div><div><dt>Action</dt><dd>${escapeHtml(row.status)}</dd></div></dl>
    <dl class="position-analysis-grid"><div><dt>MA20 / MA50</dt><dd>${escapeHtml(positionPrice(row.technical.ma20, currency))} / ${escapeHtml(positionPrice(row.technical.ma50, currency))}</dd></div><div><dt>Support</dt><dd>${escapeHtml(positionPrice(row.technical.support, currency))}</dd></div><div><dt>Resistance</dt><dd>${escapeHtml(positionPrice(row.technical.resistance, currency))}</dd></div><div><dt>Technical Structure</dt><dd>${escapeHtml(row.technical.chart_pattern)}</dd></div><div><dt>Momentum</dt><dd>${escapeHtml(row.commentary.momentum)}</dd></div><div><dt>Volume Confirmation</dt><dd>${escapeHtml(row.technical.volume_confirmation)}</dd></div><div><dt>Accumulation / Distribution</dt><dd>${escapeHtml(row.technical.accumulation_signal)}</dd></div><div><dt>Thesis Status</dt><dd>${escapeHtml(row.evidence.thesis_status)}</dd></div></dl>
    <div class="position-plan-grid"><section class="position-plan"><h5>Profit Targets</h5><p>${escapeHtml(row.targets.basis)}</p><ul>${targetRows}</ul></section><section class="position-plan"><h5>Support / Invalidation</h5><p><strong>Technical support / invalidation:</strong> ${escapeHtml(positionPrice(row.stop.level, currency))}</p><p>${escapeHtml(row.stop.basis)}</p><p>From current: ${escapeHtml(row.stop.downside_from_current_pct === null ? "Unavailable" : formatChange(row.stop.downside_from_current_pct))} · From buy: ${escapeHtml(row.stop.downside_from_buy_pct === null ? "Unavailable" : formatChange(row.stop.downside_from_buy_pct))}</p><p><strong>Thesis invalidation:</strong> ${escapeHtml(row.stop.thesis_invalidation)}</p></section><section class="position-plan"><h5>Exit Signal / Reason</h5><p><strong>Current action:</strong> ${escapeHtml(row.status)}</p><p>${escapeHtml(row.sell_plan.exit_signal_reason)}</p><p>${escapeHtml(row.sell_plan.partial_trigger)}</p><p>${escapeHtml(row.sell_plan.full_exit_trigger)}</p></section><section class="position-plan"><h5>Strategy Context</h5><p><strong>Source:</strong> ${escapeHtml(sources)}</p><p><strong>Thesis status:</strong> ${escapeHtml(row.evidence.thesis_status)}</p><p>${escapeHtml(row.evidence.thesis)}</p>${row.evidence.requested.includes("Swing Trade") ? `<p><strong>Catalyst:</strong> ${escapeHtml(row.evidence.catalyst)}</p>` : ""}</section></div>
    <div class="position-actions"><button type="button" class="position-action" data-position-edit data-ticker="${escapeHtml(row.ticker)}">Edit Position</button><button type="button" class="position-action position-remove" data-position-remove data-ticker="${escapeHtml(row.ticker)}">Delete Position</button></div></div></details>`;
}

function renderPositions(data) {
  const target = document.getElementById("my-stock-positions");
  if (!target) return;
  const rows = initializePositionState().positions.map((position) => hydratePosition(position, data))
    .sort((a, b) => a.ticker.localeCompare(b.ticker));
  target.innerHTML = rows.map(renderPositionCard).join("") || `<p class="loading-state">No owned positions have been entered. Add one directly or move a purchased stock from Watchlist.</p>`;
}

function setPositionFormStatus(message, type = "") {
  const target = document.getElementById("position-form-status");
  if (!target) return;
  target.textContent = message;
  target.className = `position-form-status${type ? ` is-${type}` : ""}`;
}

function resetPositionForm() {
  const form = document.getElementById("position-form");
  if (!form) return;
  form.reset(); form.dataset.editingTicker = ""; form.dataset.fromWatchlist = ""; form.dataset.pendingOrderTicker = "";
  form.dataset.domain = ""; form.dataset.company = "";
  document.getElementById("position-save").textContent = "Add Position";
  document.getElementById("position-cancel").hidden = true;
  document.getElementById("position-purchase-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("position-source").value = "Manual";
}

function prefillPositionForm({ ticker, company, domain, sources, edit = false, buyPrice = null, shares = null, fromPending = false }) {
  const key = normalizedTicker(ticker);
  const existing = initializePositionState().positions.find((item) => normalizedTicker(item.ticker) === key);
  resetPositionForm();
  document.getElementById("position-ticker").value = key;
  document.getElementById("position-source").value = (sources || existing?.strategy_sources?.join(" + ") || "Manual");
  if (domain || existing?.domain) document.getElementById("position-form").dataset.domain = domain || existing.domain;
  if (company || existing?.company) document.getElementById("position-form").dataset.company = company || existing.company;
  if (existing) {
    document.getElementById("position-buy-price").value = existing.buy_price;
    document.getElementById("position-shares").value = existing.shares;
    document.getElementById("position-purchase-date").value = existing.purchase_date;
    (existing.custom_targets || []).forEach((value, index) => { if (value) document.getElementById(`position-target-${index + 1}`).value = value; });
    document.getElementById("position-form").dataset.editingTicker = key;
    document.getElementById("position-save").textContent = "Update Position";
    document.getElementById("position-cancel").hidden = false;
  } else if (!edit) {
    document.getElementById("position-form").dataset.fromWatchlist = key;
    if (Number.isFinite(Number(buyPrice)) && Number(buyPrice) > 0) document.getElementById("position-buy-price").value = Number(buyPrice);
    if (Number.isFinite(Number(shares)) && Number(shares) > 0) document.getElementById("position-shares").value = Number(shares);
  }
  if (fromPending) document.getElementById("position-form").dataset.pendingOrderTicker = key;
  document.getElementById("owned-stocks")?.scrollIntoView({ behavior: "smooth", block: "start" });
  document.getElementById("position-buy-price")?.focus();
  setPositionFormStatus(existing ? `${key} is ready to edit.` : `Enter the actual execution details for ${key}; no position is created until you save.`, "success");
}

function savePositionForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const ticker = normalizedTicker(document.getElementById("position-ticker").value);
  const buyPrice = Number(document.getElementById("position-buy-price").value);
  const sharesValue = document.getElementById("position-shares").value;
  const shares = sharesValue === "" ? null : Number(sharesValue);
  const purchaseDate = document.getElementById("position-purchase-date").value;
  const sources = positionSourceNames(document.getElementById("position-source").value);
  const customTargets = [1, 2, 3].map((index) => {
    const value = document.getElementById(`position-target-${index}`).value;
    return value === "" ? null : Number(value);
  });
  if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) return setPositionFormStatus("Enter a valid ticker.", "error");
  if (!sharedMarketSecurities[ticker]) return setPositionFormStatus(`${ticker} is not in the current shared market feed, so an automatically updated position cannot be created.`, "error");
  if (!(buyPrice > 0) || (shares !== null && !(shares > 0)) || !purchaseDate) return setPositionFormStatus("Buy price and purchase date are required; shares, when entered, must be greater than zero.", "error");
  if (purchaseDate > new Date().toISOString().slice(0, 10)) return setPositionFormStatus("Purchase date cannot be in the future.", "error");
  if (customTargets.some((value) => value !== null && (!(value > 0) || value <= buyPrice))) return setPositionFormStatus("Custom profit targets must be above the average buy price.", "error");
  const originalTicker = normalizedTicker(form.dataset.editingTicker);
  const pendingOrderTicker = normalizedTicker(form.dataset.pendingOrderTicker);
  const existingIndex = positionState.positions.findIndex((item) => normalizedTicker(item.ticker) === (originalTicker || ticker));
  const record = { ticker, company: form.dataset.company || positionCompany(ticker, currentDashboardData), buy_price: buyPrice,
    shares, purchase_date: purchaseDate, strategy_sources: sources, domain: form.dataset.domain || sharedMarketSecurities[ticker]?.domains?.[0] || "ai",
    custom_targets: customTargets, updated_at: new Date().toISOString() };
  if (existingIndex >= 0) positionState.positions[existingIndex] = record; else positionState.positions.push(record);
  writePositionState(); renderPositions(currentDashboardData);
  if (pendingOrderTicker) removePendingOrder(pendingOrderTicker, false);
  setPositionFormStatus(`${ticker} position ${existingIndex >= 0 ? "updated" : "added"}. Daily data will refresh its market and technical analysis without deleting the position.`, "success");
  resetPositionForm();
}

function removePosition(ticker) {
  const key = normalizedTicker(ticker);
  if (!window.confirm(`Remove the owned ${key} position from My Stock?`)) return;
  positionState.positions = positionState.positions.filter((item) => normalizedTicker(item.ticker) !== key);
  writePositionState(); renderPositions(currentDashboardData);
  setPositionFormStatus(`${key} was removed from My Stock.`, "success");
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
    watchlistState.manual_items.push({ ticker: key, company: company || key, domain: domain || "ai",
      reason: "Personally selected for active technical monitoring.", validation_status: "pending-market-data",
      added_at: new Date().toISOString() });
    writeWatchlistState();
    setWatchlistStatus(`${key} was saved to Manually Entered, but it is outside today's static shared market-data file. Validation, price history, and technical analysis remain pending; no quote was fabricated.`, "error");
    refreshWatchlistUi();
    return true;
  }
  const resolvedDomain = domain || snapshot.domains?.[0] || "ai";
  watchlistState.manual_items.push({ ticker: key, company: company || key, domain: resolvedDomain,
    reason: "Manually selected for active technical monitoring.",
    validation_status: "validated-shared-market-data",
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
  const tickerAnchor = event.target.closest("a.ticker-link");
  if (tickerAnchor) {
    event.stopPropagation();
    return;
  }
  const pendingPrefill = event.target.closest("[data-pending-order-prefill]");
  if (pendingPrefill) {
    event.preventDefault(); event.stopPropagation();
    prefillPendingOrderForm(pendingPrefill.dataset.ticker);
    return;
  }
  const pendingEdit = event.target.closest("[data-pending-order-edit]");
  if (pendingEdit) {
    event.preventDefault(); event.stopPropagation();
    prefillPendingOrderForm(pendingEdit.dataset.ticker, true);
    return;
  }
  const pendingRemove = event.target.closest("[data-pending-order-remove]");
  if (pendingRemove) {
    event.preventDefault(); event.stopPropagation();
    removePendingOrder(pendingRemove.dataset.ticker);
    return;
  }
  const pendingFill = event.target.closest("[data-pending-order-fill]");
  if (pendingFill) {
    event.preventDefault(); event.stopPropagation();
    const key = normalizedTicker(pendingFill.dataset.ticker);
    const order = initializePendingOrderState().orders.find((item) => normalizedTicker(item.ticker) === key);
    if (order) prefillPositionForm({ ticker: key, company: order.company, domain: order.domain, sources: "Manual",
      buyPrice: order.limit_price, shares: order.shares, fromPending: true });
    return;
  }
  const positionPrefill = event.target.closest("[data-position-prefill]");
  if (positionPrefill) {
    event.preventDefault(); event.stopPropagation();
    prefillPositionForm({ ticker: positionPrefill.dataset.ticker, company: positionPrefill.dataset.company,
      domain: positionPrefill.dataset.domain, sources: positionPrefill.dataset.sources });
    return;
  }
  const positionEdit = event.target.closest("[data-position-edit]");
  if (positionEdit) {
    event.preventDefault(); event.stopPropagation();
    prefillPositionForm({ ticker: positionEdit.dataset.ticker, edit: true });
    return;
  }
  const positionRemove = event.target.closest("[data-position-remove]");
  if (positionRemove) {
    event.preventDefault(); event.stopPropagation();
    removePosition(positionRemove.dataset.ticker);
    return;
  }
  const addButton = event.target.closest("[data-watchlist-add]");
  if (addButton) {
    event.preventDefault(); event.stopPropagation();
    addWatchlistItem({ ticker: addButton.dataset.ticker, company: addButton.dataset.company,
      source: addButton.dataset.source, domain: addButton.dataset.domain });
    return;
  }
  const removeButton = event.target.closest("[data-watchlist-remove]");
  if (removeButton) { event.preventDefault(); event.stopPropagation(); removeWatchlistItem(removeButton.dataset.ticker); }
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

const radarAnalyzeForm = document.getElementById("radar-analyze-form");
if (radarAnalyzeForm) radarAnalyzeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const ticker = normalizedTicker(document.getElementById("radar-analyze-ticker")?.value);
  const status = document.getElementById("radar-analyze-status");
  if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) {
    status.textContent = "Enter a valid ticker using letters, numbers, a period, or a hyphen.";
    status.className = "radar-analyze-status is-error";
    document.getElementById("radar-analyze-result").hidden = true;
    return;
  }
  if (!currentDashboardData) {
    status.textContent = "Dashboard data is still loading. Try again after Last Updated appears.";
    status.className = "radar-analyze-status is-error";
    return;
  }
  renderRadarAnalysis(currentDashboardData, ticker, document.getElementById("radar-analyze-domain")?.value || "auto");
});

const pendingOrderForm = document.getElementById("pending-order-form");
if (pendingOrderForm) pendingOrderForm.addEventListener("submit", savePendingOrderForm);
const pendingOrderCancel = document.getElementById("pending-order-cancel");
if (pendingOrderCancel) pendingOrderCancel.addEventListener("click", () => {
  resetPendingOrderForm();
  setPendingOrderFormStatus("Pending-order edit cancelled.");
});

const positionForm = document.getElementById("position-form");
if (positionForm) positionForm.addEventListener("submit", savePositionForm);
const positionCancel = document.getElementById("position-cancel");
if (positionCancel) positionCancel.addEventListener("click", () => {
  resetPositionForm();
  setPositionFormStatus("Position edit cancelled. Enter an owned position directly, or move one from Watchlist.");
});

function renderDashboard(data) {
  if (!data || typeof data !== "object") throw new Error("Dashboard JSON is not an object.");
  currentDashboardData = data;
  sharedMarketSecurities = data.market_data?.securities || {};
  initializeWatchlistState(data);
  initializePendingOrderState();
  initializePositionState();
  if (!document.getElementById("position-purchase-date")?.value) resetPositionForm();
  const updated = new Date(data.updated_at);
  setText("last-updated", Number.isNaN(updated.valueOf()) ? data.updated_at : updated.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }));
  setText("market-data-through", formatMarketDataThrough(data.market_data_through || data.market_data?.data_through));
  setText("ai-news-summary-copy", data.summaries && data.summaries.ai);
  setText("biotech-news-summary-copy", data.summaries && data.summaries.biotech);
  setText("ai-summary", data.summaries && data.summaries.ai); setText("biotech-summary", data.summaries && data.summaries.biotech); setText("crypto-summary", data.summaries && data.summaries.crypto); setText("market-movers", data.summaries && data.summaries.market_movers);
  renderDashboardCommentary(data.commentary);
  renderSafely(() => renderTopNews(data.top_investment_news && data.top_investment_news.ai_technology), "ai-top-news");
  renderSafely(() => renderBiotechNews(data.top_investment_news && data.top_investment_news.biotech_healthcare), "biotech-top-news");
  renderSafely(() => renderAiReaccelerationAlerts(data.radar && data.radar.ai_reacceleration_alerts), "ai-reacceleration-alerts");
  renderSafely(() => renderAiRadar(aiRadarRows(data)), "ai-radar");
  renderSafely(() => renderBiotechRadar(biotechRadarRows(data)), "biotech-radar");
  renderSafely(() => renderCryptoRadar(cryptoRadarRows(data)), "crypto-radar");
  renderSafely(() => renderOpportunities("ai-opportunities", qualifiedHighConvictionRows(data, "ai")), "ai-opportunities");
  renderSafely(() => renderOpportunities("biotech-opportunities", qualifiedHighConvictionRows(data, "biotech")), "biotech-opportunities");
  renderSafely(() => renderSwingTrades(data.swing_trade_opportunities), "swing-opportunities");
  renderSafely(() => renderWatchlist(data), "my-watchlist");
  renderSafely(() => renderPendingOrders(), "pending-order-cards");
  renderSafely(() => renderPositions(data), "my-stock-positions");
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
  setText("market-data-through", "Unavailable");
  document.querySelectorAll(".loading-state").forEach((element) => { element.textContent = "The daily data feed could not be loaded. Please try again shortly."; });
  console.error("GeneDr Investment Intelligence dashboard:", error);
});
