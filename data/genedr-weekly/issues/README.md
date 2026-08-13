# GeneDr Monthly Story exports

The static GeneDr Monthly Content Manager stores drafts in the administrator's browser and exports publication records for deployment.

To prepare a Story for the public website:

1. Open `/admin/genedr-weekly/`.
2. Paste the complete finalized Story into **Complete Gene Detective Story**, or choose a `.docx`/text-based `.pdf` and select **Import Selected File**.
3. For pasted text, select **Parse Story & Create Draft**. Imported files are parsed automatically.
4. Review metadata and both previews.
5. Select **Publish & Download**.
6. Send the downloaded `genedr-weekly-issues.js` file to Codex for repository deployment.

DOCX and PDF extraction happens locally in the browser. The manager places extracted text in the same editable Story box and suggests the opening line and homepage teaser from original Story sentences. Scanned/image-only PDFs require OCR before import.

The public static site reads `data/genedr-weekly-issues.js`. The original GeneDr Weekly issue remains in that array with `publicationType: "legacy-weekly"`. New publications use `publicationType: "gene-detective-story"` and store the complete pasted or imported source in `storyContent`.
