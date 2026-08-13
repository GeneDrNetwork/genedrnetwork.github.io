(function () {
  const {
    managerStorageKey, escapeHtml, formatDate, formatMonthYear, issueLabel, storyLabel,
    isMonthlyStory, normalizeIssue, parseStory, publicationMetadataSuggestions, homepagePresentation, estimateReadingTime,
    renderStorySections, getEditorialSettings, editorCredit, editorNotePreview, renderEditorNote
  } = window.GeneDrMonthly;

  const form = document.querySelector("#issue-form");
  const editor = document.querySelector("#manager-editor");
  const preview = document.querySelector("#manager-preview");
  const previewContent = document.querySelector("#manager-preview-content");
  const list = document.querySelector("#manager-issue-list");
  const importField = document.querySelector("#story-import");
  const fileField = document.querySelector("#story-file");
  const fileImportButton = document.querySelector("#import-story-file");
  const importStatus = document.querySelector("#story-import-status");
  const saveStatus = document.querySelector("#save-status");
  const publishDialog = document.querySelector("#publish-confirmation");
  const deleteDialog = document.querySelector("#delete-confirmation");
  const deleteMessage = document.querySelector("#delete-confirmation-message");
  let activeSlug = null;
  let pendingDeleteSlug = null;
  let lastPreviewStory = null;
  let metadataVariant = 0;
  let editingPublished = false;
  let publishedIdentity = null;

  if (window.pdfjsLib) {
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  }

  const repoIssues = (window.GENEDR_WEEKLY_ISSUES || []).map(normalizeIssue);
  let browserStories = [];
  try {
    browserStories = JSON.parse(localStorage.getItem(managerStorageKey) || "[]")
      .map(normalizeIssue)
      .filter(isMonthlyStory);
  } catch (error) {
    browserStories = [];
  }

  function combinedIssues() {
    const bySlug = new Map(repoIssues.map((issue) => [issue.slug, issue]));
    browserStories.forEach((story) => bySlug.set(story.slug, story));
    return Array.from(bySlug.values()).sort((a, b) => new Date(b.date) - new Date(a.date));
  }

  function persistStories() {
    localStorage.setItem(managerStorageKey, JSON.stringify(browserStories));
  }

  function nextMonthlyNumber(field) {
    return Math.max(0, ...combinedIssues().filter(isMonthlyStory).map((story) => Number(story[field]) || 0)) + 1;
  }

  function slugify(value) {
    return String(value).toLowerCase().trim().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function storyFromForm() {
    const data = new FormData(form);
    return normalizeIssue({
      publicationType: "gene-detective-story",
      issueNumber: Number(data.get("issueNumber")),
      storyNumber: Number(data.get("storyNumber")),
      date: data.get("date").trim(),
      monthYear: data.get("monthYear").trim(),
      title: data.get("title").trim(),
      subtitle: data.get("subtitle").trim(),
      teaser: data.get("teaser").trim(),
      readingTime: data.get("readingTime").trim(),
      slug: data.get("slug").trim(),
      authorLine: data.get("authorLine").trim(),
      storyContent: data.get("storyContent").trim(),
      status: form.elements.status.value || "draft"
    });
  }

  function setPublishedEditingState(story) {
    editingPublished = story.status === "published";
    publishedIdentity = editingPublished ? {
      issueNumber: story.issueNumber,
      storyNumber: story.storyNumber,
      date: story.date,
      monthYear: story.monthYear,
      slug: story.slug
    } : null;
    ["issueNumber", "storyNumber", "date", "monthYear", "slug"].forEach((name) => {
      form.elements[name].readOnly = editingPublished;
    });
    document.querySelector("#save-draft").hidden = editingPublished;
    document.querySelector("#preview-homepage").textContent = editingPublished ? "Preview Changes" : "Preview Homepage Feature";
    document.querySelector("#publish-story").textContent = editingPublished ? "Update Publication" : "Publish & Download";
    publishDialog.querySelector("h2").textContent = editingPublished ? "Update this published Story?" : "Publish this Story?";
    publishDialog.querySelector("p").textContent = editingPublished
      ? "This replaces the existing published issue while preserving its Story number, month, and URL. A repository-ready publishing file will download for deployment."
      : "The Story will become the current featured monthly publication in this browser, and a repository-ready publishing file will download. Send that file to Codex to update the public GitHub Pages website.";
    document.querySelector("#confirm-publish").textContent = editingPublished ? "Update Publication" : "Publish & Download";
  }

  function fillForm(story, message) {
    activeSlug = story.slug;
    const values = { ...story, monthYear: story.monthYear || formatMonthYear(story.date) };
    Object.entries(values).forEach(([name, value]) => {
      if (form.elements[name]) form.elements[name].value = value;
    });
    setPublishedEditingState(story);
    editor.hidden = false;
    saveStatus.textContent = message || (editingPublished
      ? `Editing published ${storyLabel(story.storyNumber)} · updates replace this issue without creating a new one.`
      : `Editing ${storyLabel(story.storyNumber)} · browser-local draft`);
    editor.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderList() {
    list.innerHTML = combinedIssues().map((issue) => {
      if (!isMonthlyStory(issue)) {
        return `<tr>
          <td>${escapeHtml(issueLabel(issue.issueNumber))}</td>
          <td>${escapeHtml(formatMonthYear(issue.date))}</td>
          <td>${escapeHtml(issue.title)}</td>
          <td><span class="manager-status">Legacy Weekly</span></td>
          <td>${escapeHtml(issue.readingTime)}</td>
          <td><span class="manager-note-status is-complete">Preserved</span></td>
          <td><span class="manager-status">${escapeHtml(issue.status)}</span></td>
          <td><div class="manager-row-actions"><a href="../../genedr-weekly/article.html?issue=${encodeURIComponent(issue.slug)}" target="_blank" rel="noopener">View preserved article</a></div></td>
        </tr>`;
      }
      return `<tr>
        <td>${escapeHtml(storyLabel(issue.storyNumber))}</td>
        <td>${escapeHtml(issue.monthYear || formatMonthYear(issue.date))}</td>
        <td>${escapeHtml(issue.title || "Untitled Story")}</td>
        <td><span class="manager-status">Monthly Story</span></td>
        <td>${escapeHtml(issue.readingTime)}</td>
        <td><span class="manager-note-status is-complete">Permanent</span></td>
        <td><span class="manager-status">${escapeHtml(issue.status)}</span></td>
        <td><div class="manager-row-actions">
          <button type="button" data-row-action="preview" data-slug="${escapeHtml(issue.slug)}">Preview</button>
          <button type="button" data-row-action="edit" data-slug="${escapeHtml(issue.slug)}">${issue.status === "published" ? "Edit Published Issue" : "Edit"}</button>
          ${issue.status === "published" ? "" : `<button class="manager-row-delete" type="button" data-row-action="delete" data-slug="${escapeHtml(issue.slug)}">Delete</button>`}
        </div></td>
      </tr>`;
    }).join("");
  }

  function saveStory(status) {
    if (!form.reportValidity()) return null;
    const story = storyFromForm();
    if (editingPublished && publishedIdentity) Object.assign(story, publishedIdentity);
    story.status = status || story.status;
    form.elements.status.value = story.status;
    const duplicate = combinedIssues().find((item) => item.slug === story.slug && item.slug !== activeSlug);
    if (duplicate) {
      saveStatus.textContent = `The slug “${story.slug}” is already in use.`;
      form.elements.slug.focus();
      return null;
    }
    const duplicateNumber = combinedIssues().find((item) => isMonthlyStory(item) && Number(item.storyNumber) === story.storyNumber && item.slug !== activeSlug);
    if (duplicateNumber) {
      saveStatus.textContent = `${storyLabel(story.storyNumber)} already exists.`;
      form.elements.storyNumber.focus();
      return null;
    }
    const index = browserStories.findIndex((item) => item.slug === activeSlug);
    if (index >= 0) browserStories[index] = story;
    else browserStories.push(story);
    activeSlug = story.slug;
    setPublishedEditingState(story);
    persistStories();
    renderList();
    saveStatus.textContent = `${storyLabel(story.storyNumber)} saved as ${story.status} in this browser.`;
    return story;
  }

  function homepagePreview(story) {
    const settings = getEditorialSettings();
    const presentation = homepagePresentation(story);
    previewContent.innerHTML = `<div class="weekly-card">
      <div class="weekly-intro">
        <p class="weekly-wordmark" aria-label="GeneDr Monthly"><span>GeneDr</span> <em>Monthly</em></p>
        <h2>Discover Genetics, One Story at a Time.</h2>
        <p class="weekly-tagline">One completed Gene Detective Story each month.</p>
        <p class="weekly-meta">${escapeHtml(storyLabel(story.storyNumber))} <span>•</span> ${escapeHtml(story.monthYear || formatMonthYear(story.date))} <span>•</span> ${escapeHtml(story.readingTime)}</p>
        ${editorCredit(settings, "weekly-editor-credit-on-dark")}
        <aside class="weekly-note-preview"><h3>Editor’s Note</h3><p>${escapeHtml(editorNotePreview(story))}</p><span class="manager-preview-link">Continue reading →</span></aside>
      </div>
      <div class="weekly-story">
        <p class="weekly-overline">Featured Gene Detective Story</p>
        <span class="weekly-category">Gene Detective Story</span>
        <h3>${escapeHtml(story.title)}</h3>
        ${presentation.subtitle ? `<p class="weekly-feature-subtitle">${escapeHtml(presentation.subtitle)}</p>` : ""}
        <div class="weekly-scenario"><strong>Story Preview</strong><p><em>${escapeHtml(presentation.teaser)}</em></p></div>
        <div class="weekly-actions"><span class="weekly-button weekly-button-primary">Continue Reading →</span><span class="weekly-button weekly-button-secondary">Story Archive</span></div>
      </div>
    </div>`;
  }

  function articlePreview(story) {
    const settings = getEditorialSettings();
    previewContent.innerHTML = `<article class="weekly-article">
      <header class="weekly-article-header">
        <p class="weekly-wordmark" aria-label="GeneDr Monthly"><span>GeneDr</span> <em>Monthly</em></p>
        <p class="weekly-article-deck">Discover Genetics, One Story at a Time.</p>
        <p class="weekly-tagline">One completed Gene Detective Story each month.</p>
        <div class="weekly-article-meta"><span>${escapeHtml(storyLabel(story.storyNumber))} <b>•</b> ${escapeHtml(story.monthYear || formatMonthYear(story.date))} <b>•</b> ${escapeHtml(formatDate(story.date))} <b>•</b> ${escapeHtml(story.readingTime)}</span></div>
        ${editorCredit(settings, "weekly-editor-credit-on-dark")}
        <h1>${escapeHtml(story.title)}</h1>
        ${story.subtitle ? `<p class="weekly-article-subtitle">${escapeHtml(story.subtitle)}</p>` : ""}
        <span class="weekly-category weekly-article-category">Gene Detective Story</span>
      </header>
      ${renderEditorNote(story)}
      <div class="monthly-story-body">${renderStorySections(story)}</div>
      <footer class="weekly-print-footer"><span>${escapeHtml(story.title)}</span><span>GeneDr Monthly · GeneDrNetwork</span></footer>
    </article>`;
  }

  function showPreview(type, story = storyFromForm()) {
    lastPreviewStory = story;
    preview.hidden = false;
    if (type === "card") homepagePreview(story);
    else articlePreview(story);
    preview.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function download(filename, contents, type) {
    const url = URL.createObjectURL(new Blob([contents], { type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function publishingIssues() {
    const bySlug = new Map(repoIssues.map((issue) => [issue.slug, issue]));
    browserStories.filter((story) => story.status === "published").forEach((story) => bySlug.set(story.slug, story));
    return Array.from(bySlug.values()).sort((a, b) => new Date(a.date) - new Date(b.date));
  }

  function downloadPublishingFile() {
    const contents = `window.GENEDR_WEEKLY_ISSUES = ${JSON.stringify(publishingIssues(), null, 2)};\n`;
    download("genedr-weekly-issues.js", contents, "text/javascript");
  }

  async function copyStoryJson(story) {
    const value = JSON.stringify(story, null, 2);
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(value);
    else {
      const textarea = document.createElement("textarea");
      textarea.value = value;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    saveStatus.textContent = "Story JSON copied.";
  }

  function createDraftFromSource(source, successMessage) {
    if (!source) {
      importStatus.textContent = "Paste a completed Story or import a DOCX/PDF before parsing.";
      importField.focus();
      return null;
    }
    const parsed = parseStory(source);
    const suggestions = publicationMetadataSuggestions(source, 0);
    if (!parsed.title) {
      importStatus.textContent = "A Story title could not be identified. Keep the title as the first line and try again.";
      return null;
    }
    const issueNumber = nextMonthlyNumber("issueNumber");
    const storyNumber = nextMonthlyNumber("storyNumber");
    const date = new Date().toISOString().slice(0, 10);
    const story = normalizeIssue({
      publicationType: "gene-detective-story",
      issueNumber,
      storyNumber,
      date,
      monthYear: formatMonthYear(date),
      title: parsed.title,
      subtitle: suggestions.subtitle || parsed.subtitle,
      teaser: suggestions.teaser || parsed.teaser,
      readingTime: estimateReadingTime(parsed.source),
      slug: slugify(parsed.title) || `gene-detective-story-${String(storyNumber).padStart(3, "0")}`,
      authorLine: parsed.authorLine,
      storyContent: parsed.source,
      status: "draft"
    });
    activeSlug = story.slug;
    fillForm(story, `${storyLabel(storyNumber)} parsed. Review the detected details and preview before publishing.`);
    metadataVariant = 0;
    importStatus.textContent = successMessage || "Story parsed. Publication metadata was suggested without changing the Story.";
    return story;
  }

  async function extractDocx(file) {
    if (!window.mammoth) throw new Error("The Word import library did not load. Refresh the page and try again.");
    const result = await window.mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() });
    return result.value.trim();
  }

  async function extractPdf(file) {
    if (!window.pdfjsLib) throw new Error("The PDF import library did not load. Refresh the page and try again.");
    const documentTask = window.pdfjsLib.getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
    const pdf = await documentTask.promise;
    const lines = [];
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const content = await page.getTextContent();
      let line = "";
      content.items.forEach((item) => {
        const text = String(item.str || "");
        if (text) {
          const needsSpace = line && !/^\s|^[,.;:!?)]/.test(text) && !/[\s(\-/]$/.test(line);
          line += `${needsSpace ? " " : ""}${text}`;
        }
        if (item.hasEOL && line.trim()) {
          lines.push(line.trim());
          line = "";
        }
      });
      if (line.trim()) lines.push(line.trim());
    }
    return lines.join("\n").trim();
  }

  document.querySelector("#parse-story").addEventListener("click", () => {
    createDraftFromSource(importField.value.trim());
  });

  fileImportButton.addEventListener("click", async () => {
    const file = fileField.files?.[0];
    if (!file) {
      importStatus.textContent = "Choose a DOCX or PDF file first.";
      fileField.focus();
      return;
    }
    const extension = file.name.toLowerCase().split(".").pop();
    if (!['docx', 'pdf'].includes(extension)) {
      importStatus.textContent = "Choose a .docx or .pdf Story file.";
      return;
    }
    fileImportButton.disabled = true;
    importStatus.textContent = `Reading ${file.name} locally in this browser…`;
    try {
      const source = extension === "docx" ? await extractDocx(file) : await extractPdf(file);
      if (!source) throw new Error(extension === "pdf"
        ? "No selectable text was found. Use the DOCX version or a text-based PDF."
        : "No Story text was found in this Word document.");
      importField.value = source;
      const reviewNote = extension === "pdf" ? " PDF extraction can alter line breaks, so compare the Story box with the original before publishing." : "";
      createDraftFromSource(source, `${file.name} imported into the Story box. Review the suggested opening line and teaser.${reviewNote}`);
    } catch (error) {
      importStatus.textContent = error.message || "The Story file could not be imported.";
    } finally {
      fileImportButton.disabled = false;
    }
  });

  document.querySelector("#clear-story-import").addEventListener("click", () => {
    importField.value = "";
    fileField.value = "";
    importStatus.textContent = "";
    importField.focus();
  });

  list.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-row-action]");
    if (!button) return;
    const story = combinedIssues().find((item) => item.slug === button.dataset.slug && isMonthlyStory(item));
    if (!story) return;
    if (button.dataset.rowAction === "edit") fillForm(story);
    if (button.dataset.rowAction === "preview") showPreview("article", story);
    if (button.dataset.rowAction === "delete" && story.status !== "published") {
      pendingDeleteSlug = story.slug;
      deleteMessage.textContent = `${storyLabel(story.storyNumber)} — ${story.title} will be removed from this browser.`;
      deleteDialog.showModal();
    }
  });

  document.querySelector("#confirm-delete-issue").addEventListener("click", () => {
    if (!pendingDeleteSlug) return;
    browserStories = browserStories.filter((story) => story.slug !== pendingDeleteSlug || story.status === "published");
    if (activeSlug === pendingDeleteSlug) {
      activeSlug = null;
      editor.hidden = true;
      preview.hidden = true;
    }
    persistStories();
    renderList();
    pendingDeleteSlug = null;
  });

  form.addEventListener("submit", (event) => event.preventDefault());
  form.addEventListener("click", (event) => {
    const saveButton = event.target.closest("button[data-status-action]");
    const previewButton = event.target.closest("button[data-preview]");
    const exportButton = event.target.closest("button[data-export]");
    const publishButton = event.target.closest("button[data-publish]");
    const generateButton = event.target.closest("button[data-generate-metadata]");
    if (saveButton) saveStory(saveButton.dataset.statusAction);
    if (generateButton) {
      const source = form.elements.storyContent.value.trim();
      if (!source) {
        saveStatus.textContent = "Add the complete Story before generating publication metadata.";
      } else {
        metadataVariant += 1;
        const suggestions = publicationMetadataSuggestions(source, metadataVariant);
        const field = generateButton.dataset.generateMetadata;
        form.elements[field].value = suggestions[field];
        generateButton.textContent = field === "teaser" ? "Regenerate Teaser" : "Regenerate Subtitle";
        saveStatus.textContent = `${field === "teaser" ? "Homepage teaser" : "Subtitle"} regenerated. Review or edit it before publishing or updating.`;
      }
    }
    if (previewButton && form.reportValidity()) showPreview(previewButton.dataset.preview);
    if (publishButton && form.reportValidity()) publishDialog.showModal();
    if (exportButton) {
      const story = saveStory();
      if (!story) return;
      if (exportButton.dataset.export === "story-json") download(`${story.slug}.json`, JSON.stringify(story, null, 2), "application/json");
      if (exportButton.dataset.export === "publishing-file") downloadPublishingFile();
      if (exportButton.dataset.export === "copy") copyStoryJson(story).catch(() => { saveStatus.textContent = "Could not copy Story JSON."; });
    }
  });

  document.querySelector("#confirm-publish").addEventListener("click", () => {
    const wasPublishedEdit = editingPublished;
    const story = saveStory("published");
    if (!story) return;
    downloadPublishingFile();
    saveStatus.textContent = wasPublishedEdit
      ? `${storyLabel(story.storyNumber)} was updated in this browser without changing its number, month, or URL. Send the downloaded genedr-weekly-issues.js file to Codex for public deployment.`
      : `${storyLabel(story.storyNumber)} is published in this browser. Send the downloaded genedr-weekly-issues.js file to Codex for public deployment.`;
  });

  document.querySelector("#manager-preview-pdf").addEventListener("click", () => {
    if (!lastPreviewStory) return;
    articlePreview(lastPreviewStory);
    window.GeneDrWeeklyPDF.print(lastPreviewStory, "manager");
  });

  window.GeneDrMonthlyManager = { parseStory, slugify, publishingIssues };
  renderList();
})();
