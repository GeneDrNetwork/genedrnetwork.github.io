(function () {
  const storageKey = "genedr-weekly-manager-issues-v1";
  const statuses = ["draft", "ready-for-review", "approved", "published", "archived"];
  const publicCategories = window.GeneDrWeekly.categories.filter((category) => category !== "All");
  const { escapeHtml, formatDate, issueLabel, normalizeIssue } = window.GeneDrWeekly;
  const form = document.querySelector("#issue-form");
  const editor = document.querySelector("#manager-editor");
  const preview = document.querySelector("#manager-preview");
  const previewContent = document.querySelector("#manager-preview-content");
  const list = document.querySelector("#manager-issue-list");
  const dialog = document.querySelector("#publish-confirmation");
  const saveStatus = document.querySelector("#save-status");
  let activeKey = null;

  const repoIssues = (window.GENEDR_WEEKLY_ISSUES || []).map(normalizeIssue);
  let savedIssues = [];
  try {
    savedIssues = JSON.parse(localStorage.getItem(storageKey) || "[]").map(normalizeIssue);
  } catch (error) {
    savedIssues = [];
  }
  const byKey = new Map(repoIssues.map((issue) => [String(issue.issueNumber), issue]));
  savedIssues.forEach((issue) => byKey.set(String(issue.issueNumber), issue));
  let issues = Array.from(byKey.values());

  form.elements.category.innerHTML = publicCategories.map((category) =>
    `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`
  ).join("");
  form.elements.status.innerHTML = statuses.map((status) =>
    `<option value="${status}">${status.replaceAll("-", " ")}</option>`
  ).join("");

  function persistBrowserIssues() {
    localStorage.setItem(storageKey, JSON.stringify(issues));
  }

  function emptyIssue() {
    const nextNumber = Math.max(0, ...issues.map((issue) => Number(issue.issueNumber) || 0)) + 1;
    return {
      issueNumber: nextNumber,
      date: new Date().toISOString().slice(0, 10),
      title: "",
      subtitle: "",
      slug: `issue-${String(nextNumber).padStart(3, "0")}`,
      category: "Clinical Case",
      readingTime: "5 min read",
      scenario: "",
      question: "",
      excerpt: "",
      articleSections: { whyThisMatters: "", mainArticle: "" },
      keyPoints: [],
      references: [],
      disclaimer: "The clinical scenario is fictional and created for educational purposes. It does not represent an actual patient.",
      status: "draft"
    };
  }

  function splitLines(value) {
    return String(value).split("\n").map((line) => line.trim()).filter(Boolean);
  }

  function issueFromForm() {
    const data = new FormData(form);
    return {
      issueNumber: Number(data.get("issueNumber")),
      date: data.get("date").trim(),
      title: data.get("title").trim(),
      subtitle: data.get("subtitle").trim(),
      slug: data.get("slug").trim(),
      category: data.get("category"),
      readingTime: data.get("readingTime").trim(),
      scenario: data.get("scenario").trim(),
      question: data.get("question").trim(),
      excerpt: data.get("excerpt").trim(),
      articleSections: {
        whyThisMatters: data.get("whyThisMatters").trim(),
        mainArticle: data.get("mainArticle").trim()
      },
      keyPoints: splitLines(data.get("keyPoints")),
      references: splitLines(data.get("references")),
      disclaimer: data.get("disclaimer").trim(),
      status: form.elements.status.value
    };
  }

  function fillForm(issue) {
    activeKey = String(issue.issueNumber);
    const values = {
      ...issue,
      whyThisMatters: issue.articleSections.whyThisMatters || "",
      mainArticle: issue.articleSections.mainArticle || "",
      keyPoints: issue.keyPoints.join("\n"),
      references: issue.references.join("\n")
    };
    Object.entries(values).forEach(([name, value]) => {
      if (form.elements[name]) form.elements[name].value = value;
    });
    editor.hidden = false;
    saveStatus.textContent = `Editing ${issueLabel(issue.issueNumber)} · browser-local copy`;
    editor.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderList() {
    const sorted = [...issues].sort((a, b) => Number(b.issueNumber) - Number(a.issueNumber));
    list.innerHTML = sorted.map((issue) => `
      <tr>
        <td>${escapeHtml(issueLabel(issue.issueNumber))}</td>
        <td>${escapeHtml(formatDate(issue.date))}</td>
        <td>${escapeHtml(issue.title || "Untitled issue")}</td>
        <td>${escapeHtml(issue.category)}</td>
        <td>${escapeHtml(issue.readingTime)}</td>
        <td><span class="manager-status">${escapeHtml(issue.status.replaceAll("-", " "))}</span></td>
        <td><div class="manager-row-actions">
          <button type="button" data-row-action="preview" data-key="${issue.issueNumber}">Preview</button>
          <button type="button" data-row-action="edit" data-key="${issue.issueNumber}">Edit</button>
        </div></td>
      </tr>`).join("");
  }

  function saveIssue(status) {
    if (!form.reportValidity()) return null;
    const issue = issueFromForm();
    issue.status = status || issue.status;
    form.elements.status.value = issue.status;
    const newKey = String(issue.issueNumber);
    const duplicate = issues.find((item) => String(item.issueNumber) === newKey && String(item.issueNumber) !== activeKey);
    if (duplicate) {
      saveStatus.textContent = "That issue number is already in use.";
      form.elements.issueNumber.focus();
      return null;
    }
    const index = issues.findIndex((item) => String(item.issueNumber) === activeKey);
    if (index >= 0) issues[index] = issue;
    else issues.push(issue);
    activeKey = newKey;
    persistBrowserIssues();
    renderList();
    saveStatus.textContent = `${issueLabel(issue.issueNumber)} saved as ${issue.status.replaceAll("-", " ")} in this browser.`;
    return issue;
  }

  function previewCard(issue) {
    previewContent.innerHTML = `<div class="weekly-card">
      <div class="weekly-intro">
        <p class="weekly-wordmark"><span>GeneDr</span> <em>Weekly</em></p>
        <h2>Discover Genetics, One Story at a Time.</h2>
        <p class="weekly-tagline">Five minutes of enjoyable genetics reading every week.</p>
        <p class="weekly-meta">${issueLabel(issue.issueNumber)} <span>•</span> ${escapeHtml(formatDate(issue.date))} <span>•</span> ${escapeHtml(issue.readingTime)}</p>
        <span class="weekly-category">${escapeHtml(issue.category)}</span>
      </div>
      <div class="weekly-story">
        <p class="weekly-overline">Featured Article of the Week</p>
        <h3>${escapeHtml(issue.title || "Untitled issue")}</h3>
        <div class="weekly-scenario"><strong>Clinical Scenario</strong><p><em>${escapeHtml(issue.scenario)}</em></p><p class="weekly-question">${escapeHtml(issue.question)}</p></div>
        <div class="weekly-actions"><span class="weekly-button weekly-button-primary">Read This Week's Story</span><span class="weekly-button weekly-button-secondary">Browse All Issues</span></div>
      </div>
    </div>`;
  }

  function previewArticle(issue) {
    previewContent.innerHTML = `<article class="weekly-article">
      <header class="weekly-article-header">
        <p class="weekly-wordmark"><span>GeneDr</span> <em>Weekly</em></p>
        <p class="weekly-article-deck">Discover Genetics, One Story at a Time.</p>
        <p class="weekly-tagline">Five minutes of enjoyable genetics reading every week.</p>
        <div class="weekly-article-meta"><span>${issueLabel(issue.issueNumber)} <b>•</b> ${escapeHtml(formatDate(issue.date))} <b>•</b> ${escapeHtml(issue.readingTime)}</span><span class="weekly-category">${escapeHtml(issue.category)}</span></div>
        <h1>${escapeHtml(issue.title || "Untitled issue")}</h1>
        ${issue.subtitle ? `<p class="weekly-article-subtitle">${escapeHtml(issue.subtitle)}</p>` : ""}
      </header>
      <section><h2>Clinical Scenario</h2><p><em>${escapeHtml(issue.scenario)}</em></p><p><strong>${escapeHtml(issue.question)}</strong></p></section>
      <section><h2>Why This Matters</h2><p>${escapeHtml(issue.articleSections.whyThisMatters)}</p></section>
      <section><h2>Main Article</h2><p>${escapeHtml(issue.articleSections.mainArticle)}</p></section>
      <section><h2>Key Points</h2><ul>${issue.keyPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul></section>
      <section><h2>References</h2><ol>${issue.references.map((reference) => `<li>${escapeHtml(reference)}</li>`).join("")}</ol></section>
      <p class="weekly-disclaimer"><em>${escapeHtml(issue.disclaimer)}</em></p>
    </article>`;
  }

  function showPreview(type, issue = issueFromForm()) {
    preview.hidden = false;
    if (type === "card") previewCard(issue);
    else previewArticle(issue);
    preview.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function markdownFor(issue) {
    return `# ${issue.title}\n\n${issue.subtitle}\n\n- Issue #${issue.issueNumber}\n- Date: ${formatDate(issue.date)}\n- Category: ${issue.category}\n- Reading time: ${issue.readingTime}\n- Status: ${issue.status}\n\n## Clinical Scenario\n\n${issue.scenario}\n\n**${issue.question}**\n\n## Excerpt\n\n${issue.excerpt}\n\n## Why This Matters\n\n${issue.articleSections.whyThisMatters}\n\n## Main Article\n\n${issue.articleSections.mainArticle}\n\n## Key Points\n\n${issue.keyPoints.map((point) => `- ${point}`).join("\n")}\n\n## References\n\n${issue.references.map((reference, index) => `${index + 1}. ${reference}`).join("\n")}\n\n_${issue.disclaimer}_\n`;
  }

  function download(filename, contents, type) {
    const url = URL.createObjectURL(new Blob([contents], { type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyIssueJson(issue) {
    const json = JSON.stringify(issue, null, 2);
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(json);
    else {
      const textarea = document.createElement("textarea");
      textarea.value = json;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    saveStatus.textContent = "Issue JSON copied. Add it to data/genedr-weekly-issues.js before deployment.";
  }

  document.querySelector("#create-issue").addEventListener("click", () => {
    const issue = emptyIssue();
    issues.push(issue);
    persistBrowserIssues();
    renderList();
    fillForm(issue);
    saveStatus.textContent = `${issueLabel(issue.issueNumber)} created as a browser-local draft.`;
  });

  list.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-row-action]");
    if (!button) return;
    const issue = issues.find((item) => String(item.issueNumber) === button.dataset.key);
    if (!issue) return;
    if (button.dataset.rowAction === "edit") fillForm(issue);
    else showPreview("article", issue);
  });

  form.addEventListener("submit", (event) => event.preventDefault());
  form.addEventListener("click", (event) => {
    const statusButton = event.target.closest("button[data-status-action]");
    const previewButton = event.target.closest("button[data-preview]");
    const exportButton = event.target.closest("button[data-export]");
    if (statusButton) {
      const status = statusButton.dataset.statusAction;
      if (status === "published") {
        if (form.reportValidity()) dialog.showModal();
      } else saveIssue(status);
    }
    if (previewButton) showPreview(previewButton.dataset.preview);
    if (exportButton) {
      const issue = saveIssue();
      if (!issue) return;
      if (exportButton.dataset.export === "json") download(`${issue.slug}.json`, JSON.stringify(issue, null, 2), "application/json");
      if (exportButton.dataset.export === "markdown") download(`${issue.slug}.md`, markdownFor(issue), "text/markdown");
      if (exportButton.dataset.export === "copy") copyIssueJson(issue).catch(() => { saveStatus.textContent = "Could not copy issue JSON."; });
    }
  });

  document.querySelector("#confirm-publish").addEventListener("click", () => saveIssue("published"));
  renderList();
})();
