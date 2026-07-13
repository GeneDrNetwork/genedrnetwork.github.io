(function () {
  const config = window.GENEDR_WEEKLY_EMAIL_CONFIG || {};

  class SubscriberEmailError extends Error {
    constructor(code, message, status = 0, details = null) {
      super(message);
      this.name = "SubscriberEmailError";
      this.code = code;
      this.status = status;
      this.details = details;
    }
  }

  function articleUrl(issue) {
    return `${String(config.siteBaseUrl || location.origin).replace(/\/$/, "")}/genedr-weekly/article.html?issue=${encodeURIComponent(issue.slug)}`;
  }

  function buildPreview(issue) {
    return {
      subject: `GeneDr Weekly Issue #${issue.issueNumber}: ${issue.title}`,
      title: issue.title,
      issueNumber: issue.issueNumber,
      date: window.GeneDrWeekly.formatDate(issue.date),
      excerpt: issue.excerpt,
      articleUrl: articleUrl(issue)
    };
  }

  async function request(action, issue, options = {}) {
    if (issue.status !== "published") throw new SubscriberEmailError("NOT_PUBLISHED", "Only a published issue can be emailed to subscribers.");
    if (!config.endpoint) throw new SubscriberEmailError("NO_CONNECTION", "The secure subscriber-email endpoint is not configured.");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), Number(config.timeoutMs) || 30000);
    try {
      const response = await fetch(config.endpoint, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, issue, articleUrl: articleUrl(issue), ...options }),
        signal: controller.signal
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 409) throw new SubscriberEmailError("ALREADY_SENT", "This issue has already been sent to subscribers.", response.status, result);
      if (!response.ok) throw new SubscriberEmailError(result.code || "SEND_FAILED", result.error || "Email sending failed.", response.status, result);
      return result;
    } catch (error) {
      if (error.name === "AbortError") throw new SubscriberEmailError("TIMEOUT", "The email request timed out. Please try again.");
      if (error instanceof SubscriberEmailError) throw error;
      throw new SubscriberEmailError("SEND_FAILED", "Email sending failed. Check the secure email connection and try again.");
    } finally {
      clearTimeout(timeout);
    }
  }

  window.GeneDrWeeklyEmail = { SubscriberEmailError, articleUrl, buildPreview, request };
})();
