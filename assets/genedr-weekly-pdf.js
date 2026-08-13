(function () {
  function filename(issue) {
    const monthly = issue.publicationType === "gene-detective-story";
    const number = String(monthly ? issue.storyNumber : issue.issueNumber).padStart(3, "0");
    const title = String(issue.title).replace(/['’]/g, "").replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "");
    return `${monthly ? "GeneDr-Monthly-Gene-Detective-Story" : "GeneDr-Weekly-Legacy-Issue"}-${number}-${title}`;
  }

  function print(issue, context = "article") {
    const previousTitle = document.title;
    document.title = filename(issue);
    document.body.classList.add("weekly-printing", context === "manager" ? "weekly-print-manager" : "weekly-print-article");
    const cleanup = () => {
      document.title = previousTitle;
      document.body.classList.remove("weekly-printing", "weekly-print-manager", "weekly-print-article");
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    window.print();
    setTimeout(cleanup, 1500);
  }

  window.GeneDrWeeklyPDF = { filename, print };
})();
