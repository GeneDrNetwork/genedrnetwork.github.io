# GeneDr Weekly issue exports

The static Content Manager exports one JSON file per issue into this folder format.

To publish an issue:

1. Review and approve the issue in `/admin/genedr-weekly/`.
2. Use **Download JSON** and place the file in this directory.
3. Add the same issue object to the array in `data/genedr-weekly-issues.js`.
4. Set `status` to `published` only after the publication confirmation review.
5. Commit and deploy both files.

Files in this folder are content records. The public site reads the aggregated `data/genedr-weekly-issues.js` file so it remains compatible with GitHub Pages and direct static hosting.
