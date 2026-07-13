# GeneDr Weekly AI connection

The Content Manager is hosted on static GitHub Pages. Provider API keys must not be added to any frontend file.

The AI Draft Generator tries these connections in order:

1. A server-side endpoint configured in `assets/genedr-weekly-ai-config.js`.
2. A compatible browser-provided language model.
3. A visible “No AI connection” error when neither is available.

The server-side endpoint receives a JSON `POST` body containing `systemPrompt`, `userPrompt`, and `responseFormat`. It should call the chosen AI provider using credentials stored only on the server and return either the issue JSON object or `{ "draft": { ... } }`.

The endpoint should enforce administrator authentication, rate limits, request-size limits, and an allowlist for the website origin. It must never return provider credentials to the browser.

The GitHub Actions weekly-draft workflow uses the repository `OPENAI_API_KEY` secret securely, but it is asynchronous and is not called by the browser's Generate Draft button. GitHub Pages cannot call that workflow securely without administrator authentication. For reliable on-demand generation from the Content Manager, deploy an authenticated serverless or backend endpoint implementing the contract above and set its public URL in `assets/genedr-weekly-ai-config.js`. Keep the provider API key only in that service's secret environment.

When no endpoint is configured, the manager clearly reports that it is using a compatible browser-provided model. If neither connection exists, generation stops before an issue number or browser-storage record is created.

Generated issues are forced to `status: "draft"` in the browser regardless of the model response. Publication continues through Review, Approve, and the existing confirmation-protected Publish action.
