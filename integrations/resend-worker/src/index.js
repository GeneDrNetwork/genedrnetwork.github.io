const json = (body, status = 200, origin = "") => new Response(JSON.stringify(body), {
  status,
  headers: {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Credentials": "true",
    "Vary": "Origin"
  }
});

const escapeHtml = (value = "") => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

function emailContent(issue, articleUrl, includeUnsubscribe) {
  const subject = `GeneDr Weekly Issue #${issue.issueNumber}: ${issue.title}`;
  const unsubscribe = includeUnsubscribe
    ? `<p style="margin-top:32px;font-size:12px;color:#607789"><a href="{{{RESEND_UNSUBSCRIBE_URL}}}">Unsubscribe</a> or manage your email preferences.</p>`
    : `<p style="margin-top:32px;font-size:12px;color:#607789">The subscriber broadcast will include a provider-managed unsubscribe link.</p>`;
  const html = `<div style="font-family:Arial,sans-serif;max-width:680px;margin:auto;color:#153653"><div style="padding:28px;border-radius:16px;background:linear-gradient(135deg,#1767a2,#15958f);color:white"><div style="font-family:Georgia,serif;font-size:36px;font-weight:bold">GeneDr <em>Weekly</em></div><p>Discover Genetics, One Story at a Time.</p><p><em>Five minutes of enjoyable genetics reading every week.</em></p></div><div style="padding:28px"><p><strong>Issue #${Number(issue.issueNumber)} | ${escapeHtml(issue.date)}</strong></p><h1 style="font-family:Georgia,serif;color:#087d89">${escapeHtml(issue.title)}</h1><p>${escapeHtml(issue.excerpt)}</p><p><a href="${escapeHtml(articleUrl)}" style="display:inline-block;padding:11px 18px;border-radius:9px;background:#138b96;color:white;text-decoration:none;font-weight:bold">Read the full story</a></p>${unsubscribe}</div></div>`;
  const text = `GeneDr Weekly\n\nDiscover Genetics, One Story at a Time.\n\nFive minutes of enjoyable genetics reading every week.\n\nIssue #${issue.issueNumber} | ${issue.date}\n\n${issue.title}\n\n${issue.excerpt}\n\nRead the full story:\n${articleUrl}${includeUnsubscribe ? "\n\nUnsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}" : ""}`;
  return { subject, html, text };
}

async function resendFetch(env, path, options = {}) {
  const response = await fetch(`https://api.resend.com${path}`, {
    ...options,
    headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json", ...(options.headers || {}) }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || body.error || `Resend API returned ${response.status}`);
  return body;
}

async function countRecipients(env) {
  let after = "";
  let count = 0;
  do {
    const query = new URLSearchParams({ limit: "100" });
    if (after) query.set("after", after);
    const result = await resendFetch(env, `/segments/${env.RESEND_SEGMENT_ID}/contacts?${query}`);
    const contacts = result.data || [];
    count += contacts.filter((contact) => !contact.unsubscribed).length;
    after = result.has_more && contacts.length ? contacts[contacts.length - 1].id : "";
  } while (after);
  return count;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowedOrigin = env.ADMIN_ORIGIN || "https://genedrnetwork.github.io";
    if (origin !== allowedOrigin) return json({ code: "ORIGIN_DENIED", error: "Origin not allowed." }, 403, allowedOrigin);
    if (request.method === "OPTIONS") return new Response(null, { headers: { "Access-Control-Allow-Origin": allowedOrigin, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "POST, OPTIONS" } });
    if (request.method !== "POST") return json({ error: "Method not allowed." }, 405, allowedOrigin);
    if (env.REQUIRE_ACCESS !== "false" && !request.headers.get("Cf-Access-Jwt-Assertion")) return json({ code: "AUTH_REQUIRED", error: "Administrator authentication is required." }, 401, allowedOrigin);
    if (!env.RESEND_API_KEY || !env.RESEND_FROM || !env.RESEND_SEGMENT_ID || !env.RESEND_TEST_EMAIL) return json({ code: "CONFIGURATION_ERROR", error: "Email service configuration is incomplete." }, 503, allowedOrigin);

    let payload;
    try { payload = await request.json(); } catch { return json({ error: "Invalid JSON." }, 400, allowedOrigin); }
    const { action, issue, articleUrl, resend = false, resendConfirmed = false } = payload;
    if (!issue || issue.status !== "published") return json({ code: "NOT_PUBLISHED", error: "Only published issues can be emailed." }, 400, allowedOrigin);
    const issueKey = `issue-${Number(issue.issueNumber)}`;
    const previous = await env.GENEDR_EMAIL_SENDS.get(issueKey, "json");
    if (action === "send" && previous?.status === "sent" && !(resend && resendConfirmed)) {
      return json({ code: "ALREADY_SENT", error: "This issue has already been sent to subscribers.", previous }, 409, allowedOrigin);
    }

    const sentAt = new Date().toISOString();
    try {
      if (action === "test") {
        const content = emailContent(issue, articleUrl, false);
        const result = await resendFetch(env, "/emails", { method: "POST", headers: { "Idempotency-Key": `genedr-test-${issueKey}-${Date.now()}` }, body: JSON.stringify({ from: env.RESEND_FROM, to: [env.RESEND_TEST_EMAIL], ...content }) });
        return json({ status: "test-sent", sentAt, recipientCount: 1, providerId: result.id }, 200, allowedOrigin);
      }
      if (action !== "send") return json({ error: "Unsupported email action." }, 400, allowedOrigin);
      const recipientCount = await countRecipients(env);
      const content = emailContent(issue, articleUrl, true);
      const result = await resendFetch(env, "/broadcasts", { method: "POST", body: JSON.stringify({ segment_id: env.RESEND_SEGMENT_ID, from: env.RESEND_FROM, name: `GeneDr Weekly ${issueKey}${resend ? ` resend ${sentAt}` : ""}`, preview_text: issue.excerpt, send: true, ...content }) });
      const record = { issueNumber: Number(issue.issueNumber), sentAt, recipientCount, providerId: result.id, status: "sent", resend: Boolean(resend), error: null };
      await env.GENEDR_EMAIL_SENDS.put(issueKey, JSON.stringify(record));
      return json(record, 200, allowedOrigin);
    } catch (error) {
      const record = { issueNumber: Number(issue.issueNumber), sentAt, recipientCount: 0, providerId: null, status: "failed", error: error.message };
      await env.GENEDR_EMAIL_SENDS.put(`${issueKey}-failure-${Date.now()}`, JSON.stringify(record), { expirationTtl: 2592000 });
      return json(record, 502, allowedOrigin);
    }
  }
};
