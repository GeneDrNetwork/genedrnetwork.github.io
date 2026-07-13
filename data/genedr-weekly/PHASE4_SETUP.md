# GeneDr Weekly Phase 4 operations

## Monday draft workflow

The workflow is `.github/workflows/genedr-weekly-draft.yml`. It runs across the Monday morning UTC window and uses a timezone guard so daylight-saving changes are handled.

Repository settings:

- Secret: `OPENAI_API_KEY`
- Variable: `OPENAI_MODEL` (default `gpt-5.6`)
- Variable: `GENEDR_TIMEZONE` (default `America/Los_Angeles`)
- Variable: `GENEDR_SCHEDULE_WEEKDAY` (default `1`, Monday using ISO weekday numbering)
- Variable: `GENEDR_SCHEDULE_HOUR` (default `9`, local 24-hour time)
- Variable: `NCBI_CONTACT_EMAIL` (recommended public administrative contact for NCBI E-utilities requests)

The Action calculates the next issue number, avoids recent topics, balances recently used categories, creates a draft record and workflow log, and opens a review pull request. It never approves, publishes, or commits generated content to `main`.

At generation time, references are refreshed from NCBI PubMed using the default **Recent plus landmark references** ranking mode. Language-model citations are replaced by the verified retrieval result before the draft pull request is created.

To test manually, open **Actions → Generate GeneDr Weekly Draft → Run workflow**. Start with `dry_run: true`; this validates selection and output handling without calling OpenAI or creating a pull request. Run again with `dry_run: false` to test the complete review-PR flow.

## Subscriber email

The selected provider is Resend. Subscriber contacts live in a Resend Segment, not this repository. Deploy the authenticated Worker in `integrations/resend-worker/` and follow its README. Configure its URL in `assets/genedr-weekly-email-config.js`.

The Content Manager shows **Email to Subscribers** only for a published issue. It provides a branded preview, test-email action, and confirmation-protected full send. The Worker records the issue number, send time, recipient count, Resend broadcast ID, status, and error in Cloudflare KV. A second send is rejected until the additional resend confirmation is completed.

## PDF export

The article page and Content Manager preview use browser print-to-PDF. This produces selectable text rather than a screenshot. Choose **Export to PDF**, select **Save as PDF** in the browser print dialog, and use the generated `GeneDr-Weekly-Issue-...` filename. Print CSS uses US Letter sizing, page numbers, blue/teal accents, and removes navigation, sharing buttons, and administrator controls.
