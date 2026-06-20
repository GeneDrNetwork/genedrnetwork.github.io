const featuredContainer = document.querySelector("#featured-picks");
const featuredPeriod = document.querySelector("#featured-period");
const featuredStatus = document.querySelector("#featured-status");
const library = document.querySelector("#culture-library");
const libraryTitle = document.querySelector("#library-title");
const libraryIntro = document.querySelector("#library-intro");
const libraryItems = document.querySelector("#library-items");
const categoryButtons = [...document.querySelectorAll("[data-category]")];

const categories = {
  moviesAndDocumentaries: { title: "Genetics Movies & Documentaries", intro: "Films and series that bring genetic discovery, rare disease, biotechnology, identity, and ethics into focus.", type: "movie", detail: "Why it connects to genetics" },
  dnaDetectiveStories: { title: "DNA Detective Stories", intro: "True stories of forensic investigation, genetic genealogy, identity, and difficult diagnoses resolved through DNA.", type: "story", detail: "Why it matters" },
  dnaMusic: { title: "DNA Music", intro: "Listen to projects that translate sequences and genetic variation into composition, sound, and shared experience.", type: "music", detail: "Why it connects to genetics" },
  dnaArts: { title: "DNA Arts", intro: "Visual and performance projects that make genomics, inheritance, identity, and medical science visible.", type: "art", detail: "Why it connects to genetics" },
};

const categoryLabels = { movie: "Movie & documentary", story: "DNA detective story", music: "DNA music", art: "DNA art" };
let programData;

function externalLink(item) {
  const link = document.createElement("a");
  link.href = item.link;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = `Explore at ${item.source_name}`;
  return link;
}

function createTag(text) {
  const tag = document.createElement("span");
  tag.className = "culture-tag";
  tag.textContent = text;
  return tag;
}

function createLibraryCard(item, config) {
  const card = document.createElement("article");
  card.className = `library-card library-card-${config.type}`;
  const meta = document.createElement("div");
  meta.className = "library-meta";
  meta.append(createTag(item.tag));
  const creator = item.year || item.artist;
  if (creator) {
    const byline = document.createElement("span");
    byline.textContent = creator;
    meta.append(byline);
  }
  const title = document.createElement("h3");
  title.textContent = item.title;
  const description = document.createElement("p");
  description.textContent = item.description;
  const relevance = document.createElement("p");
  relevance.className = "library-relevance";
  const strong = document.createElement("strong");
  strong.textContent = `${config.detail}: `;
  relevance.append(strong, item.genetics_relevance || item.importance);
  card.append(meta, title, description, relevance, externalLink(item));
  return card;
}

function showCategory(key, shouldFocus = true) {
  const config = categories[key];
  const items = programData[key] || [];
  libraryTitle.textContent = config.title;
  libraryIntro.textContent = config.intro;
  libraryItems.replaceChildren(...items.map((item) => createLibraryCard(item, config)));
  library.hidden = false;
  categoryButtons.forEach((button) => {
    const active = button.dataset.category === key;
    button.setAttribute("aria-expanded", String(active));
    button.classList.toggle("is-active", active);
  });
  if (shouldFocus) {
    library.focus({ preventScroll: true });
    library.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function findFeaturedItem(pick) {
  const key = Object.keys(categories).find((category) => categories[category].type === pick.category);
  return (programData[key] || []).find((item) => item.id === pick.item_id);
}

function createFeaturedCard(pick, monthly) {
  const item = findFeaturedItem(pick);
  if (!item) return null;
  const card = document.createElement("article");
  card.className = `featured-card featured-card-${pick.category}`;
  const label = document.createElement("p");
  label.className = "featured-card-label";
  label.textContent = categoryLabels[pick.category];
  const tag = createTag(item.tag);
  const title = document.createElement("h3");
  title.textContent = item.title;
  const description = document.createElement("p");
  description.className = "featured-description";
  description.textContent = item.description;
  const reason = document.createElement("p");
  reason.className = "featured-reason";
  reason.textContent = `Selected because: ${pick.reason_selected}`;
  const updated = document.createElement("p");
  updated.className = "featured-updated";
  updated.textContent = `Last updated ${monthly.last_updated}`;
  card.append(label, tag, title, description, reason, externalLink(item), updated);
  return card;
}

async function loadProgram() {
  try {
    const response = await fetch("../data/movies-stories-music-arts.json");
    if (!response.ok) throw new Error("Program content could not be loaded.");
    programData = await response.json();
    categoryButtons.forEach((button) => button.addEventListener("click", () => showCategory(button.dataset.category)));
    showCategory("moviesAndDocumentaries", false);

    const monthly = programData.monthlyFeaturedPicks;
    featuredPeriod.textContent = `${monthly.month} ${monthly.year} collection`;
    const cards = monthly.picks.map((pick) => createFeaturedCard(pick, monthly)).filter(Boolean);
    featuredContainer.replaceChildren(...cards);
    if (!cards.length) throw new Error("No valid featured picks were found.");
  } catch (error) {
    library.hidden = false;
    libraryTitle.textContent = "Curated library";
    libraryIntro.textContent = "The collection is temporarily unavailable. Please check back soon.";
    featuredPeriod.textContent = "Monthly collection";
    featuredStatus.hidden = false;
    featuredStatus.textContent = "Featured picks are temporarily unavailable. Please check back soon.";
  }
}

loadProgram();
