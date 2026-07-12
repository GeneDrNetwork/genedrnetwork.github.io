(function () {
  const issues = (window.GENEDR_WEEKLY_ISSUES || [])
    .filter((issue) => issue.published)
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
          <p class="weekly-kicker">GeneDr Weekly</p>
          <h2 id="weekly-section-title">Discover Genetics, One Story at a Time.</h2>
          <p class="weekly-tagline">Five minutes of enjoyable genetics reading every week.</p>
          <p class="weekly-meta">${issueLabel(issue.issueNumber)} <span>•</span> ${issue.dateLabel} <span>•</span> ${issue.readingTime}</p>
          <span class="weekly-category">${issue.category}</span>
        </div>
        <div class="weekly-story">
          <p class="weekly-overline">Featured This Week</p>
          <h3>${issue.title}</h3>
          <div class="weekly-scenario">
            <strong>Clinical Scenario</strong>
            <p><em>${issue.scenario}</em></p>
            <p class="weekly-question">${issue.question}</p>
          </div>
          <div class="weekly-actions">
            <a class="weekly-button weekly-button-primary" href="${articleUrl(issue)}">Read This Week's Story</a>
            <a class="weekly-button weekly-button-secondary" href="genedr-weekly/archive.html">Browse All Issues</a>
          </div>
        </div>
      </div>`;
  }

  function renderArchive() {
    const target = document.querySelector("#weekly-archive-list");
    if (!target) return;
    target.innerHTML = issues.map((issue) => `
      <a class="weekly-archive-card" href="article.html?issue=${encodeURIComponent(issue.slug)}">
        <div class="weekly-archive-meta">
          <span>${issueLabel(issue.issueNumber)}</span><span>${issue.dateLabel}</span>
        </div>
        <h2>${issue.title}</h2>
        <p>${issue.description}</p>
        <div class="weekly-archive-footer">
          <span class="weekly-category">${issue.category}</span>
          <span>${issue.readingTime} <b aria-hidden="true">→</b></span>
        </div>
      </a>`).join("");
  }

  function renderArticle() {
    const target = document.querySelector("#weekly-article");
    if (!target) return;
    const slug = new URLSearchParams(window.location.search).get("issue");
    const issue = issues.find((item) => item.slug === slug) || issues[0];
    if (!issue) return;
    document.title = `${issue.title} | GeneDr Weekly`;
    target.innerHTML = `
      <a class="back-link" href="../index.html">← Back to Home</a>
      <header class="weekly-article-header">
        <p class="weekly-kicker">GeneDr Weekly</p>
        <h1>${issue.title}</h1>
        <div class="weekly-article-meta">
          <span>${issueLabel(issue.issueNumber)}</span><span>${issue.dateLabel}</span>
          <span>${issue.readingTime}</span><span class="weekly-category">${issue.category}</span>
        </div>
      </header>
      <section><h2>Clinical Scenario</h2><p><em>${issue.scenario}</em></p><p><strong>${issue.question}</strong></p></section>
      <section><h2>Why This Matters</h2><p>${issue.sections.whyThisMatters}</p></section>
      <section><h2>Main Article</h2><p>${issue.sections.mainArticle}</p></section>
      <section><h2>Key Points</h2><ul>${issue.sections.keyPoints.map((point) => `<li>${point}</li>`).join("")}</ul></section>
      <section><h2>References</h2><ol>${issue.sections.references.map((reference) => `<li>${reference}</li>`).join("")}</ol></section>
      <p class="weekly-disclaimer"><em>The clinical scenario is fictional and created for educational purposes. It does not represent an actual patient.</em></p>`;
  }

  renderHomepage();
  renderArchive();
  renderArticle();
})();
