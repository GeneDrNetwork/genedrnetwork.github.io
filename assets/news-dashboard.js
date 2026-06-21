const DATA_URL = "../data/news-dashboard.json";

const escapeHtml = (value = "") => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const safeUrl = (value = "") => { try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : "#"; } catch { return "#"; } };
const setText = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = value || "No update available."; };
const title = (key) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function download(name, content, type) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type }));
  link.download = name;
  document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(link.href);
}

function makeTable(targetId, rows = [], columns, options = {}) {
  const target = document.getElementById(targetId);
  if (!target) return;
  const tableId = `${targetId}-grid`;
  const filters = ["market_cap", "sector", "risk", "growth_potential"].filter((key) => rows.some((row) => row[key]));
  target.innerHTML = `<div class="data-tools">
    <label class="search-control"><span>Search</span><input type="search" placeholder="Filter companies" data-search /></label>
    ${filters.map((key) => `<label><span>${title(key)}</span><select data-filter="${key}"><option value="">All</option>${[...new Set(rows.map((row) => row[key]).filter(Boolean))].sort().map((value) => `<option>${escapeHtml(value)}</option>`).join("")}</select></label>`).join("")}
    <div class="export-buttons"><button type="button" data-export="csv">Export CSV</button><button type="button" data-export="xls">Export Excel</button></div>
  </div><div class="table-wrap"><table id="${tableId}"><thead><tr>${columns.map((column) => `<th><button type="button" data-sort="${column.key}">${escapeHtml(column.label)}<span aria-hidden="true">↕</span></button></th>`).join("")}</tr></thead><tbody></tbody></table></div>`;

  let view = [...rows]; let sortKey = options.defaultSort || ""; let direction = 1;
  const tbody = target.querySelector("tbody");
  const cell = (row, column) => {
    const value = row[column.key] ?? "—";
    if (column.link && row.url) return `<a class="news-source" href="${safeUrl(row.url)}" target="_blank" rel="noopener">${escapeHtml(value)} ↗</a>`;
    if (column.badge) return `<span class="data-badge ${String(value).toLowerCase()}">${escapeHtml(value)}</span>`;
    return escapeHtml(value);
  };
  const render = () => { tbody.innerHTML = view.map((row) => `<tr>${columns.map((column) => `<td>${cell(row, column)}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${columns.length}">No matching companies.</td></tr>`; };
  const apply = () => {
    const query = target.querySelector("[data-search]").value.toLowerCase();
    view = rows.filter((row) => (!query || Object.values(row).join(" ").toLowerCase().includes(query)) && filters.every((key) => {
      const selected = target.querySelector(`[data-filter="${key}"]`).value; return !selected || row[key] === selected;
    }));
    if (sortKey) view.sort((a, b) => String(a[sortKey] ?? "").localeCompare(String(b[sortKey] ?? ""), undefined, { numeric: true }) * direction);
    render();
  };
  target.querySelectorAll("input, select").forEach((control) => control.addEventListener("input", apply));
  target.querySelectorAll("[data-sort]").forEach((button) => button.addEventListener("click", () => { direction = sortKey === button.dataset.sort ? -direction : 1; sortKey = button.dataset.sort; apply(); }));
  target.querySelectorAll("[data-export]").forEach((button) => button.addEventListener("click", () => {
    const values = [columns.map((column) => column.label), ...view.map((row) => columns.map((column) => row[column.key] ?? ""))];
    if (button.dataset.export === "csv") download(`${targetId}.csv`, values.map((line) => line.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n"), "text/csv;charset=utf-8");
    else download(`${targetId}.xls`, `<table>${values.map((line) => `<tr>${line.map((value) => `<td>${escapeHtml(value)}</td>`).join("")}</tr>`).join("")}</table>`, "application/vnd.ms-excel");
  }));
  apply();
}

const leaderColumns = [
  { key: "company", label: "Company" }, { key: "ticker", label: "Ticker" }, { key: "sector", label: "Sector" },
  { key: "role", label: "AI Demand Exposure" }, { key: "market_cap", label: "Market Cap" }, { key: "growth_potential", label: "Growth Potential", badge: true }
];
const emergingAiColumns = [
  { key: "rank", label: "Rank" }, { key: "company", label: "Company" }, { key: "sector", label: "Sector" },
  { key: "thesis", label: "Investment Thesis" }, { key: "market_cap", label: "Market Cap" }, { key: "growth_potential", label: "Growth Potential", badge: true }, { key: "risk", label: "Risk", badge: true }
];
const biotechLeaderColumns = [
  { key: "company", label: "Company" }, { key: "ticker", label: "Ticker" }, { key: "sector", label: "Focus" },
  { key: "proven_therapy", label: "Proven Therapies" }, { key: "pipeline", label: "Pipeline" }, { key: "market_cap", label: "Market Cap" }, { key: "growth_potential", label: "Growth Potential", badge: true }
];
const emergingBioColumns = [
  { key: "rank", label: "Rank" }, { key: "company", label: "Company" }, { key: "technology", label: "Technology" },
  { key: "lead_programs", label: "Lead Programs" }, { key: "catalysts", label: "Catalysts" }, { key: "market_cap", label: "Market Cap" }, { key: "growth_potential", label: "Growth Potential", badge: true }, { key: "risk", label: "Risk", badge: true }
];
const watchColumns = [
  { key: "company", label: "Company" }, { key: "ticker", label: "Ticker" }, { key: "sector", label: "Sector" }, { key: "market_cap", label: "Market Cap" },
  { key: "why", label: "Why It Is Tracked" }, { key: "catalyst", label: "Upcoming Catalyst" }, { key: "growth_potential", label: "Growth Potential", badge: true }, { key: "risk", label: "Risk", badge: true }
];
const pickColumns = [
  { key: "rank", label: "#" }, { key: "company", label: "Company" }, { key: "thesis", label: "Investment Thesis" },
  { key: "catalyst", label: "Near-Term Catalyst" }, { key: "opportunity", label: "Long-Term Opportunity" }, { key: "risk", label: "Risk", badge: true }
];

function changeClass(value) { const number = Number.parseFloat(value); return number > 0 ? "change-up" : number < 0 ? "change-down" : "change-flat"; }
function formatChange(value) { const number = Number.parseFloat(value); return Number.isFinite(number) ? `${number > 0 ? "+" : ""}${number.toFixed(2)}%` : "N/A"; }
function renderMarkets(markets = []) { document.getElementById("market-cards").innerHTML = markets.map((market) => `<article class="market-card"><h3>${escapeHtml(market.name)}</h3><span class="market-value">${escapeHtml(market.value)}</span><span class="${changeClass(market.daily)}">${formatChange(market.daily)} today</span><div class="market-periods"><span>Weekly<strong class="${changeClass(market.weekly)}">${formatChange(market.weekly)}</strong></span><span>Monthly<strong class="${changeClass(market.monthly)}">${formatChange(market.monthly)}</strong></span></div></article>`).join(""); }
function renderDemand(items = []) { document.getElementById("demand-map").innerHTML = items.map((item) => `<article class="demand-card"><span>${escapeHtml(item.rank)}</span><h4>${escapeHtml(item.area)}</h4><p>${escapeHtml(item.why)}</p><dl><dt>Public leaders</dt><dd>${escapeHtml(item.public_companies)}</dd><dt>Emerging</dt><dd>${escapeHtml(item.emerging_companies)}</dd></dl></article>`).join(""); }

function renderDashboard(data) {
  const updated = new Date(data.updated_at);
  setText("last-updated", Number.isNaN(updated.valueOf()) ? data.updated_at : updated.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }));
  setText("ai-summary", data.summaries.ai); setText("market-summary", data.summaries.market); setText("biotech-summary", data.summaries.biotech); setText("market-movers", data.summaries.market_movers);
  document.getElementById("key-takeaways").innerHTML = data.takeaways.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  makeTable("ai-infrastructure", data.ai.infrastructure_leaders, leaderColumns);
  makeTable("ai-platforms", data.ai.platform_leaders, leaderColumns);
  makeTable("ai-emerging", data.ai.emerging, emergingAiColumns, { defaultSort: "rank" });
  renderDemand(data.ai.demand_drivers);
  makeTable("biotech-leaders", data.biotech.leaders, biotechLeaderColumns);
  makeTable("biotech-emerging", data.biotech.emerging, emergingBioColumns, { defaultSort: "rank" });
  makeTable("ai-watchlist", data.watchlists.ai, watchColumns); makeTable("biotech-watchlist", data.watchlists.biotech, watchColumns);
  makeTable("ai-picks", data.monthly_picks.ai, pickColumns, { defaultSort: "rank" }); makeTable("biotech-picks", data.monthly_picks.biotech, pickColumns, { defaultSort: "rank" });
  makeTable("fda-table", data.fda, [{ key: "company", label: "Company" }, { key: "product", label: "Product" }, { key: "indication", label: "Indication" }, { key: "event", label: "Regulatory Event", link: true }, { key: "date", label: "Date" }]);
  renderMarkets(data.markets);
}

fetch(DATA_URL, { cache: "no-store" }).then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); }).then(renderDashboard).catch((error) => {
  setText("last-updated", "Dashboard temporarily unavailable"); setText("ai-summary", "The daily data feed could not be loaded. Please try again shortly."); console.error("GeneDr News dashboard:", error);
});
