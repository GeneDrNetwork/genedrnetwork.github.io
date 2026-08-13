# GeneDr Monthly Story exports

The static GeneDr Monthly Content Manager stores drafts in the administrator's browser and exports publication records for deployment.

To prepare a Story for the public website:

1. Open `/admin/genedr-weekly/`.
2. Paste the complete finalized Story into **Complete Gene Detective Story**, or choose a `.docx`/text-based `.pdf` and select **Import Selected File**.
3. For pasted text, select **Parse Story & Create Draft**. Imported files are parsed automatically.
4. Review or regenerate the editable subtitle and homepage teaser.
5. Select **Preview Homepage Feature** to review the original GeneDr Weekly-style two-column feature card and permanent Editor’s Note.
6. Select **Preview Full Story** to review the dedicated Story page and its actual narrative headings.
7. Select **Publish & Download**.
8. Send the downloaded `genedr-weekly-issues.js` file to Codex for repository deployment.

To revise an existing publication, select **Edit Published Issue** in its library row. The manager locks its Story number, issue number, month, publication date, and slug, while leaving its title, subtitle, teaser, reading time, author information, and complete Story content editable. Use **Preview Changes**, then **Update Publication**. The downloaded publishing file replaces the matching slug, so the revision retains its route and does not create an Archive duplicate.

DOCX and PDF extraction happens locally in the browser. The manager places extracted text in the same editable Story box. Metadata generation affects only the subtitle and teaser; it never changes `storyContent`. Scanned/image-only PDFs require OCR before import. The homepage displays one concise Story Preview teaser rather than a teaser plus a second excerpt.

The GeneDr Monthly Editor’s Note is permanent publication text stored in `assets/genedr-weekly.js`. It is applied automatically to every monthly Story and is not part of the monthly editing workflow.

The public static site reads `data/genedr-weekly-issues.js`. The original GeneDr Weekly issue remains in that array with `publicationType: "legacy-weekly"`. New publications use `publicationType: "gene-detective-story"` and store the complete pasted or imported source in `storyContent`.
