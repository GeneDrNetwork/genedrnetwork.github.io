(function () {
  "use strict";

  const data = window.GeneDrTherapeuticsData;
  if (!data) return;

  const escapeHtml = (value = "") => String(value)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  const safeUrl = (value = "") => {
    try {
      const url = new URL(value);
      return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
    } catch (_error) { return "#"; }
  };

  const externalLink = (url, label = "Learn More") =>
    `<a class="resource-link" href="${safeUrl(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}<span aria-hidden="true"> &nearr;</span></a>`;

  function renderFeaturedPicks() {
    document.getElementById("featured-period").textContent = data.featuredPeriod;
    document.getElementById("monthly-featured-picks").innerHTML = data.monthlyFeaturedPicks.map((item) => `
      <article class="resource-card featured-pick">
        <span class="resource-tag">${escapeHtml(item.type)}</span>
        <h3>${escapeHtml(item.product)}</h3>
        <p class="card-company">${escapeHtml(item.company)}</p>
        <dl><dt>Disease / indication</dt><dd>${escapeHtml(item.indication)}</dd></dl>
        <p>${escapeHtml(item.explanation)}</p>
        ${externalLink(item.url, "View source")}
      </article>`).join("");
  }

  function renderTable(columns, rows) {
    return `<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable therapy table">
      <table><thead><tr>${columns.map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((row) => `<tr>${row.map((cell, index) => `<${index ? "td" : "th"}${index ? "" : ' scope="row"'}>${escapeHtml(cell)}</${index ? "td" : "th"}>`).join("")}</tr>`).join("")}</tbody></table>
    </div>`;
  }

  function renderTherapeutics() {
    document.getElementById("therapeutics-categories").innerHTML = data.therapeuticsData.map((group, index) => `
      <details class="resource-accordion"${index === 0 ? " open" : ""}>
        <summary><span>${escapeHtml(group.category)}</span><span class="summary-count">${group.rows.length} conditions</span></summary>
        <div class="accordion-content">${renderTable(group.columns, group.rows)}</div>
      </details>`).join("");
  }

  function renderAccordionCards(id, items, type) {
    document.getElementById(id).innerHTML = items.map((item) => {
      const body = type === "company"
        ? `<dl><dt>Therapeutic area</dt><dd>${escapeHtml(item.area)}</dd><dt>Featured products</dt><dd>${escapeHtml(item.products)}</dd></dl>`
        : `<dl><dt>Testing focus</dt><dd>${escapeHtml(item.focus)}</dd><dt>Technology / platform</dt><dd>${escapeHtml(item.platform)}</dd></dl>`;
      return `<details class="resource-accordion compact-accordion"><summary>${escapeHtml(item.name)}</summary><div class="accordion-content">${body}<p>${escapeHtml(item.intro)}</p>${externalLink(item.url, "Official website")}</div></details>`;
    }).join("");
  }

  function renderCompanyDirectory() {
    const companies = [...data.companyList].sort((a, b) => a.name.localeCompare(b.name));
    const groups = companies.reduce((result, company) => {
      const letter = company.name.charAt(0).toUpperCase();
      if (!result[letter]) result[letter] = [];
      result[letter].push(company);
      return result;
    }, {});

    document.getElementById("company-directory-nav").innerHTML = Object.keys(groups)
      .map((letter) => `<a href="#company-${letter}" aria-label="Companies beginning with ${letter}">${letter}</a>`)
      .join("");

    document.getElementById("company-list").innerHTML = Object.entries(groups).map(([letter, companiesInGroup]) => `
      <section class="directory-letter-group" id="company-${letter}" aria-labelledby="company-${letter}-title">
        <h4 id="company-${letter}-title">${letter}</h4>
        <div class="accordion-grid">${companiesInGroup.map((company) => `
          <details class="resource-accordion compact-accordion company-card">
            <summary>${escapeHtml(company.name)}</summary>
            <div class="accordion-content">
              <p class="company-introduction">${escapeHtml(company.intro)}</p>
              <dl>
                <dt>Major therapeutic focus</dt><dd>${escapeHtml(company.area)}</dd>
                <dt>Key approved products</dt><dd>${escapeHtml(company.products)}</dd>
                <dt>Pipeline highlights</dt><dd>${escapeHtml(company.pipeline || `Clinical and research programs across ${company.area.toLowerCase()}; consult the official pipeline for current study status.`)}</dd>
              </dl>
              ${externalLink(company.url, "Official website")}
            </div>
          </details>`).join("")}
        </div>
      </section>`).join("");
  }

  function renderFdaTherapies() {
    const columns = ["Product", "Company", "Disease / indication", "Gene", "Therapy type", "FDA approval", "Source"];
    const rows = data.fdaApprovedTherapies.map((item) => [item.product, item.company, item.indication, item.gene, item.type, item.approval, externalLink(item.url, "FDA")]);
    const html = `<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable FDA-approved therapies table"><table><thead><tr>${columns.map((column) => `<th scope="col">${column}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell, index) => `<${index ? "td" : 'th scope="row"'}>${index === 6 ? cell : escapeHtml(cell)}</${index ? "td" : "th"}>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    document.getElementById("fda-approved-therapies").innerHTML = html;
    document.getElementById("fda-updated").textContent = data.fdaLastReviewed;
  }

  function setUpContactForm() {
    const form = document.getElementById("industry-contact-form");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const values = new FormData(form);
      const labels = { company: "Company", contact: "Contact", email: "Email", product: "Product / technology", area: "Disease / therapeutic area", description: "Brief description", website: "Website" };
      const body = Object.entries(labels).map(([key, label]) => `${label}: ${values.get(key) || "Not provided"}`).join("\n");
      const recipient = data.industryConnectionInfo.recipient;
      const subject = data.industryConnectionInfo.subject;
      document.getElementById("form-status").textContent = `Opening your email application to contact ${recipient}.`;
      window.location.href = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    });
  }

  renderFeaturedPicks();
  renderTherapeutics();
  renderCompanyDirectory();
  renderFdaTherapies();
  renderAccordionCards("technology-labs", data.technologyLabs, "lab");
  setUpContactForm();
}());
