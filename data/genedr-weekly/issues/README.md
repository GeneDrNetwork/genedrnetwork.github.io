# GeneDr Monthly Story exports

The static GeneDr Monthly Content Manager stores drafts in the administrator's browser and exports publication records for deployment.

To prepare a Story for the public website:

1. Open `/admin/genedr-weekly/`.
2. Paste the complete finalized Story into **Complete Gene Detective Story**.
3. Select **Parse Story & Create Draft**.
4. Review metadata and both previews.
5. Select **Publish & Download**.
6. Send the downloaded `genedr-weekly-issues.js` file to Codex for repository deployment.

The public static site reads `data/genedr-weekly-issues.js`. The original GeneDr Weekly issue remains in that array with `publicationType: "legacy-weekly"`. New publications use `publicationType: "gene-detective-story"` and store the complete pasted source in `storyContent`.
