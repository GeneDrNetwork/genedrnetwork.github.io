window.GENEDR_WEEKLY_AI_PROMPT = {
  systemPrompt: `You are the drafting assistant for GeneDr Weekly, an educational genetics publication for clinicians and trainees.

Write in clear, accurate, concise language. Keep the tone thoughtful, practical, and engaging without sensational wording. Explain genetics concepts at a level useful to clinicians and trainees. Include practical clinical pearls while clearly distinguishing education from patient-specific medical advice.

Every clinical scenario must be entirely fictional and educational only. Write approximately 3–5 concise sentences with no patient name, identifying detail, detailed medical record, real patient case, stated diagnosis, or final outcome. Provide one separate clinical question that follows the scenario.

Create an approximately five-minute article with clear, topic-appropriate subheadings written as lines beginning with "### ". Adapt the structure to the category instead of forcing the same headings for every issue. Write naturally for clinicians, trainees, patients, families, or general readers as appropriate to the selected topic. Do not include Learning Objectives. Avoid unnecessary jargon and lecture-like or sensational wording. Include practical clinical or scientific context without presenting unreviewed regulatory status, guideline recommendations, diagnostic yield, or treatment efficacy as confirmed.

Do not claim that generated references are verified. Return reference leads only under the field "references"; these will be displayed as “Suggested References — Verification Required.” Do not invent a DOI, PMID, quotation, guideline recommendation, diagnostic-yield statistic, drug indication, dose, approval status, or publication detail. When exact bibliographic information is uncertain, name the authoritative organization, guideline, journal, or search target that an editor should verify.

Return only valid JSON matching the requested schema. Never include Markdown fences or commentary outside the JSON. Never set a publication status other than "draft".`,

  buildUserPrompt({ topic, category, audience = "Auto", issueNumber, date, recentTopics }) {
    const categoryGuidance = {
      "Clinical Case": "Use a reasoning-focused structure that discusses the differential approach without revealing the fictional scenario's diagnosis.",
      "Genetic Testing": "Explain what the test is, how it works, when it is considered, limitations, interpretation, and practical use.",
      "Disease Spotlight": "Explain the condition, genetic basis, clinical recognition, diagnosis, management principles, and family considerations.",
      "Drug Spotlight": "Explain the therapeutic concept, mechanism, eligible population, evidence, safety or access limitations, and practical considerations without asserting unreviewed regulatory status.",
      "Gene Detective Story": "Use a narrative discovery structure while clearly separating established evidence from inference.",
      "Guideline Update": "Explain what changed, who is affected, evidence context, limitations, and practical implementation without presenting unreviewed recommendations as confirmed.",
      "AI in Genetics": "Explain the tool or method, potential uses, evidence, bias, validation, privacy, limitations, and human oversight.",
      "Movie": "Connect the work to genetics themes, representation, scientific accuracy, ethics, and discussion points without treating fiction as medical evidence.",
      "Music & Arts": "Connect the work to genetics, identity, disability, family experience, ethics, or public understanding with an accessible cultural-analysis structure."
    };
    return `Create a complete GeneDr Weekly draft about: ${topic}

Category: ${category}
Audience: ${audience === "Auto" ? "Select the most appropriate audience from Clinicians, Residents, Medical Students, Genetic Counselors, Patients and Families, or General Public." : audience}
Category-specific structure guidance: ${categoryGuidance[category] || "Adapt the structure naturally to the topic."}
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
    "scenario": "3–5 concise fictional sentences; do not reveal the diagnosis or final outcome",
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

  buildCorePrompt({ topic, category, audience = "Auto", issueNumber, date, recentTopics }) {
    return `Create the core fields for a GeneDr Weekly draft about: ${topic}

Category: ${category}
Audience: ${audience === "Auto" ? "Select the most appropriate audience from Clinicians, Residents, Medical Students, Genetic Counselors, Patients and Families, or General Public." : audience}
Issue number: ${issueNumber}
Date: ${date}
Recently used topics to avoid repeating in framing: ${recentTopics.length ? recentTopics.join("; ") : "None"}

Return only this JSON shape:
{
  "title": "",
  "subtitle": "",
  "slug": "lowercase-hyphenated-slug",
  "readingTime": "5 min read",
  "scenario": "3–5 concise fictional sentences without the diagnosis or final outcome",
  "question": "one concise clinical question",
  "excerpt": "concise homepage excerpt",
  "whyThisMatters": "one concise practical paragraph",
  "disclaimer": "appropriate educational disclaimer"
}`;
  },

  buildSectionPrompt({ section, issue }) {
    const requirements = {
      clinicalScenario: `Return {"scenario":"3–5 concise fictional sentences without a name, identifiers, detailed medical record, diagnosis, final outcome, or real case","question":"one concise clinical question"}.`,
      whyThisMatters: `Return {"whyThisMatters":"one concise, practical paragraph explaining the topic's clinical or scientific importance"}.`,
      mainArticle: `Return {"mainArticle":"a complete approximately 700–900 word article using topic-adaptive subheadings as lines beginning with ### "}. Do not include Learning Objectives.`,
      keyPoints: `Return {"keyPoints":["3–5 concise useful takeaways"]}.`
    };
    return `Regenerate only the ${section} section for this GeneDr Weekly draft.

Issue title: ${issue.title}
Subtitle: ${issue.subtitle || ""}
Category: ${issue.category}
Audience and tone: ${issue.audience && issue.audience !== "Auto" ? issue.audience : "choose from Clinicians, Residents, Medical Students, Genetic Counselors, Patients and Families, or General Public based on the topic"}; write clearly, naturally, and educationally.
Current excerpt: ${issue.excerpt || ""}
Current clinical scenario: ${issue.scenario || ""}
Current Why This Matters: ${issue.articleSections?.whyThisMatters || ""}
Current Main Article: ${issue.articleSections?.mainArticle || ""}

${requirements[section]}
Return only valid JSON. Do not return any other issue section or change publication status.`;
  }
};
