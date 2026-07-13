(function () {
  const categories = [
    "All",
    "Clinical Case",
    "Genetic Testing",
    "Disease Spotlight",
    "Drug Spotlight",
    "Gene Detective Story",
    "Guideline Update",
    "AI in Genetics",
    "Movie",
    "Music & Arts"
  ];

  const escapeHtml = (value = "") => String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  const formatDate = (date) => {
    if (!date) return "Date not set";
    const parts = String(date).split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return String(date);
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric"
    }).format(new Date(parts[0], parts[1] - 1, parts[2]));
  };

  const normalizeIssue = (issue) => ({
    ...issue,
    subtitle: issue.subtitle || "",
    excerpt: issue.excerpt || issue.description || "",
    articleSections: issue.articleSections || issue.sections || {},
    keyPoints: issue.keyPoints || issue.sections?.keyPoints || [],
    references: issue.references || issue.sections?.references || [],
    disclaimer: issue.disclaimer || "The clinical scenario is fictional and created for educational purposes. It does not represent an actual patient.",
    status: issue.status || (issue.published ? "published" : "draft")
  });

  const allIssues = (window.GENEDR_WEEKLY_ISSUES || []).map(normalizeIssue);
  const issues = allIssues
    .filter((issue) => issue.status === "published")
    .sort((a, b) => new Date(b.date) - new Date(a.date));

  const issueLabel = (number) => `Issue #${String(number).padStart(3, "0")}`;
  const articleUrl = (issue, prefix = "") =>
    `${prefix}genedr-weekly/article.html?issue=${encodeURIComponent(issue.slug)}`;

  function renderHomepage() {
    const target = document.querySelector("#weekly-feature");
    if (!target || !issues.length) return;
    const issue = issues[0];

    target.innerHTML = `
      <div class="weekly-card">
        <div class="weekly-intro">
          <p class="weekly-wordmark" aria-label="GeneDr Weekly"><span>GeneDr</span> <em>Weekly</em></p>
          <h2 id="weekly-section-title">Discover Genetics, One Story at a Time.</h2>
          <p class="weekly-tagline">Five minutes of enjoyable genetics reading every week.</p>
          <p class="weekly-meta">${issueLabel(issue.issueNumber)} <span>•</span> ${escapeHtml(formatDate(issue.date))} <span>•</span> ${escapeHtml(issue.readingTime)}</p>
          <span class="weekly-category">${escapeHtml(issue.category)}</span>
        </div>
        <div class="weekly-story">
          <p class="weekly-overline">Featured Article of the Week</p>
          <h3>${escapeHtml(issue.title)}</h3>
          <div class="weekly-scenario">
            <strong>Clinical Scenario</strong>
            <p><em>${escapeHtml(issue.scenario)}</em></p>
            <p class="weekly-question">${escapeHtml(issue.question)}</p>
          </div>
          <div class="weekly-actions">
            <a class="weekly-button weekly-button-primary" href="${articleUrl(issue)}">Read This Week's Story</a>
            <a class="weekly-button weekly-button-secondary" href="genedr-weekly/archive.html">Browse All Issues</a>
          </div>
        </div>
      </div>`;
  }

  function archiveCard(issue) {
    return `
      <a class="weekly-archive-card" href="article.html?issue=${encodeURIComponent(issue.slug)}">
        <div class="weekly-archive-meta">
          <span>${issueLabel(issue.issueNumber)}</span><span>${escapeHtml(formatDate(issue.date))}</span>
        </div>
        <h2>${escapeHtml(issue.title)}</h2>
        <p>${escapeHtml(issue.excerpt)}</p>
        <div class="weekly-archive-footer">
          <span class="weekly-category">${escapeHtml(issue.category)}</span>
          <span>${escapeHtml(issue.readingTime)} <b aria-hidden="true">→</b></span>
        </div>
      </a>`;
  }

  function renderArchive() {
    const target = document.querySelector("#weekly-archive-list");
    const filters = document.querySelector("#weekly-archive-filters");
    if (!target) return;

    const showCategory = (category) => {
      const visibleIssues = category === "All"
        ? issues
        : issues.filter((issue) => issue.category === category);
      target.innerHTML = visibleIssues.length
        ? visibleIssues.map(archiveCard).join("")
        : `<p class="weekly-archive-empty">No published issues in this category yet.</p>`;
      filters?.querySelectorAll("button").forEach((button) => {
        const selected = button.dataset.category === category;
        button.classList.toggle("is-active", selected);
        button.setAttribute("aria-pressed", String(selected));
      });
    };

    if (filters) {
      filters.innerHTML = categories.map((category) =>
        `<button type="button" data-category="${escapeHtml(category)}" aria-pressed="false">${escapeHtml(category)}</button>`
      ).join("");
      filters.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-category]");
        if (button) showCategory(button.dataset.category);
      });
    }
    showCategory("All");
  }

  function copyText(text) {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
    const input = document.createElement("textarea");
    input.value = text;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
    return Promise.resolve();
  }

  function setupSharing(issue) {
    const actions = document.querySelector("#weekly-share-actions");
    if (!actions) return;
    const pageUrl = window.location.href;
    const subject = `GeneDr Weekly Issue #${issue.issueNumber}: ${issue.title}`;
    const body = `I thought you might be interested in this GeneDr Weekly story:\n\n${issue.title}\n\nIssue #${issue.issueNumber} | ${formatDate(issue.date)}\n\nDiscover Genetics, One Story at a Time.\n\nRead the full story here:\n${pageUrl}`;
    const email = actions.querySelector("[data-share=email]");
    const share = actions.querySelector("[data-share=native]");
    const copy = actions.querySelector("[data-share=copy]");
    const status = actions.querySelector("[data-share-status]");
    email.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

    if (!navigator.share) share.hidden = true;
    share.addEventListener("click", async () => {
      try {
        await navigator.share({ title: subject, text: issue.excerpt, url: pageUrl });
      } catch (error) {
        if (error.name !== "AbortError") status.textContent = "Sharing is unavailable. Please use Email or Copy Link.";
      }
    });
    copy.addEventListener("click", async () => {
      try {
        await copyText(pageUrl);
        status.textContent = "Link copied";
      } catch (error) {
        status.textContent = "Could not copy the link.";
      }
    });
  }

  function renderArticle() {
    const target = document.querySelector("#weekly-article");
    if (!target) return;
    const slug = new URLSearchParams(window.location.search).get("issue");
    const issue = issues.find((item) => item.slug === slug) || issues[0];
    if (!issue) return;
    document.title = `${issue.title} | GeneDr Weekly`;
    target.innerHTML = `
      <nav class="weekly-article-links" aria-label="Article links">
        <a class="back-link" href="../index.html">← Back to Home</a>
        <a class="back-link" href="archive.html">Browse All Issues →</a>
      </nav>
      <header class="weekly-article-header">
        <p class="weekly-wordmark" aria-label="GeneDr Weekly"><span>GeneDr</span> <em>Weekly</em></p>
        <p class="weekly-article-deck">Discover Genetics, One Story at a Time.</p>
        <p class="weekly-tagline">Five minutes of enjoyable genetics reading every week.</p>
        <div class="weekly-article-meta">
          <span>${issueLabel(issue.issueNumber)} <b>•</b> ${escapeHtml(formatDate(issue.date))} <b>•</b> ${escapeHtml(issue.readingTime)}</span>
          <span class="weekly-category">${escapeHtml(issue.category)}</span>
        </div>
        <h1>${escapeHtml(issue.title)}</h1>
        ${issue.subtitle ? `<p class="weekly-article-subtitle">${escapeHtml(issue.subtitle)}</p>` : ""}
      </header>
      <div id="weekly-share-actions" class="weekly-share-actions" aria-label="Share this article">
        <a class="weekly-button weekly-button-secondary" data-share="email" href="#">Email This Story</a>
        <button class="weekly-button weekly-button-primary" data-share="native" type="button">Share This Story</button>
        <button class="weekly-button weekly-button-secondary" data-share="copy" type="button">Copy Link</button>
        <span class="weekly-share-status" data-share-status role="status" aria-live="polite"></span>
      </div>
      <section><h2>Clinical Scenario</h2><p><em>${escapeHtml(issue.scenario)}</em></p><p><strong>${escapeHtml(issue.question)}</strong></p></section>
      <section><h2>Why This Matters</h2><p>${escapeHtml(issue.articleSections.whyThisMatters || "")}</p></section>
      <section><h2>Main Article</h2><p>${escapeHtml(issue.articleSections.mainArticle || "")}</p></section>
      <section><h2>Key Points</h2><ul>${issue.keyPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul></section>
      <section><h2>References</h2><ol>${issue.references.map((reference) => `<li>${escapeHtml(reference)}</li>`).join("")}</ol></section>
      <p class="weekly-disclaimer"><em>${escapeHtml(issue.disclaimer)}</em></p>`;
    setupSharing(issue);
  }

  window.GeneDrWeekly = {
    categories,
    escapeHtml,
    formatDate,
    normalizeIssue,
    issueLabel,
    getPublishedIssues: () => issues.map((issue) => ({ ...issue }))
  };
  renderHomepage();
  renderArchive();
  renderArticle();
})();
