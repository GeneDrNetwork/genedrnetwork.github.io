(function () {
  const storageKey = "genedr-weekly-manager-issues-v1";
  const topicStorageKey = "genedr-weekly-manager-topics-v1";
  const emailHistoryKey = "genedr-weekly-email-history-v1";
  const statuses = ["draft", "ready-for-review", "approved", "published", "archived"];
  const publicCategories = window.GeneDrWeekly.categories.filter((category) => category !== "All");
  const { escapeHtml, formatDate, issueLabel, normalizeIssue, renderArticleText } = window.GeneDrWeekly;
  const form = document.querySelector("#issue-form");
  const editor = document.querySelector("#manager-editor");
  const preview = document.querySelector("#manager-preview");
  const previewContent = document.querySelector("#manager-preview-content");
  const list = document.querySelector("#manager-issue-list");
  const dialog = document.querySelector("#publish-confirmation");
  const saveStatus = document.querySelector("#save-status");
  const aiStatus = document.querySelector("#ai-generation-status");
  const referencesFieldLabel = document.querySelector("#references-field-label");
  const emailButton = document.querySelector("#email-subscribers");
  const emailDialog = document.querySelector("#email-confirmation");
  const emailResendDialog = document.querySelector("#email-resend-confirmation");
  const emailPreviewContent = document.querySelector("#email-preview-content");
  const emailActionStatus = document.querySelector("#email-action-status");
  const previewPdfButton = document.querySelector("#manager-preview-pdf");
  const referenceMode = document.querySelector("#reference-retrieval-mode");
  let activeKey = null;
  let activeEmailIssue = null;
  let lastPreviewIssue = null;

  let topics = (window.GENEDR_WEEKLY_TOPICS || []).map((topic) => ({ ...topic }));
  try {
    const savedTopics = JSON.parse(localStorage.getItem(topicStorageKey) || "[]");
    const savedByTitle = new Map(savedTopics.map((topic) => [topic.title, topic]));
    topics = topics.map((topic) => savedByTitle.get(topic.title) || topic);
  } catch (error) {
    // Continue with the repository topic library when browser-local topic history is invalid.
  }

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

  function persistTopics() {
    localStorage.setItem(topicStorageKey, JSON.stringify(topics));
  }

  function nextIssueNumber() {
    return Math.max(0, ...issues.map((issue) => Number(issue.issueNumber) || 0)) + 1;
  }

  function slugify(value) {
    return String(value).toLowerCase().trim().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function categoryForTopic(topic) {
    const libraryMatch = topics.find((item) => item.title.toLowerCase() === topic.toLowerCase());
    if (libraryMatch) return libraryMatch.category;
    const value = topic.toLowerCase();
    if (/movie|film|cinema/.test(value)) return "Movie";
    if (/music|art|song/.test(value)) return "Music & Arts";
    if (/\bai\b|artificial intelligence|machine learning/.test(value)) return "AI in Genetics";
    if (/drug|therapy|treatment|inhibitor|replacement/.test(value)) return "Drug Spotlight";
    if (/guideline|recommendation|consensus/.test(value)) return "Guideline Update";
    if (/sequenc|testing|microarray|biomarker/.test(value)) return "Genetic Testing";
    if (/disease|syndrome|deficiency|disorder/.test(value)) return "Disease Spotlight";
    return "Clinical Case";
  }

  function selectLibraryTopic() {
    const recentTitles = issues
      .filter((issue) => issue.date)
      .sort((a, b) => new Date(b.date) - new Date(a.date))
      .slice(0, 8)
      .map((issue) => issue.title.toLowerCase());
    const active = topics.filter((topic) => topic.active);
    const notRecent = active.filter((topic) => !recentTitles.some((title) =>
      title.includes(topic.title.toLowerCase()) || topic.title.toLowerCase().includes(title)
    ));
    const candidates = notRecent.length ? notRecent : active;
    return [...candidates].sort((a, b) => {
      if (!a.lastUsed && b.lastUsed) return -1;
      if (a.lastUsed && !b.lastUsed) return 1;
      if ((a.usageCount || 0) !== (b.usageCount || 0)) return (a.usageCount || 0) - (b.usageCount || 0);
      return new Date(a.lastUsed || 0) - new Date(b.lastUsed || 0);
    })[0];
  }

  function emptyIssue() {
    const nextNumber = nextIssueNumber();
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
    const activeIssue = issues.find((item) => String(item.issueNumber) === activeKey);
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
      status: form.elements.status.value,
      referencesNeedVerification: Boolean(activeIssue?.referencesNeedVerification)
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
    emailButton.hidden = issue.status !== "published";
    emailButton.disabled = issue.status !== "published";
    referencesFieldLabel.textContent = issue.referencesNeedVerification
      ? "Suggested References — Verification Required"
      : "References";
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
    const duplicateSlug = issues.find((item) => item.slug === issue.slug && String(item.issueNumber) !== activeKey);
    if (duplicateSlug) {
      saveStatus.textContent = `The slug “${issue.slug}” is already used by ${issueLabel(duplicateSlug.issueNumber)}.`;
      form.elements.slug.focus();
      return null;
    }
    const index = issues.findIndex((item) => String(item.issueNumber) === activeKey);
    if (index >= 0) issues[index] = issue;
    else issues.push(issue);
    activeKey = newKey;
    persistBrowserIssues();
    renderList();
    emailButton.hidden = issue.status !== "published";
    emailButton.disabled = issue.status !== "published";
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
      <section><h2>Main Article</h2>${renderArticleText(issue.articleSections.mainArticle)}</section>
      <section><h2>Key Points</h2><ul>${issue.keyPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul></section>
      <section><h2>${issue.referencesNeedVerification ? "Suggested References — Verification Required" : "References"}</h2><ol>${issue.references.map((reference) => `<li>${escapeHtml(reference)}</li>`).join("")}</ol></section>
      <p class="weekly-disclaimer"><em>${escapeHtml(issue.disclaimer)}</em></p>
      <footer class="weekly-print-footer"><span>${escapeHtml(issue.title)}</span><span>GeneDrNetwork · https://genedrnetwork.github.io</span></footer>
    </article>`;
  }

  function showPreview(type, issue = issueFromForm()) {
    lastPreviewIssue = issue;
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

  function recordEmailResult(issue, result) {
    let history = {};
    try { history = JSON.parse(localStorage.getItem(emailHistoryKey) || "{}"); } catch (error) { history = {}; }
    history[String(issue.issueNumber)] = {
      issueNumber: issue.issueNumber,
      sentAt: result.sentAt || new Date().toISOString(),
      recipientCount: result.recipientCount ?? null,
      providerId: result.providerId || null,
      status: result.status || "unknown",
      error: result.error || null
    };
    localStorage.setItem(emailHistoryKey, JSON.stringify(history));
  }

  function openEmailPreview(issue) {
    if (issue.status !== "published") {
      saveStatus.textContent = "Only a published issue can be emailed to subscribers.";
      return;
    }
    activeEmailIssue = issue;
    const email = window.GeneDrWeeklyEmail.buildPreview(issue);
    emailPreviewContent.innerHTML = `
      <div class="manager-email-brand"><strong>GeneDr <em>Weekly</em></strong><span>Discover Genetics, One Story at a Time.</span><span>Five minutes of enjoyable genetics reading every week.</span></div>
      <dl><div><dt>Email subject</dt><dd>${escapeHtml(email.subject)}</dd></div><div><dt>Issue</dt><dd>#${issue.issueNumber} · ${escapeHtml(email.date)}</dd></div><div><dt>Title</dt><dd>${escapeHtml(email.title)}</dd></div><div><dt>Short excerpt</dt><dd>${escapeHtml(email.excerpt)}</dd></div><div><dt>Article link</dt><dd>${escapeHtml(email.articleUrl)}</dd></div></dl>`;
    emailActionStatus.textContent = "";
    emailDialog.showModal();
  }

  async function sendSubscriberEmail(action, resend = false) {
    if (!activeEmailIssue) return;
    const label = action === "test" ? "Sending test email…" : resend ? "Resending to subscribers…" : "Sending to subscribers…";
    emailActionStatus.textContent = label;
    try {
      const result = await window.GeneDrWeeklyEmail.request(action, activeEmailIssue, { resend, resendConfirmed: resend });
      recordEmailResult(activeEmailIssue, result);
      emailActionStatus.textContent = action === "test"
        ? `Test email sent. Provider ID: ${result.providerId || "not returned"}.`
        : `Subscriber email sent to ${result.recipientCount ?? "the configured"} recipients. Provider ID: ${result.providerId || "not returned"}.`;
    } catch (error) {
      recordEmailResult(activeEmailIssue, { status: "failed", error: error.message });
      emailActionStatus.textContent = error.message;
      if (error.code === "ALREADY_SENT") emailResendDialog.showModal();
    }
  }

  async function generateAiDraft(topic, category) {
    const issueNumber = nextIssueNumber();
    const date = new Date().toISOString().slice(0, 10);
    const recentTopics = [...issues]
      .sort((a, b) => new Date(b.date) - new Date(a.date))
      .slice(0, 8)
      .map((issue) => issue.title);
    const buttons = [document.querySelector("#ai-suggest-generate"), document.querySelector("#ai-custom-generate")];
    buttons.forEach((button) => { button.disabled = true; });
    aiStatus.textContent = `Generating a draft about ${topic}…`;
    try {
      const result = await window.GeneDrWeeklyAI.generateDraft({ topic, category, issueNumber, date, recentTopics });
      const referenceResult = await window.GeneDrWeeklyReferences.retrieve(topic, "recent-plus-landmark");
      result.references = referenceResult.references;
      const draft = normalizeIssue({
        ...result,
        issueNumber,
        date,
        category,
        slug: slugify(result.slug || result.title || topic),
        status: "draft",
        referencesNeedVerification: true
      });
      if (issues.some((issue) => Number(issue.issueNumber) === issueNumber)) {
        throw new window.GeneDrWeeklyAI.DraftGenerationError("DUPLICATE_ISSUE", `Issue #${issueNumber} already exists. No issue was overwritten.`);
      }
      const duplicateSlug = issues.find((issue) => issue.slug === draft.slug);
      if (duplicateSlug) {
        throw new window.GeneDrWeeklyAI.DraftGenerationError("DUPLICATE_SLUG", `The generated slug “${draft.slug}” is already used by ${issueLabel(duplicateSlug.issueNumber)}. No issue was overwritten.`);
      }
      issues.push(draft);
      const topicEntry = topics.find((item) => item.title.toLowerCase() === topic.toLowerCase());
      if (topicEntry) {
        topicEntry.lastUsed = date;
        topicEntry.usageCount = (topicEntry.usageCount || 0) + 1;
        persistTopics();
      }
      persistBrowserIssues();
      renderList();
      fillForm(draft);
      aiStatus.textContent = `${issueLabel(issueNumber)} was generated and saved as Draft. Suggested references require verification.`;
    } catch (error) {
      aiStatus.textContent = error.userMessage || "Draft generation failed. Please try again.";
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  function storeRegeneratedDraft(issue, message) {
    const draft = normalizeIssue({ ...issue, status: "draft" });
    const duplicateNumber = issues.find((item) => Number(item.issueNumber) === Number(draft.issueNumber) && String(item.issueNumber) !== activeKey);
    const duplicateSlug = issues.find((item) => item.slug === draft.slug && String(item.issueNumber) !== activeKey);
    if (duplicateNumber || duplicateSlug) {
      throw new window.GeneDrWeeklyAI.DraftGenerationError("DUPLICATE_ISSUE", "Regeneration would duplicate an existing issue number or slug. No content was overwritten.");
    }
    const index = issues.findIndex((item) => String(item.issueNumber) === activeKey);
    if (index < 0) throw new window.GeneDrWeeklyAI.DraftGenerationError("MISSING_FIELDS", "Save the issue before regenerating content.");
    issues[index] = draft;
    persistBrowserIssues();
    renderList();
    fillForm(draft);
    saveStatus.textContent = message;
  }

  async function regenerateSection(section) {
    if (!form.reportValidity()) return;
    const issue = issueFromForm();
    const buttons = [...document.querySelectorAll("[data-regenerate-section],[data-regenerate-full]")];
    buttons.forEach((button) => { button.disabled = true; });
    saveStatus.textContent = `Regenerating ${section.replace(/([A-Z])/g, " $1").toLowerCase()}…`;
    try {
      const result = await window.GeneDrWeeklyAI.generateSection({ section, issue });
      if (section === "clinicalScenario") {
        issue.scenario = result.scenario;
        issue.question = result.question;
      }
      if (section === "whyThisMatters") issue.articleSections.whyThisMatters = result.whyThisMatters;
      if (section === "mainArticle") issue.articleSections.mainArticle = result.mainArticle;
      if (section === "keyPoints") issue.keyPoints = result.keyPoints;
      if (section === "references") {
        issue.references = result.references;
        issue.referencesNeedVerification = true;
      }
      storeRegeneratedDraft(issue, `${issueLabel(issue.issueNumber)} section regenerated and saved as Draft.`);
    } catch (error) {
      saveStatus.textContent = error.userMessage || error.message || "Section regeneration failed.";
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  async function regenerateFullDraft() {
    if (!form.reportValidity()) return;
    const issue = issueFromForm();
    const buttons = [...document.querySelectorAll("[data-regenerate-section],[data-regenerate-full]")];
    buttons.forEach((button) => { button.disabled = true; });
    saveStatus.textContent = "Regenerating the complete article…";
    try {
      const recentTopics = issues.filter((item) => String(item.issueNumber) !== activeKey).sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8).map((item) => item.title);
      const result = await window.GeneDrWeeklyAI.generateDraft({
        topic: issue.title,
        category: issue.category,
        issueNumber: issue.issueNumber,
        date: issue.date,
        recentTopics
      });
      const referenceResult = await window.GeneDrWeeklyReferences.retrieve(issue.title, referenceMode.value || "recent-plus-landmark");
      result.references = referenceResult.references;
      storeRegeneratedDraft({ ...result, issueNumber: issue.issueNumber, date: issue.date, status: "draft", referencesNeedVerification: true }, `${issueLabel(issue.issueNumber)} fully regenerated and saved as Draft.`);
    } catch (error) {
      saveStatus.textContent = error.userMessage || error.message || "Full-article regeneration failed.";
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  async function refreshReferences(action) {
    if (!form.reportValidity()) return;
    const issue = issueFromForm();
    const buttons = [...document.querySelectorAll("[data-reference-action]")];
    buttons.forEach((button) => { button.disabled = true; });
    saveStatus.textContent = `${action === "update" ? "Updating" : "Refreshing"} verified references from PubMed and authoritative sources…`;
    try {
      const result = await window.GeneDrWeeklyReferences.retrieve(issue.title, referenceMode.value);
      issue.references = result.references;
      issue.referencesNeedVerification = true;
      const warning = result.warnings.length ? ` ${result.warnings.join(" ")}` : "";
      storeRegeneratedDraft(issue, `${result.references.length} reference${result.references.length === 1 ? "" : "s"} retrieved and saved as Draft.${warning}`);
    } catch (error) {
      saveStatus.textContent = error.userMessage || error.message || "Reference retrieval failed. Existing references were not changed.";
    } finally {
      buttons.forEach((button) => { button.disabled = false; });
    }
  }

  document.querySelector("#create-issue").addEventListener("click", () => {
    const issue = emptyIssue();
    issues.push(issue);
    persistBrowserIssues();
    renderList();
    fillForm(issue);
    saveStatus.textContent = `${issueLabel(issue.issueNumber)} created as a browser-local draft.`;
  });

  document.querySelector("#ai-suggest-generate").addEventListener("click", () => {
    const topic = selectLibraryTopic();
    if (!topic) {
      aiStatus.textContent = "No active topics are available in the topic library.";
      return;
    }
    generateAiDraft(topic.title, topic.category);
  });

  document.querySelector("#ai-custom-generate").addEventListener("click", () => {
    const input = document.querySelector("#ai-custom-topic");
    const topic = input.value.trim();
    if (!topic) {
      aiStatus.textContent = "Enter a topic before generating a draft.";
      input.focus();
      return;
    }
    generateAiDraft(topic, categoryForTopic(topic));
  });

  emailButton.addEventListener("click", () => openEmailPreview(issueFromForm()));
  document.querySelector("#send-test-email").addEventListener("click", () => sendSubscriberEmail("test"));
  document.querySelector("#confirm-subscriber-email").addEventListener("click", () => sendSubscriberEmail("send"));
  document.querySelector("#confirm-subscriber-resend").addEventListener("click", async () => {
    emailResendDialog.close();
    await sendSubscriberEmail("send", true);
  });
  previewPdfButton.addEventListener("click", () => {
    if (!lastPreviewIssue) return;
    previewArticle(lastPreviewIssue);
    window.GeneDrWeeklyPDF.print(lastPreviewIssue, "manager");
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
    const regenerateButton = event.target.closest("button[data-regenerate-section]");
    const regenerateFullButton = event.target.closest("button[data-regenerate-full]");
    const referenceButton = event.target.closest("button[data-reference-action]");
    if (regenerateButton) regenerateSection(regenerateButton.dataset.regenerateSection);
    if (regenerateFullButton) regenerateFullDraft();
    if (referenceButton) refreshReferences(referenceButton.dataset.referenceAction);
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
  window.GeneDrWeeklyManagerAI = { categoryForTopic, nextIssueNumber, selectLibraryTopic, slugify };
  renderList();
})();
