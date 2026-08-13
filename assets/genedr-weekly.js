(function () {
  const managerStorageKey = "genedr-monthly-manager-publications-v1";
  const editorialSettingsStorageKey = "genedr-weekly-editorial-settings-v1";
  const LEGACY_EDITOR_NOTE_INTRODUCTION = "Genetics may look like a high wall from the outside. It can seem difficult to understand. But once you step through the gate, you’ll discover a fascinating world where genetics connects every specialty and transforms the way we care for patients.";
  const EDITOR_NOTE_INTRODUCTION = "Genetics may look like a high wall from the outside. It can seem difficult to understand. But once you step through the gate, you’ll discover a fascinating world where genetics connects across medicine and helps us understand the stories written within each of us.";
  const EDITOR_NOTE_MESSAGE = "Gene Detective Stories opens that world to everyone—one patient, one mystery, and one genetic clue at a time.";
  const EDITOR_NOTE_CLOSING = "Welcome to this month’s GeneDr Monthly.";

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
  const estimateReadingTime = (value) => `${Math.max(1, Math.ceil(String(value || "").trim().split(/\s+/).filter(Boolean).length / 220))} min read`;

  const getEditorialSettings = () => {
    const defaults = {
      editorLabel: "Edited and Reviewed by",
      editorName: "Hua Wang",
      editorCredentials: "MD, PhD, FACMG, DABOM",
      ...(window.GENEDR_WEEKLY_EDITORIAL_SETTINGS || {})
    };
    try {
      const saved = JSON.parse(localStorage.getItem(editorialSettingsStorageKey) || "{}");
      return {
        editorLabel: String(saved.editorLabel || defaults.editorLabel).trim(),
        editorName: String(saved.editorName || defaults.editorName).trim(),
        editorCredentials: String(saved.editorCredentials || defaults.editorCredentials).trim()
      };
    } catch (error) {
      return defaults;
    }
  };

  const editorDisplayName = (settings = getEditorialSettings()) =>
    [settings.editorName, settings.editorCredentials].filter(Boolean).join(", ");

  const editorCredit = (settings = getEditorialSettings(), className = "") => `
    <div class="weekly-editor-credit ${className}">
      <span>${escapeHtml(settings.editorLabel)}</span>
      <strong>${escapeHtml(editorDisplayName(settings))}</strong>
    </div>`;

  const normalizeIssue = (issue) => ({
    ...issue,
    publicationType: issue.publicationType || "legacy-weekly",
    subtitle: issue.subtitle || "",
    teaser: issue.teaser || issue.excerpt || "",
    homepageExcerpt: issue.homepageExcerpt || issue.teaser || issue.excerpt || "",
    storyNumber: Number(issue.storyNumber || 0),
    storyContent: issue.storyContent || "",
    authorLine: issue.authorLine || "",
    readingTime: issue.readingTime || estimateReadingTime(issue.storyContent || issue.articleSections?.mainArticle || ""),
    editorNoteTopicIntroduction: issue.editorNoteTopicIntroduction || "",
    excerpt: issue.excerpt || issue.description || "",
    articleSections: issue.articleSections || issue.sections || {},
    keyPoints: issue.keyPoints || issue.sections?.keyPoints || [],
    references: issue.references || issue.sections?.references || [],
    disclaimer: issue.disclaimer || "The clinical scenario is fictional and created for educational purposes. It does not represent an actual patient.",
    status: issue.status || (issue.published ? "published" : "draft")
  });

  const fullEditorNote = (issue) => isMonthlyStory(issue)
    ? [EDITOR_NOTE_INTRODUCTION, EDITOR_NOTE_MESSAGE, EDITOR_NOTE_CLOSING]
    : [LEGACY_EDITOR_NOTE_INTRODUCTION, issue.editorNoteTopicIntroduction, "Welcome to this week’s GeneDr Weekly."].filter(Boolean);

  const editorNotePreview = (issue, maximum = 310) => {
    const text = fullEditorNote(issue).join(" ").replace(/\s+/g, " ").trim();
    const sentences = text.match(/[^.!?]+[.!?]+(?:[”’"'](?=\s|$))?/g) || [text];
    let preview = sentences.slice(0, 3).join(" ").trim();
    const isTruncated = preview.length < text.length || preview.length > maximum;
    if (preview.length > maximum) {
      const shortened = preview.slice(0, maximum + 1);
      preview = shortened.slice(0, shortened.lastIndexOf(" ")).replace(/[.,;:!?]+$/, "");
    }
    return `${preview}${isTruncated ? "…" : ""}`;
  };

  const renderEditorNote = (issue) => `
    <aside id="editors-note" class="weekly-editors-note" aria-labelledby="editors-note-heading">
      <h2 id="editors-note-heading">Editor’s Note</h2>
      ${fullEditorNote(issue).map((paragraph, index, note) => `<p${index === note.length - 1 ? ' class="weekly-editor-note-closing"' : ""}>${escapeHtml(paragraph)}</p>`).join("")}
    </aside>`;

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

  function storyBlocks(source) {
    const hasParagraphBreaks = /\n\s*\n/.test(source);
    const paragraphBlocks = hasParagraphBreaks ? source.split(/\n\s*\n/) : [];
    const seriesLabelSharesBlock = /^gene\s+detective\s+stor(?:y|ies)\s*#?\s*\d+[^\n]*\n/i.test(paragraphBlocks[0] || "");
    const mostlySingleLineDocument = paragraphBlocks.length <= 2 && source.split("\n").filter((line) => line.trim()).length > 10;
    return (hasParagraphBreaks && !seriesLabelSharesBlock && !mostlySingleLineDocument ? paragraphBlocks : source.split("\n"))
      .map((block) => block.trim())
      .filter(Boolean);
  }

  function suggestedTeaser(blocks, excludedBlock) {
    const selections = [];
    for (const block of blocks) {
      if (block === excludedBlock || looksLikeHeading(block)) continue;
      if (/^(by|author|source case|adapted from|written by|edited by|edited and reviewed by)\s*[:—–-]?\s*/i.test(block)) continue;
      const candidate = block.replace(/\s+/g, " ").trim();
      if (!candidate) continue;
      selections.push(candidate);
      const combined = selections.join(" ");
      if (combined.length >= 170 || selections.length === 3) return truncate(combined);
    }
    return truncate(selections.join(" "));
  }

  function looksLikeAuthorLine(block) {
    const value = String(block || "").replace(/\s+/g, " ").trim();
    if (!value || value.length > 180) return false;
    if (/^(author|written by|edited by|edited and reviewed by)\s*[:—–-]\s*\S+/i.test(value)) return true;
    return /^by\s+[A-Z][A-Za-z.'’\-]+/.test(value) && !/[.!?]$/.test(value) && value.split(/\s+/).length <= 18;
  }

  function parseStory(value) {
    const source = String(value || "").replace(/\r\n?/g, "\n").trim();
    const rawBlocks = storyBlocks(source);
    if (!rawBlocks.length) return { title: "", subtitle: "", teaser: "", authorLine: "", sections: [], source };

    let titleIndex = 0;
    if (/^gene\s+detective\s+stor(?:y|ies)\s*#?\s*\d+/i.test(rawBlocks[0]) && rawBlocks[1]) titleIndex = 1;
    const title = cleanHeading(rawBlocks[titleIndex].replace(/^title\s*:\s*/i, ""));
    let cursor = titleIndex + 1;
    let subtitle = "";
    if (rawBlocks[cursor] && !looksLikeHeading(rawBlocks[cursor]) && rawBlocks[cursor].length <= 220) {
      subtitle = rawBlocks[cursor].replace(/^subtitle\s*:\s*/i, "").trim();
      cursor += 1;
    }

    const bodyBlocks = rawBlocks.slice(cursor);
    const authorBlock = bodyBlocks.find(looksLikeAuthorLine);
    const authorHeadingIndex = bodyBlocks.findIndex((block) => /^author\s*:?$/i.test(block));
    const authorLine = authorBlock
      ? authorBlock.replace(/\s+/g, " ").trim()
      : (authorHeadingIndex >= 0 ? String(bodyBlocks[authorHeadingIndex + 1] || "").replace(/\s+/g, " ").trim() : "");
    const teaser = suggestedTeaser(bodyBlocks, authorBlock);
    const sections = [];
    let current = { heading: "", level: 2, blocks: [] };
    bodyBlocks.forEach((block, index) => {
      const followsAuthorHeading = index > 0 && /^author\s*:?$/i.test(bodyBlocks[index - 1]);
      if (looksLikeHeading(block) && !followsAuthorHeading) {
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
    return { title, subtitle, teaser, authorLine, sections, source };
  }

  function publicationMetadataSuggestions(value, variant = 0) {
    const parsed = parseStory(value);
    const paragraphs = parsed.sections.flatMap((section) => section.blocks)
      .map((block) => block.replace(/\s+/g, " ").trim())
      .filter((block) => block && !looksLikeAuthorLine(block) && !/^(author|source case|adapted from|references?)\s*:?$/i.test(block));
    const sentences = [parsed.subtitle, ...paragraphs.flatMap((paragraph) =>
      paragraph.match(/[^.!?]+[.!?]+(?:[”’"'](?=\s|$))?/g) || [paragraph]
    )].map((sentence) => sentence.trim()).filter((sentence, index, all) =>
      sentence.length >= 25 && sentence.length <= 220 && all.indexOf(sentence) === index
    );
    const offset = sentences.length ? Math.abs(Number(variant) || 0) % sentences.length : 0;
    const subtitle = sentences[offset] || parsed.subtitle || parsed.teaser;
    const teaserParts = [];
    for (let index = 1; index <= Math.min(sentences.length, 4); index += 1) {
      const sentence = sentences[(offset + index) % sentences.length];
      if (!sentence || sentence === subtitle) continue;
      const next = [...teaserParts, sentence].join(" ");
      if (next.length > 280 && teaserParts.length) break;
      teaserParts.push(sentence);
      if (next.length >= 150) break;
    }
    const teaser = truncate(teaserParts.join(" ") || parsed.teaser);
    const homepageExcerpt = truncate(teaserParts.slice(0, 2).join(" ") || teaser, 190);
    return { subtitle, teaser, homepageExcerpt };
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
    const currentIssue = monthlyStories[0];
    const issue = currentIssue || normalizeIssue({
      publicationType: "gene-detective-story",
      storyNumber: 1,
      issueNumber: 1,
      date: "",
      monthYear: "New monthly series",
      title: "The first Gene Detective Story is coming soon.",
      subtitle: "Completed clinical mysteries, published one Story at a time.",
      teaser: "The original GeneDr Weekly publication remains available while the first monthly Story is prepared.",
      homepageExcerpt: "A completed Gene Detective Story will be featured here without placing the full Story on the homepage.",
      status: "draft"
    });
    const settings = getEditorialSettings();
    const storyUrl = currentIssue ? articleUrl(issue) : "genedr-weekly/archive.html";

    target.innerHTML = `<div class="weekly-card">
      <div class="weekly-intro">
        <p class="weekly-wordmark" aria-label="GeneDr Monthly"><span>GeneDr</span> <em>Monthly</em></p>
        <h2 id="weekly-section-title">Discover Genetics, One Story at a Time.</h2>
        <p class="weekly-tagline">One completed Gene Detective Story each month.</p>
        <p class="weekly-meta">${escapeHtml(currentIssue ? storyLabel(issue.storyNumber) : "Gene Detective Story")} <span>•</span> ${escapeHtml(issue.monthYear || formatMonthYear(issue.date))}${currentIssue ? ` <span>•</span> ${escapeHtml(issue.readingTime)}` : ""}</p>
        ${editorCredit(settings, "weekly-editor-credit-on-dark")}
        <aside class="weekly-note-preview" aria-labelledby="weekly-note-preview-title">
          <h3 id="weekly-note-preview-title">Editor’s Note</h3>
          <p>${escapeHtml(editorNotePreview(issue))}</p>
          <a href="${storyUrl}${currentIssue ? "#editors-note" : ""}">Continue reading <span aria-hidden="true">→</span></a>
        </aside>
      </div>
      <div class="weekly-story">
        <p class="weekly-overline">Featured Gene Detective Story</p>
        <span class="weekly-category">Gene Detective Story</span>
        <h3>${escapeHtml(issue.title)}</h3>
        ${issue.subtitle ? `<p class="weekly-feature-subtitle">${escapeHtml(issue.subtitle)}</p>` : ""}
        <div class="weekly-scenario">
          <strong>Story Preview</strong>
          <p><em>${escapeHtml(issue.homepageExcerpt || issue.teaser)}</em></p>
          ${issue.teaser && issue.teaser !== issue.homepageExcerpt ? `<p class="weekly-question">${escapeHtml(issue.teaser)}</p>` : ""}
        </div>
        <div class="weekly-actions">
          <a class="weekly-button weekly-button-primary" href="${storyUrl}">${currentIssue ? "Continue Reading" : "View Previous Publication"} <span aria-hidden="true">→</span></a>
          <a class="weekly-button weekly-button-secondary" href="genedr-weekly/archive.html">Story Archive</a>
        </div>
      </div>
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
    const settings = getEditorialSettings();
    return `<nav class="weekly-article-links" aria-label="Story links">
      <a class="back-link" href="../index.html">← Back to Home</a><a class="back-link" href="archive.html">Story Archive →</a>
    </nav>
    <header class="weekly-article-header">
      <p class="weekly-wordmark" aria-label="GeneDr Monthly"><span>GeneDr</span> <em>Monthly</em></p>
      <p class="weekly-article-deck">Discover Genetics, One Story at a Time.</p>
      <p class="weekly-tagline">One completed Gene Detective Story each month.</p>
      <div class="weekly-article-meta"><span>${escapeHtml(storyLabel(issue.storyNumber))} <b>•</b> ${escapeHtml(issue.monthYear || formatMonthYear(issue.date))} <b>•</b> ${escapeHtml(formatDate(issue.date))} <b>•</b> ${escapeHtml(issue.readingTime)}</span></div>
      ${editorCredit(settings, "weekly-editor-credit-on-dark")}
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
    ${renderEditorNote(issue)}
    <div class="monthly-story-body">${renderStorySections(issue)}</div>
    <footer class="weekly-print-footer"><span>${escapeHtml(issue.title)}</span><span>GeneDr Monthly · GeneDrNetwork</span></footer>`;
  }

  function legacyArticle(issue) {
    const settings = getEditorialSettings();
    return `<nav class="weekly-article-links" aria-label="Article links">
      <a class="back-link" href="../index.html">← Back to Home</a><a class="back-link" href="archive.html">Publication Archive →</a>
    </nav>
    <header class="weekly-article-header weekly-legacy-header">
      <p class="weekly-wordmark" aria-label="GeneDr Weekly"><span>GeneDr</span> <em>Weekly</em></p>
      <p class="weekly-article-deck">Discover Genetics, One Story at a Time.</p>
      <p class="weekly-tagline">Five minutes of enjoyable genetics reading every week.</p>
      <div class="weekly-article-meta"><span>${escapeHtml(issueLabel(issue.issueNumber))} <b>•</b> ${escapeHtml(formatDate(issue.date))} <b>•</b> ${escapeHtml(issue.readingTime)}</span></div>
      ${editorCredit(settings, "weekly-editor-credit-on-dark")}
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
    ${renderEditorNote(issue)}
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
    isMonthlyStory, normalizeIssue, parseStory, publicationMetadataSuggestions, estimateReadingTime,
    renderStorySections, renderLegacyArticleText, getEditorialSettings, editorDisplayName, editorCredit,
    fullEditorNote, editorNotePreview, renderEditorNote, EDITOR_NOTE_INTRODUCTION, EDITOR_NOTE_MESSAGE, EDITOR_NOTE_CLOSING,
    articleUrl, getAllIssues: () => allIssues.map((issue) => ({ ...issue }))
  };
  window.GeneDrWeekly = window.GeneDrMonthly;
  renderHomepage();
  renderArchive();
  renderArticle();
})();
