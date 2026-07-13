import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = process.cwd();
const issuesPath = path.join(root, "data/genedr-weekly-issues.js");
const topicsPath = path.join(root, "data/genedr-weekly-topics.js");
const promptPath = path.join(root, "assets/genedr-weekly-ai-prompt.js");
const referencesPath = path.join(root, "assets/genedr-weekly-references.js");
const outputDir = path.join(root, "data/genedr-weekly/issues");
const logDir = path.join(root, "data/genedr-weekly/workflow-log");
const dryRun = process.env.GENEDR_DRY_RUN === "true";
const generatedAt = new Date().toISOString();

function loadWindowScript(file) {
  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  return context.window;
}

function slugify(value) {
  return String(value).toLowerCase().trim().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function selectTopic(topics, issues) {
  const recent = [...issues].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8);
  const recentTitles = recent.map((issue) => issue.title.toLowerCase());
  const recentCategoryCounts = recent.slice(0, 4).reduce((counts, issue) => {
    counts[issue.category] = (counts[issue.category] || 0) + 1;
    return counts;
  }, {});
  const active = topics.filter((topic) => topic.active);
  const unusedRecently = active.filter((topic) => !recentTitles.some((title) =>
    title.includes(topic.title.toLowerCase()) || topic.title.toLowerCase().includes(title)
  ));
  const candidates = unusedRecently.length ? unusedRecently : active;
  return [...candidates].sort((a, b) => {
    const categoryDifference = (recentCategoryCounts[a.category] || 0) - (recentCategoryCounts[b.category] || 0);
    if (categoryDifference) return categoryDifference;
    if ((a.usageCount || 0) !== (b.usageCount || 0)) return (a.usageCount || 0) - (b.usageCount || 0);
    return new Date(a.lastUsed || 0) - new Date(b.lastUsed || 0);
  })[0];
}

function validateDraft(draft) {
  const required = ["issueNumber", "date", "title", "slug", "category", "readingTime", "editorNoteTopicIntroduction", "scenario", "question", "excerpt", "articleSections", "keyPoints", "references", "disclaimer"];
  const missing = required.filter((key) => draft[key] === undefined || draft[key] === null || draft[key] === "");
  if (missing.length || !draft.articleSections?.mainArticle || !draft.articleSections?.whyThisMatters || !Array.isArray(draft.keyPoints) || !Array.isArray(draft.references)) {
    throw new Error(`Generated draft is missing required fields: ${missing.join(", ") || "article content"}`);
  }
  const combined = `${draft.scenario} ${draft.articleSections.whyThisMatters} ${draft.articleSections.mainArticle}`.toLowerCase();
  if (/article content will be added|placeholder text|content goes here/.test(combined)) throw new Error("Generated draft contains placeholder text.");
  if (!dryRun && draft.articleSections.mainArticle.trim().split(/\s+/).length < 500) throw new Error("Generated Main Article is too short for a complete five-minute draft.");
  if (!dryRun && (draft.keyPoints.length < 3 || draft.keyPoints.length > 5)) throw new Error("Generated draft must contain 3–5 key points.");
  const scenarioSentences = (String(draft.scenario).match(/[.!?]+(?=\s|$)/g) || []).length;
  if (!dryRun && (scenarioSentences < 3 || scenarioSentences > 5)) throw new Error("Generated Clinical Scenario must contain 3–5 concise sentences.");
}

async function callOpenAI(systemPrompt, userPrompt) {
  if (!process.env.OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is missing.");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: { "Authorization": `Bearer ${process.env.OPENAI_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: process.env.OPENAI_MODEL || "gpt-5.6",
        instructions: systemPrompt,
        input: userPrompt,
        store: false,
        text: { format: { type: "json_object" } }
      }),
      signal: controller.signal
    });
    if (response.status === 429) throw new Error("OpenAI rate limit reached (HTTP 429).");
    if (!response.ok) throw new Error(`OpenAI generation failed (HTTP ${response.status}): ${await response.text()}`);
    const data = await response.json();
    const text = data.output_text || data.output?.flatMap((item) => item.content || []).find((item) => item.type === "output_text")?.text;
    if (!text) throw new Error("OpenAI returned no draft text.");
    return JSON.parse(text);
  } finally {
    clearTimeout(timeout);
  }
}

function writeLog(result) {
  fs.mkdirSync(logDir, { recursive: true });
  const stamp = generatedAt.replace(/[:.]/g, "-");
  fs.writeFileSync(path.join(logDir, `${stamp}.json`), `${JSON.stringify(result, null, 2)}\n`);
}

