(function () {
  const config = window.GENEDR_WEEKLY_AI_CONFIG || {};
  const promptTemplate = window.GENEDR_WEEKLY_AI_PROMPT;
  const requiredFields = [
    "issueNumber", "date", "title", "slug", "category", "readingTime", "scenario",
    "question", "excerpt", "articleSections", "keyPoints", "references", "disclaimer"
  ];

  class DraftGenerationError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "DraftGenerationError";
      this.code = code;
      this.userMessage = message;
    }
  }

  function parseResponse(value) {
    if (value && typeof value === "object") return value.draft || value;
    const text = String(value || "").trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
    try {
      const parsed = JSON.parse(text);
      return parsed.draft || parsed;
    } catch (error) {
      throw new DraftGenerationError("GENERATION_FAILURE", "The AI response was not valid issue JSON. Please try again.");
    }
  }

  function validateDraft(draft) {
    const missing = requiredFields.filter((field) => {
      const value = draft?.[field];
      return value === undefined || value === null || value === "";
    });
    if (missing.length || !draft.articleSections?.mainArticle || !draft.articleSections?.whyThisMatters || !Array.isArray(draft.keyPoints) || !Array.isArray(draft.references)) {
      throw new DraftGenerationError("MISSING_FIELDS", `The generated draft is missing required fields: ${missing.join(", ") || "article content, key points, or references"}.`);
    }
    return draft;
  }

  async function generateWithEndpoint(payload, signal) {
    const response = await fetch(config.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal
    });
    if (response.status === 429) throw new DraftGenerationError("RATE_LIMIT", "The AI service rate limit was reached. Please wait and try again.");
    if (!response.ok) throw new DraftGenerationError("GENERATION_FAILURE", `Draft generation failed with service status ${response.status}.`);
    return response.json();
  }

  async function generateWithBrowserAI(payload) {
    const provider = window.LanguageModel || window.ai?.languageModel;
    if (!provider?.create) throw new DraftGenerationError("NO_CONNECTION", "No AI connection is configured. Add a server-side AI endpoint or use a browser with a compatible language model.");
    const session = await provider.create({ systemPrompt: payload.systemPrompt });
    try {
      return await session.prompt(payload.userPrompt);
    } finally {
      if (session.destroy) session.destroy();
    }
  }

  async function generateDraft({ topic, category, issueNumber, date, recentTopics = [] }) {
    if (!topic || !category || !issueNumber || !date) {
      throw new DraftGenerationError("MISSING_FIELDS", "Topic, category, issue number, and date are required.");
    }
    const payload = {
      systemPrompt: promptTemplate.systemPrompt,
      userPrompt: promptTemplate.buildUserPrompt({ topic, category, issueNumber, date, recentTopics }),
      responseFormat: "genedr-weekly-issue-json"
    };
    const controller = new AbortController();
    const timeoutMs = Number(config.timeoutMs) || 45000;
    let timeoutId;
    const timeout = new Promise((resolve, reject) => {
      timeoutId = setTimeout(() => {
        controller.abort();
        reject(new DraftGenerationError("TIMEOUT", "Draft generation timed out. Please try again."));
      }, timeoutMs);
    });
    try {
      const generation = config.endpoint
        ? generateWithEndpoint(payload, controller.signal)
        : generateWithBrowserAI(payload);
      const response = await Promise.race([generation, timeout]);
      const draft = validateDraft(parseResponse(response));
      return { ...draft, issueNumber, date, category, status: "draft", referencesNeedVerification: true };
    } catch (error) {
      if (error.name === "AbortError") throw new DraftGenerationError("TIMEOUT", "Draft generation timed out. Please try again.");
      if (error instanceof DraftGenerationError) throw error;
      throw new DraftGenerationError("GENERATION_FAILURE", "Draft generation failed. Please check the AI connection and try again.");
    } finally {
      clearTimeout(timeoutId);
    }
  }

  window.GeneDrWeeklyAI = { DraftGenerationError, generateDraft, validateDraft };
})();
