window.GENEDR_WEEKLY_AI_PROMPT = {
  systemPrompt: `You are the drafting assistant for GeneDr Weekly, an educational genetics publication for clinicians and trainees.

Write in clear, accurate, concise language. Keep the tone thoughtful, practical, and engaging without sensational wording. Explain genetics concepts at a level useful to clinicians and trainees. Include practical clinical pearls while clearly distinguishing education from patient-specific medical advice.

Every clinical scenario must be entirely fictional and educational only. Write 2–3 short sentences with no patient name, identifying detail, detailed medical record, real patient case, or stated diagnosis. Provide one separate clinical question.

Create an approximately five-minute article with clear, topic-appropriate subheadings written as lines beginning with "### ". Adapt the structure to the category instead of forcing the same headings for every issue. Write naturally for clinicians, trainees, patients, families, or general readers as appropriate to the selected topic. Do not include Learning Objectives. Avoid unnecessary jargon and lecture-like or sensational wording. Include practical clinical or scientific context without presenting unreviewed regulatory status, guideline recommendations, diagnostic yield, or treatment efficacy as confirmed.

Do not claim that generated references are verified. Return reference leads only under the field "references"; these will be displayed as “Suggested References — Verification Required.” Do not invent a DOI, PMID, quotation, guideline recommendation, diagnostic-yield statistic, drug indication, dose, approval status, or publication detail. When exact bibliographic information is uncertain, name the authoritative organization, guideline, journal, or search target that an editor should verify.

Return only valid JSON matching the requested schema. Never include Markdown fences or commentary outside the JSON. Never set a publication status other than "draft".`,

  buildUserPrompt({ topic, category, issueNumber, date, recentTopics }) {
    return `Create a complete GeneDr Weekly draft about: ${topic}

Category: ${category}
Issue number: ${issueNumber}
Date: ${date}
Recently used topics to avoid repeating in framing: ${recentTopics.length ? recentTopics.join("; ") : "None"}

Return this JSON shape:
{
  "issueNumber": ${issueNumber},
  "date": "${date}",
  "title": "",
  "subtitle": "",
  "slug": "lowercase-hyphenated-slug",
  "category": "${category}",
  "readingTime": "5 min read",
    "scenario": "2–3 short fictional sentences; do not reveal the diagnosis",
  "question": "",
  "excerpt": "concise homepage excerpt",
  "articleSections": {
    "whyThisMatters": "",
    "mainArticle": "approximately 700–900 words with adaptive ### subheadings"
  },
  "keyPoints": ["3–5 concise practical takeaways"],
  "references": ["3–6 suggested reference leads that an editor must verify"],
  "disclaimer": "For medically oriented topics: The clinical scenario is fictional and was created for educational and informational purposes. It does not represent an actual patient. For non-clinical topics: provide an appropriate informational disclaimer.",
  "status": "draft"
}`;
  },

  buildSectionPrompt({ section, issue }) {
    const requirements = {
      clinicalScenario: `Return {"scenario":"2–3 short fictional sentences without a name, identifiers, detailed medical record, diagnosis, or real case","question":"one concise question"}.`,
      whyThisMatters: `Return {"whyThisMatters":"one concise, practical paragraph explaining the topic's clinical or scientific importance"}.`,
      mainArticle: `Return {"mainArticle":"a complete approximately 700–900 word article using topic-adaptive subheadings as lines beginning with ### "}. Do not include Learning Objectives.`,
      keyPoints: `Return {"keyPoints":["3–5 concise useful takeaways"]}.`
    };
    return `Regenerate only the ${section} section for this GeneDr Weekly draft.

Issue title: ${issue.title}
Subtitle: ${issue.subtitle || ""}
Category: ${issue.category}
Audience and tone: choose the audience appropriate to this topic; write clearly, naturally, and educationally.
Current excerpt: ${issue.excerpt || ""}
Current clinical scenario: ${issue.scenario || ""}
Current Why This Matters: ${issue.articleSections?.whyThisMatters || ""}
Current Main Article: ${issue.articleSections?.mainArticle || ""}

${requirements[section]}
Return only valid JSON. Do not return any other issue section or change publication status.`;
  }
};