try {
  const issueWindow = loadWindowScript(issuesPath);
  const topicWindow = loadWindowScript(topicsPath);
  const promptWindow = loadWindowScript(promptPath);
  const issues = issueWindow.GENEDR_WEEKLY_ISSUES || [];
  const topics = topicWindow.GENEDR_WEEKLY_TOPICS || [];
  const topic = selectTopic(topics, issues);
  if (!topic) throw new Error("No active non-duplicate topic is available.");
  const issueNumber = Math.max(0, ...issues.map((issue) => Number(issue.issueNumber) || 0)) + 1;
  const date = new Intl.DateTimeFormat("en-CA", { timeZone: process.env.GENEDR_TIMEZONE || "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const recentTopics = [...issues].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8).map((issue) => issue.title);
  const prompt = promptWindow.GENEDR_WEEKLY_AI_PROMPT;
  const generated = dryRun ? {
    issueNumber, date, title: `[Dry Run] ${topic.title}`, subtitle: "Workflow validation draft", slug: `dry-run-${slugify(topic.title)}-${issueNumber}`,
    category: topic.category, readingTime: "5 min read", editorNoteTopicIntroduction: "This topic has important implications for genetics practice. It can shape how clinicians approach evaluation and communicate uncertainty. Understanding its uses and limitations supports more thoughtful patient care.", scenario: "A fictional patient has an unexplained finding. Initial evaluation does not identify the cause. The condition continues to evolve without a confirmed diagnosis.", question: "What should the clinical team consider next?", excerpt: "Dry-run excerpt.",
    articleSections: { whyThisMatters: "Dry-run validation content.", mainArticle: "Dry-run validation article content." }, keyPoints: ["Dry-run clinical pearl."], references: ["Suggested reference to verify."],
    disclaimer: "The clinical scenario is fictional and created for educational purposes. It does not represent an actual patient."
  } : await callOpenAI(prompt.systemPrompt, prompt.buildUserPrompt({ topic: topic.title, category: topic.category, audience: "Auto", issueNumber, date, recentTopics }));
  let retrievedReferences = generated.references;
  let referenceWarnings = [];
  if (!dryRun) {
    const referenceContext = {
      window: { GENEDR_WEEKLY_REFERENCE_CONFIG: { tool: "genedr_weekly_github_action", email: process.env.NCBI_CONTACT_EMAIL || "", timeoutMs: 20000, maxReferences: 8, defaultMode: "recent-plus-landmark" } },
      fetch, URLSearchParams, AbortController, setTimeout, clearTimeout, Date, Promise
    };
    vm.createContext(referenceContext);
    vm.runInContext(fs.readFileSync(referencesPath, "utf8"), referenceContext, { filename: referencesPath });
    const referenceResult = await referenceContext.window.GeneDrWeeklyReferences.retrieve(topic.title, "recent-plus-landmark");
    retrievedReferences = referenceResult.references;
    referenceWarnings = referenceResult.warnings;
  }
  const draft = { ...generated, references: retrievedReferences, issueNumber, date, category: topic.category, slug: slugify(generated.slug || generated.title), status: "draft", referencesNeedVerification: true, generation: { generatedAt, selectedTopic: topic.title, workflow: "github-actions-weekly", result: "success", referenceMode: "recent-plus-landmark", referenceWarnings } };
  validateDraft(draft);
  if (issues.some((issue) => Number(issue.issueNumber) === issueNumber)) throw new Error(`Duplicate issue number ${issueNumber}; no file was changed.`);
  if (issues.some((issue) => issue.slug === draft.slug)) throw new Error(`Duplicate slug ${draft.slug}; no file was changed.`);
  if (recentTopics.some((title) => title.toLowerCase().includes(topic.title.toLowerCase()))) throw new Error(`Topic duplication detected for ${topic.title}.`);

  if (!dryRun) {
    fs.mkdirSync(outputDir, { recursive: true });
    const issueFile = path.join(outputDir, `${draft.slug}.json`);
    if (fs.existsSync(issueFile)) throw new Error(`Issue file already exists: ${issueFile}`);
    fs.writeFileSync(issueFile, `${JSON.stringify(draft, null, 2)}\n`, { flag: "wx" });
    issues.push(draft);
    fs.writeFileSync(issuesPath, `window.GENEDR_WEEKLY_ISSUES = ${JSON.stringify(issues, null, 2)};\n`);
    const topicEntry = topics.find((item) => item.title === topic.title);
    topicEntry.lastUsed = date;
    topicEntry.usageCount = (topicEntry.usageCount || 0) + 1;
    fs.writeFileSync(topicsPath, `window.GENEDR_WEEKLY_TOPICS = ${JSON.stringify(topics, null, 2)};\n`);
    process.stdout.write(`GENEDR_GENERATED_FILE=${path.relative(root, issueFile)}\n`);
    if (process.env.GITHUB_ENV) fs.appendFileSync(process.env.GITHUB_ENV, `GENEDR_GENERATED_FILE=${path.relative(root, issueFile)}\n`);
  }
  writeLog({ generatedAt, selectedTopic: topic.title, selectedCategory: topic.category, issueNumber, slug: draft.slug, status: "draft", result: dryRun ? "dry-run-success" : "success" });
  console.log(`${dryRun ? "Dry run" : "Draft generation"} completed for Issue #${issueNumber}: ${topic.title}`);
} catch (error) {
  writeLog({ generatedAt, status: "draft-not-created", result: "failure", error: error.message });
  console.error(error.message);
  process.exitCode = 1;
}

export { selectTopic, slugify, validateDraft };
