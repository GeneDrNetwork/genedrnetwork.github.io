# Secure subscriber email integration

This Cloudflare Worker is the secure integration layer between the static Content Manager and Resend. Protect its route with Cloudflare Access so only authenticated administrators can invoke it.

## Setup

1. Create a Resend Segment for GeneDr Weekly subscribers and manage contacts in Resend. Subscriber addresses remain in Resend and never enter this repository.
2. Create a Resend sending-domain API key.
3. Create a Cloudflare KV namespace for duplicate-send records and copy `wrangler.toml.example` to a private deployment configuration.
4. Add Worker secrets: `RESEND_API_KEY`, `RESEND_FROM`, `RESEND_SEGMENT_ID`, and `RESEND_TEST_EMAIL`.
5. Configure Cloudflare Access for the Worker route and restrict it to authorized administrators.
6. Deploy the Worker, then set its public URL in `assets/genedr-weekly-email-config.js`. The URL is not a credential.

The Worker creates Resend Broadcasts for the configured Segment. Each bulk message contains `{{{RESEND_UNSUBSCRIBE_URL}}}`, allowing Resend to provide and manage unsubscribe links. It counts subscribed Segment contacts server-side, records send metadata in KV, and rejects a second bulk send for the same issue unless the administrator completes the deliberate resend confirmation.
