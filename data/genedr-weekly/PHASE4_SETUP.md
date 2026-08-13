# GeneDr Monthly operations

## Story publishing

GeneDr Monthly is a formatting and publishing workflow, not a writing system. The website does not call an AI model or generate references or article sections.

The Content Manager accepts one complete finalized Gene Detective Story as pasted text, DOCX, or text-based PDF. File extraction happens locally in the browser. It detects likely headings and metadata without changing wording and provides editable generation controls for the subtitle, homepage teaser, and short homepage excerpt. The permanent GeneDr Monthly Editor’s Note is applied automatically and is not an issue-specific manager field. Homepage preview restores the original GeneDr Weekly two-column card; full-page preview uses the Story’s actual headings. Draft and published states are stored in browser local storage.

Because the site is hosted on static GitHub Pages, a browser cannot securely commit to the repository. **Publish & Download** marks the Story published in that browser and downloads a complete repository-ready `genedr-weekly-issues.js` file. Send that file to Codex for the final commit and deployment.

## PDF export

The Story page and Content Manager preview use browser print-to-PDF. This produces selectable text rather than a screenshot. Choose **Export to PDF**, select **Save as PDF**, and use the generated `GeneDr-Monthly-Gene-Detective-Story-...` filename.
