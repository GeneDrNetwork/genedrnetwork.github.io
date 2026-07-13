(function () {
  const config = window.GENEDR_WEEKLY_REFERENCE_CONFIG || {};
  const baseUrl = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils";
  const fallbackMessage = "No recent authoritative reference was identified. Administrator review is required.";
  const modes = ["recent-only", "recent-plus-landmark", "guidelines-only", "reviews-only", "clinical-trials-only"];
  const authorityTerms = ["ACMG", "ClinGen", "FDA", "NIH", "NCCN", "GeneReviews", "consensus", "guideline"];
  const majorSources = ["new england journal of medicine", "jama", "lancet", "nature reviews", "genetics in medicine", "american journal of human genetics"];

  class ReferenceRetrievalError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ReferenceRetrievalError";
      this.code = code;
      this.userMessage = message;
    }
  }

  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const recentStartYear = () => new Date().getFullYear() - 5;
  const topicTerms = (topic) => String(topic).toLowerCase().match(/[a-z0-9]{3,}/g) || [];

  function modeFilter(mode) {
    const filters = {
      "guidelines-only": "(guideline[Publication Type] OR practice guideline[Publication Type] OR consensus[Title/Abstract] OR ACMG[Title/Abstract] OR ClinGen[Title/Abstract] OR NCCN[Title/Abstract] OR FDA[Title/Abstract])",
      "reviews-only": "(systematic review[Publication Type] OR review[Publication Type] OR meta-analysis[Publication Type])",
      "clinical-trials-only": "(clinical trial[Publication Type] OR randomized controlled trial[Publication Type])"
    };
    return filters[mode] || "";
  }

  function queryFor(topic, mode, recent) {
    const parts = [`(${topic})`];
    const filter = modeFilter(mode);
    if (filter) parts.push(filter);
    if (recent) parts.push(`("${recentStartYear()}"[Date - Publication] : "3000"[Date - Publication])`);
    return parts.join(" AND ");
  }

  async function ncbi(path, params) {
    const query = new URLSearchParams({ ...params, tool: config.tool || "genedr_weekly_reference_manager", retmode: "json" });
    if (config.email) query.set("email", config.email);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), Number(config.timeoutMs) || 20000);
    try {
      const response = await fetch(`${baseUrl}/${path}?${query}`, { signal: controller.signal });
      if (response.status === 429) throw new ReferenceRetrievalError("RATE_LIMIT", "PubMed rate limit reached. Wait briefly, then refresh references again.");
      if (!response.ok) throw new ReferenceRetrievalError("SOURCE_FAILURE", `PubMed connection failed with status ${response.status}.`);
      return response.json();
    } catch (error) {
      if (error.name === "AbortError") throw new ReferenceRetrievalError("SOURCE_FAILURE", "The PubMed reference search timed out.");
      if (error instanceof ReferenceRetrievalError) throw error;
      throw new ReferenceRetrievalError("SOURCE_FAILURE", "The PubMed reference source could not be reached.");
    } finally {
      clearTimeout(timeout);
    }
  }

  async function search(query, sort, retmax = 14) {
    const data = await ncbi("esearch.fcgi", { db: "pubmed", term: query, sort, retmax: String(retmax) });
    return data.esearchresult?.idlist || [];
  }

  function articleIds(item) {
    const ids = {};
    (item.articleids || []).forEach((entry) => { ids[String(entry.idtype).toLowerCase()] = entry.value; });
    return ids;
  }

  function yearOf(item) {
    const match = String(item.pubdate || item.epubdate || "").match(/\d{4}/);
    return match ? Number(match[0]) : 0;
  }

  function evidenceScore(item) {
    const types = (item.pubtype || []).join(" ").toLowerCase();
    if (/practice guideline|guideline/.test(types)) return 32;
    if (/systematic review|meta-analysis/.test(types)) return 28;
    if (/randomized controlled trial/.test(types)) return 27;
    if (/clinical trial/.test(types)) return 22;
    if (/review/.test(types)) return 18;
    return 8;
  }

  function authorityScore(item) {
    const haystack = `${item.title || ""} ${(item.authors || []).map((a) => a.name).join(" ")} ${item.fulljournalname || item.source || ""}`.toLowerCase();
    let score = majorSources.some((source) => haystack.includes(source)) ? 24 : 0;
    if (authorityTerms.some((term) => haystack.includes(term.toLowerCase()))) score += 26;
    return score;
  }

  function relevanceScore(item, topic, originalIndex) {
    const title = String(item.title || "").toLowerCase();
    const overlap = topicTerms(topic).filter((term) => title.includes(term)).length;
    return overlap * 7 + Math.max(0, 18 - originalIndex);
  }

  function normalize(item, topic, originalIndex) {
    const ids = articleIds(item);
    const pmid = ids.pubmed || item.uid;
    const doi = ids.doi || "";
    const year = yearOf(item);
    const authors = (item.authors || []).map((author) => author.name).filter(Boolean);
    const journal = item.fulljournalname || item.source || "";
    const score = relevanceScore(item, topic, originalIndex) + authorityScore(item) + evidenceScore(item) + Math.max(0, 22 - (new Date().getFullYear() - year) * 3);
    return {
      authors,
      title: String(item.title || "").replace(/\.$/, ""),
      journal,
      year,
      doi,
      pmid,
      url: `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`,
      score,
      evidenceScore: evidenceScore(item),
      authorityScore: authorityScore(item),
      isRecent: year >= recentStartYear()
    };
  }

  function deduplicate(items) {
    const seen = new Set();
    const unique = [];
    for (const item of items) {
      const key = item.doi ? `doi:${item.doi.toLowerCase()}` : item.pmid ? `pmid:${item.pmid}` : `title:${item.title.toLowerCase().replace(/\W/g, "")}`;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      unique.push(item);
    }
    return unique;
  }

  function format(item) {
    const authorText = item.authors.length > 6 ? `${item.authors.slice(0, 6).join(", ")}, et al` : item.authors.join(", ");
    return `${authorText}. ${item.title}. ${item.journal}. ${item.year}.${item.doi ? ` doi:${item.doi}.` : ""}${item.pmid ? ` PMID:${item.pmid}.` : ""} ${item.url}`.replace(/^\. /, "").trim();
  }

  async function retrieve(topic, mode = config.defaultMode || "recent-plus-landmark") {
    if (!topic?.trim()) throw new ReferenceRetrievalError("MISSING_TOPIC", "A title or topic is required to retrieve references.");
    if (!modes.includes(mode)) throw new ReferenceRetrievalError("INVALID_MODE", "Choose a supported reference filter.");
    const requests = [];
    if (mode === "recent-plus-landmark") {
      requests.push({ query: queryFor(topic, mode, true), sort: "pub_date", type: "recent" });
      requests.push({ query: queryFor(topic, mode, false), sort: "relevance", type: "landmark" });
    } else {
      requests.push({ query: queryFor(topic, mode, mode === "recent-only"), sort: mode === "recent-only" ? "pub_date" : "relevance", type: "filtered" });
    }
    requests.push({ query: `(${topic}) AND (GeneReviews[Book] OR ACMG[Title/Abstract] OR ClinGen[Title/Abstract] OR guideline[Publication Type])`, sort: "relevance", type: "authority" });

    const ids = [];
    for (const request of requests) {
      const result = await search(request.query, request.sort, request.type === "authority" ? 6 : request.type === "landmark" ? 30 : 14);
      result.forEach((id) => { if (!ids.includes(id)) ids.push(id); });
      await delay(380);
    }
    if (!ids.length) return { references: [fallbackMessage], records: [], warnings: ["NO_RESULTS"] };
    const summary = await ncbi("esummary.fcgi", { db: "pubmed", id: ids.join(","), version: "2.0" });
    const records = ids.map((id, index) => summary.result?.[id] ? normalize(summary.result[id], topic, index) : null).filter(Boolean);
    let ranked = deduplicate(records).sort((a, b) => b.score - a.score);
    if (mode === "recent-only") ranked = ranked.filter((item) => item.isRecent);
    if (mode === "recent-plus-landmark") {
      const recent = ranked.filter((item) => item.isRecent).slice(0, 6);
      const landmark = ranked.filter((item) => !item.isRecent && (item.evidenceScore >= 22 || item.authorityScore >= 24)).slice(0, 2);
      ranked = deduplicate([...recent, ...landmark]);
    }
    ranked = ranked.slice(0, Number(config.maxReferences) || 8);
    if (!ranked.length) return { references: [fallbackMessage], records: [], warnings: ["NO_RESULTS"] };
    const warnings = [];
    const duplicateCount = records.length - deduplicate(records).length;
    if (duplicateCount) warnings.push(`${duplicateCount} duplicate reference${duplicateCount === 1 ? " was" : "s were"} removed.`);
    const missingIdentifiers = ranked.filter((item) => !item.doi && !item.pmid).length;
    if (missingIdentifiers) warnings.push(`${missingIdentifiers} verified record${missingIdentifiers === 1 ? " is" : "s are"} missing both DOI and PMID.`);
    return { references: ranked.map(format), records: ranked, warnings };
  }

  window.GeneDrWeeklyReferences = { ReferenceRetrievalError, fallbackMessage, modes, recentStartYear, retrieve };
})();
