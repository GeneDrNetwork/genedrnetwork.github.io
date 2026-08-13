(function () {
  const managerStorageKey = "genedr-monthly-manager-publications-v1";

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
      year: "numeric", month: "long", day: "numeric"
    }).format(new Date(parts[0], parts[1] - 1, parts[2]));
  };

  const formatMonthYear = (date) => {
    if (!date) return "Month not set";
    const parts = String(date).split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return String(date);
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric", month: "long"
    }).format(new Date(parts[0], parts[1] - 1, 1));
  };

  const issueLabel = (number) => `Issue #${String(number).padStart(3, "0")}`;
  const storyLabel = (number) => `Gene Detective Story #${String(number).padStart(3, "0")}`;
  const isMonthlyStory = (issue) => issue.publicationType === "gene-detective-story";

  const normalizeIssue = (issue) => ({
    ...issue,
    publicationType: issue.publicationType || "legacy-weekly",
    subtitle: issue.subtitle || "",
    teaser: issue.teaser || issue.excerpt || "",
    storyNumber: Number(issue.storyNumber || 0),
    storyContent: issue.storyContent || "",
    authorLine: issue.authorLine || "",
    excerpt: issue.excerpt || issue.description || "",
    articleSections: issue.articleSections || issue.sections || {},
    keyPoints: issue.keyPoints || issue.sections?.keyPoints || [],
    references: issue.references || issue.sections?.references || [],
    disclaimer: issue.disclaimer || "The clinical scenario is fictional and created for educational purposes. It does not represent an actual patient.",
    status: issue.status || (issue.published ? "published" : "draft")
  });

  const cleanHeading = (value) => String(value || "").replace(/^#{1,6}\s+/, "").trim();

  function looksLikeHeading(block) {
    const value = block.trim();
    if (!value || value.includes("\n") || value.length > 110) return false;
    if (/^(by|author|written by|edited by|edited and reviewed by)\s*[:—–-]?\s+/i.test(value)) return false;
    if (/^#{1,6}\s+/.test(value)) return true;
    if (/^(references|conclusion|discussion|the diagnosis|diagnostic journey|clinical clues?|genetic findings?|educational discussion|what happened next|the first clue|the next clue|the reveal|lessons? learned)\s*:?[\s]*$/i.test(value)) return true;
    if (/[.!?]$/.test(value)) return false;
    const words = value.replace(/[:—–-]$/, "").split(/\s+/);
    if (words.length > 12) return false;
    const significant = words.filter((word) => /[A-Za-z]/.test(word));
    const capitalized = significant.filter((word) => /^[A-Z0-9]/.test(word) || /^(a|an|and|as|at|by|for|from|in|of|on|or|the|to|with)$/i.test(word));
    return significant.length > 0 && capitalized.length / significant.length >= 0.8;
  }

  function truncate(value, maximum = 260) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (text.length <= maximum) return text;
    const shortened = text.slice(0, maximum + 1);
    return `${shortened.slice(0, shortened.lastIndexOf(" ")).replace(/[.,;:!?]+$/, "")}…`;
  }

  function parseStory(value) {
    const source = String(value || "").replace(/\r\n?/g, "\n").trim();
    const rawBlocks = source.split(/\n\s*\n/).map((block) => block.trim()).filter(Boolean);
    if (!rawBlocks.length) return { title: "", subtitle: "", teaser: "", authorLine: "", sections: [], source };

    const title = cleanHeading(rawBlocks[0].replace(/^title\s*:\s*/i, ""));
    let cursor = 1;
    let subtitle = "";
    if (rawBlocks[cursor] && !looksLikeHeading(rawBlocks[cursor]) && rawBlocks[cursor].length <= 180 && !/[.!?]$/.test(rawBlocks[cursor])) {
      subtitle = rawBlocks[cursor].replace(/^subtitle\s*:\s*/i, "").trim();
      cursor += 1;
    }

    const bodyBlocks = rawBlocks.slice(cursor);
    const authorBlock = bodyBlocks.find((block) => /^(by|author|written by|edited by|edited and reviewed by)\s*[:—–-]?\s+/i.test(block));
    const authorLine = authorBlock ? authorBlock.replace(/\s+/g, " ").trim() : "";
    const teaserBlock = bodyBlocks.find((block) => !looksLikeHeading(block) && block !== authorBlock) || "";
    const sections = [];
    let current = { heading: "", level: 2, blocks: [] };
    bodyBlocks.forEach((block) => {
      if (looksLikeHeading(block)) {
        if (current.heading || current.blocks.length) sections.push(current);
        const markdown = block.match(/^(#{1,6})\s+(.+)$/);
        current = {
          heading: cleanHeading(block),
          level: markdown ? Math.min(3, Math.max(2, markdown[1].length)) : 2,
          blocks: []
        };
      } else {
        current.blocks.push(block);
      }
    });
    if (current.heading || current.blocks.length) sections.push(current);
    return { title, subtitle, teaser: truncate(teaserBlock), authorLine, sections, source };
  }

  function renderStorySections(issue) {
    const parsed = parseStory(issue.storyContent);
    return parsed.sections.map((section) => {
      const heading = section.heading
        ? `<h${section.level}>${escapeHtml(section.heading)}</h${section.level}>`
        : "";
      const blocks = section.blocks.map((block) =>
        `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`
      ).join("");
      return `<section class="monthly-story-section${section.heading ? "" : " monthly-story-opening"}">${heading}${blocks}</section>`;
    }).join("");
  }

  function renderLegacyArticleText(value = "") {
    const output = [];
    let paragraph = [];
    const flush = () => {
      if (paragraph.length) output.push(`<p>${paragraph.map(escapeHtml).join(" ")}</p>`);
      paragraph = [];
    };
    String(value).split(/\r?\n/).forEach((line) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("### ")) {
        flush();
        output.push(`<h3>${escapeHtml(trimmed.slice(4))}</h3>`);
      } else if (!trimmed) flush();
      else paragraph.push(trimmed);
    });
    flush();
    return output.join("");
  }

  const repoIssues = (window.GENEDR_WEEKLY_ISSUES || []).map(normalizeIssue);
  let browserIssues = [];
  try {
    browserIssues = JSON.parse(localStorage.getItem(managerStorageKey) || "[]").map(normalizeIssue);
  } catch (error) {
    browserIssues = [];
  }
  const merged = new Map(repoIssues.map((issue) => [issue.slug, issue]));
  browserIssues.forEach((issue) => merged.set(issue.slug, issue));
  const allIssues = Array.from(merged.values()).sort((a, b) => new Date(b.date) - new Date(a.date));
  const published = allIssues.filter((issue) => issue.status === "published");
  const monthlyStories = published.filter(isMonthlyStory).sort((a, b) => new Date(b.date) - new Date(a.date));
  const legacyIssues = published.filter((issue) => !isMonthlyStory(issue)).sort((a, b) => new Date(b.date) - new Date(a.date));

  const articleUrl = (issue, prefix = "") => `${prefix}genedr-weekly/article.html?issue=${encodeURIComponent(issue.slug)}`;

  function renderHomepage() {
    const target = document.querySelector("#weekly-feature");
    if (!target) return;
    const issue = monthlyStories[0];
    const rightPanel = issue ? `
      <p class="weekly-overline">GeneDr Monthly</p>
      <span class="weekly-category">${escapeHtml(storyLabel(issue.storyNumber))}</span>
      <h3>${escapeHtml(issue.title)}</h3>
      <div class="weekly-scenario monthly-feature-teaser">
        <strong>Featured Story</strong>
        <p>${escapeHtml(issue.teaser || parseStory(issue.storyContent).teaser)}</p>
      </div>
      <div class="weekly-actions">
        <a class="weekly-button weekly-button-primary" href="${articleUrl(issue)}">Read the Story <span aria-hidden="true">→</span></a>
        <a class="weekly-button weekly-button-secondary" href="genedr-weekly/archive.html">Previous Stories</a>
      </div>` : `
      <p class="weekly-overline">GeneDr Monthly</p>
      <span class="weekly-category">Gene Detective Story</span>
      <h3>The first monthly story is coming soon.</h3>
      <div class="weekly-scenario monthly-feature-teaser">
        <strong>Previous Publication</strong>
        <p>The original GeneDr Weekly article remains available in the publication archive.</p>
      </div>
      <div class="weekly-actions"><a class="weekly-button weekly-button-secondary" href="genedr-weekly/archive.html">View Archive</a></div>`;

    target.innerHTML = `<div class="weekly-card">
      <div class="weekly-intro">
        <p class="weekly-wordmark" aria-label="GeneDr Monthly"><span>GeneDr</span> <em>Monthly</em></p>
        <h2 id="weekly-section-title">Gene Detective Story</h2>
        <p class="weekly-tagline">Discover Genetics, One story at a time.</p>
        ${issue ? `<p class="weekly-meta">${escapeHtml(issue.monthYear || formatMonthYear(issue.date))} <span>•</span> ${escapeHtml(storyLabel(issue.storyNumber))}</p>` : ""}
      </div>
      <div class="weekly-story">${rightPanel}</div>
    </div>`;
  }

  function monthlyArchiveCard(issue) {
    return `<a class="weekly-archive-card" href="article.html?issue=${encodeURIComponent(issue.slug)}">
      <div class="weekly-archive-meta"><span>${escapeHtml(storyLabel(issue.storyNumber))}</span><span>${escapeHtml(issue.monthYear || formatMonthYear(issue.date))}</span></div>
      <h2>${escapeHtml(issue.title)}</h2>
      <p>${escapeHtml(issue.teaser || parseStory(issue.storyContent).teaser)}</p>
      <div class="weekly-archive-footer"><span class="weekly-category">Gene Detective Story</span><span>${escapeHtml(formatDate(issue.date))} <b aria-hidden="true">→</b></span></div>
    </a>`;
  }

  function legacyArchiveCard(issue) {
    return `<a class="weekly-archive-card weekly-archive-card-legacy" href="article.html?issue=${encodeURIComponent(issue.slug)}">
      <div class="weekly-archive-meta"><span>Legacy GeneDr Weekly · ${escapeHtml(issueLabel(issue.issueNumber))}</span><span>${escapeHtml(formatDate(issue.date))}</span></div>
      <h2>${escapeHtml(issue.title)}</h2>
      <p>${escapeHtml(issue.excerpt)}</p>
      <div class="weekly-archive-footer"><span class="weekly-category">Previous Publication</span><span>Read article <b aria-hidden="true">→</b></span></div>
    </a>`;
  }

  function renderArchive() {
    const target = document.querySelector("#weekly-archive-list");
    if (!target) return;
    target.innerHTML = `
      <section class="monthly-archive-group" aria-labelledby="monthly-stories-heading">
        <h2 id="monthly-stories-heading">Previous Stories</h2>
        <div class="weekly-archive-list">${monthlyStories.length ? monthlyStories.map(monthlyArchiveCard).join("") : '<p class="weekly-archive-empty">No Gene Detective Stories have been published yet.</p>'}</div>
      </section>
      <section class="monthly-archive-group" aria-labelledby="legacy-publications-heading">
        <h2 id="legacy-publications-heading">Previous Publications</h2>
        <div class="weekly-archive-list">${legacyIssues.map(legacyArchiveCard).join("")}</div>
      </section>`;
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
    const label = isMonthlyStory(issue) ? storyLabel(issue.storyNumber) : issueLabel(issue.issueNumber);
    const subject = `${isMonthlyStory(issue) ? "GeneDr Monthly" : "GeneDr Weekly"} ${label}: ${issue.title}`;
    const body = `${issue.title}\n\n${label} | ${formatDate(issue.date)}\n\nRead the full story here:\n${pageUrl}`;
    const email = actions.querySelector("[data-share=email]");
    const share = actions.querySelector("[data-share=native]");
    const copy = actions.querySelector("[data-share=copy]");
    const pdf = actions.querySelector("[data-share=pdf]");
    const status = actions.querySelector("[data-share-status]");
    email.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    if (!navigator.share) share.hidden = true;
    share.addEventListener("click", async () => {
      try { await navigator.share({ title: subject, text: issue.teaser || issue.excerpt, url: pageUrl }); }
      catch (error) { if (error.name !== "AbortError") status.textContent = "Sharing is unavailable. Please use Email or Copy Link."; }
    });
    copy.addEventListener("click", async () => {
      try { await copyText(pageUrl); status.textContent = "Link copied"; }
      catch (error) { status.textContent = "Could not copy the link."; }
    });
    pdf.addEventListener("click", () => window.GeneDrWeeklyPDF.print(issue, "article"));
  }

  function monthlyArticle(issue) {
    const parsed = parseStory(issue.storyContent);
    return `<nav class="weekly-article-links" aria-label="Story links">
      <a class="back-link" href="../index.html">← Back to Home</a><a class="back-link" href="archive.html">Previous Stories →</a>
    </nav>
    <header class="weekly-article-header">
      <p class="weekly-wordmark" aria-label="GeneDr Monthly"><span>GeneDr</span> <em>Monthly</em></p>
      <p class="weekly-article-deck">Gene Detective Story</p>
      <p class="weekly-tagline">Discover Genetics, One story at a time.</p>
      <div class="weekly-article-meta"><span>${escapeHtml(issue.monthYear || formatMonthYear(issue.date))} <b>•</b> ${escapeHtml(storyLabel(issue.storyNumber))} <b>•</b> ${escapeHtml(formatDate(issue.date))}</span></div>
      <h1>${escapeHtml(issue.title || parsed.title)}</h1>
      ${(issue.subtitle || parsed.subtitle) ? `<p class="weekly-article-subtitle">${escapeHtml(issue.subtitle || parsed.subtitle)}</p>` : ""}
      <span class="weekly-category weekly-article-category">Gene Detective Story</span>
    </header>
    <div id="weekly-share-actions" class="weekly-share-actions" aria-label="Share this story">
      <a class="weekly-button weekly-button-secondary" data-share="email" href="#">Email This Story</a>
      <button class="weekly-button weekly-button-primary" data-share="native" type="button">Share This Story</button>
      <button class="weekly-button weekly-button-secondary" data-share="copy" type="button">Copy Link</button>
      <button class="weekly-button weekly-button-secondary" data-share="pdf" type="button">Export to PDF</button>
      <span class="weekly-share-status" data-share-status role="status" aria-live="polite"></span>
    </div>
    <div class="monthly-story-body">${renderStorySections(issue)}</div>
    <footer class="weekly-print-footer"><span>${escapeHtml(issue.title)}</span><span>GeneDr Monthly · GeneDrNetwork</span></footer>`;
  }

  function legacyArticle(issue) {
    return `<nav class="weekly-article-links" aria-label="Article links">
      <a class="back-link" href="../index.html">← Back to Home</a><a class="back-link" href="archive.html">Publication Archive →</a>
    </nav>
    <header class="weekly-article-header weekly-legacy-header">
      <p class="weekly-wordmark" aria-label="GeneDr Weekly"><span>GeneDr</span> <em>Weekly</em></p>
      <p class="weekly-article-deck">Legacy Publication</p>
      <div class="weekly-article-meta"><span>${escapeHtml(issueLabel(issue.issueNumber))} <b>•</b> ${escapeHtml(formatDate(issue.date))} <b>•</b> ${escapeHtml(issue.readingTime)}</span></div>
      <h1>${escapeHtml(issue.title)}</h1>${issue.subtitle ? `<p class="weekly-article-subtitle">${escapeHtml(issue.subtitle)}</p>` : ""}
      <span class="weekly-category weekly-article-category">${escapeHtml(issue.category)}</span>
    </header>
    <div id="weekly-share-actions" class="weekly-share-actions" aria-label="Share this article">
      <a class="weekly-button weekly-button-secondary" data-share="email" href="#">Email This Story</a>
      <button class="weekly-button weekly-button-primary" data-share="native" type="button">Share This Story</button>
      <button class="weekly-button weekly-button-secondary" data-share="copy" type="button">Copy Link</button>
      <button class="weekly-button weekly-button-secondary" data-share="pdf" type="button">Export to PDF</button>
      <span class="weekly-share-status" data-share-status role="status" aria-live="polite"></span>
    </div>
    <section><h2>Clinical Scenario</h2><p><em>${escapeHtml(issue.scenario)}</em></p><p><strong>${escapeHtml(issue.question)}</strong></p></section>
    <section><h2>Why This Matters</h2><p>${escapeHtml(issue.articleSections.whyThisMatters || "")}</p></section>
    <section><h2>Main Article</h2>${renderLegacyArticleText(issue.articleSections.mainArticle || "")}</section>
    <section><h2>Key Points</h2><ul>${issue.keyPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul></section>
    <section><h2>References</h2><ol>${issue.references.map((reference) => `<li>${escapeHtml(reference)}</li>`).join("")}</ol></section>
    <p class="weekly-disclaimer"><em>${escapeHtml(issue.disclaimer)}</em></p>
    <footer class="weekly-print-footer"><span>${escapeHtml(issue.title)}</span><span>GeneDr Weekly legacy publication · GeneDrNetwork</span></footer>`;
  }

  function renderArticle() {
    const target = document.querySelector("#weekly-article");
    if (!target) return;
    const slug = new URLSearchParams(window.location.search).get("issue");
    const issue = published.find((item) => item.slug === slug) || monthlyStories[0] || legacyIssues[0];
    if (!issue) return;
    document.title = `${issue.title} | ${isMonthlyStory(issue) ? "GeneDr Monthly" : "GeneDr Weekly"}`;
    target.innerHTML = isMonthlyStory(issue) ? monthlyArticle(issue) : legacyArticle(issue);
    setupSharing(issue);
  }

  window.GeneDrMonthly = {
    managerStorageKey, escapeHtml, formatDate, formatMonthYear, issueLabel, storyLabel,
    isMonthlyStory, normalizeIssue, parseStory, renderStorySections, renderLegacyArticleText,
    articleUrl, getAllIssues: () => allIssues.map((issue) => ({ ...issue }))
  };
  window.GeneDrWeekly = window.GeneDrMonthly;
  renderHomepage();
  renderArchive();
  renderArticle();
})();
