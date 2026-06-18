const DATA_URL = "../data/news-dashboard.json";

const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

const safeUrl = (value = "") => {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch { return "#"; }
};

const setText = (id, value) => {
  const element = document.getElementById(id);
  if (element) element.textContent = value || "No update available.";
};

function changeClass(value) {
  const number = Number.parseFloat(value);
  if (number > 0) return "change-up";
  if (number < 0) return "change-down";
  return "change-flat";
}

function formatChange(value) {
  const number = Number.parseFloat(value);
  if (!Number.isFinite(number)) return "N/A";
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function renderEntities(id, entities) {
  const container = document.getElementById(id);
  if (!container) return;
  container.innerHTML = entities.map((entity) => {
    const details = Object.entries(entity.details || {}).map(([label, value]) =>
      `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join("");
    const news = entity.news || {};
    return `<article class="entity-card">
      <div class="entity-top"><h4>${escapeHtml(entity.name)}</h4><span class="entity-badge">${escapeHtml(entity.status || entity.ticker || "Tracked")}</span></div>
      <p class="entity-meta">${escapeHtml(entity.focus || entity.platform || "Industry intelligence")}</p>
      <dl>${details}<dt>Latest</dt><dd><a class="news-source" href="${safeUrl(news.url)}" target="_blank" rel="noopener">${escapeHtml(news.title || "View latest coverage")} ↗</a></dd></dl>
    </article>`;
  }).join("");
}

function renderMarkets(markets) {
  const container = document.getElementById("market-cards");
  container.innerHTML = markets.map((market) => `<article class="market-card">
    <h3>${escapeHtml(market.name)}</h3><span class="market-value">${escapeHtml(market.value)}</span>
    <span class="${changeClass(market.daily)}">${formatChange(market.daily)} today</span>
    <div class="market-periods"><span>Weekly<strong class="${changeClass(market.weekly)}">${formatChange(market.weekly)}</strong></span><span>Monthly<strong class="${changeClass(market.monthly)}">${formatChange(market.monthly)}</strong></span></div>
  </article>`).join("");
}

function renderFda(items) {
  document.getElementById("fda-updates").innerHTML = items.map((item) => `<tr>
    <td>${escapeHtml(item.company)}</td><td>${escapeHtml(item.product)}</td><td>${escapeHtml(item.indication)}</td>
    <td>${escapeHtml(item.event)}</td><td>${escapeHtml(item.date)}</td><td><a class="news-source" href="${safeUrl(item.url)}" target="_blank" rel="noopener">Source ↗</a></td>
  </tr>`).join("") || '<tr><td colspan="6">No new regulatory items were found in today\'s feeds.</td></tr>';
}

function renderWatchlist(items) {
  document.getElementById("watchlist-rows").innerHTML = items.map((item) => `<tr>
    <td class="ticker">${escapeHtml(item.ticker)}</td><td>${escapeHtml(item.company)}</td><td>${escapeHtml(item.price)}</td>
    <td class="${changeClass(item.daily)}">${formatChange(item.daily)}</td><td class="${changeClass(item.weekly)}">${formatChange(item.weekly)}</td>
    <td><a class="news-source" href="${safeUrl(item.news?.url)}" target="_blank" rel="noopener">${escapeHtml(item.news?.title || "Latest coverage")} ↗</a><br>${escapeHtml(item.summary || "Monitored for material developments.")}</td>
  </tr>`).join("");
}

function renderOpportunities(items) {
  document.getElementById("opportunity-grid").innerHTML = items.map((item) => `<article class="opportunity-card">
    <div class="score-row"><h3>${escapeHtml(item.company)}</h3><span class="score">${escapeHtml(item.score)}/10</span></div>
    <span class="risk">${escapeHtml(item.risk)} risk</span>
    <p><strong>Growth potential:</strong> ${escapeHtml(item.potential)}</p><p><strong>Upcoming catalyst:</strong> ${escapeHtml(item.catalyst)}</p>
    <a class="news-source" href="${safeUrl(item.url)}" target="_blank" rel="noopener">Supporting news ↗</a>
  </article>`).join("");
}

function renderDashboard(data) {
  const updated = new Date(data.updated_at);
  setText("last-updated", Number.isNaN(updated.valueOf()) ? data.updated_at : updated.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }));
  setText("ai-summary", data.summaries.ai);
  setText("market-summary", data.summaries.market);
  setText("biotech-summary", data.summaries.biotech);
  setText("market-movers", data.summaries.market_movers);
  document.getElementById("key-takeaways").innerHTML = data.takeaways.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  renderEntities("ai-leaders", data.ai.leaders);
  renderEntities("ai-emerging", data.ai.emerging);
  renderEntities("biotech-leaders", data.biotech.leaders);
  renderEntities("biotech-emerging", data.biotech.emerging);
  renderFda(data.fda);
  renderMarkets(data.markets);
  renderWatchlist(data.watchlist);
  renderOpportunities(data.opportunities);
}

fetch(DATA_URL, { cache: "no-store" })
  .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
  .then(renderDashboard)
  .catch((error) => {
    setText("last-updated", "Dashboard temporarily unavailable");
    setText("ai-summary", "The daily data feed could not be loaded. Please try again shortly.");
    console.error("GeneDrNews dashboard:", error);
  });
