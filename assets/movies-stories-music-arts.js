const featuredContainer = document.querySelector("#featured-picks");
const featuredPeriod = document.querySelector("#featured-period");
const featuredStatus = document.querySelector("#featured-status");

const categoryLabels = {
  movie: "Featured Genetics-Related Movie",
  story: "Featured DNA Detective Story",
  music: "Featured DNA Music",
  art: "Featured DNA Art",
};

function formatMonth(month, year) {
  return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(
    new Date(year, month - 1, 1),
  );
}

function createFeaturedCard(item) {
  const card = document.createElement("article");
  card.className = `featured-card featured-card-${item.category}`;

  const label = document.createElement("p");
  label.className = "featured-card-label";
  label.textContent = categoryLabels[item.category] || item.category;

  const title = document.createElement("h3");
  title.textContent = item.title;

  const description = document.createElement("p");
  description.className = "featured-description";
  description.textContent = item.description;

  const link = document.createElement("a");
  link.href = item.link;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = `Explore at ${item.source_name}`;

  const updated = document.createElement("p");
  updated.className = "featured-updated";
  updated.textContent = `Last updated ${item.last_updated}`;

  card.append(label, title, description, link, updated);
  return card;
}

async function loadFeaturedPicks() {
  if (!featuredContainer) return;

  try {
    const response = await fetch("../data/movies-stories-music-arts.json");
    if (!response.ok) throw new Error("Featured picks could not be loaded.");

    const items = await response.json();
    const now = new Date();
    const currentMonth = now.getMonth() + 1;
    const currentYear = now.getFullYear();
    let picks = items.filter((item) => item.month === currentMonth && item.year === currentYear);
    let displayMonth = currentMonth;
    let displayYear = currentYear;

    if (!picks.length && items.length) {
      const newest = [...items].sort((a, b) => b.year - a.year || b.month - a.month)[0];
      displayMonth = newest.month;
      displayYear = newest.year;
      picks = items.filter((item) => item.month === displayMonth && item.year === displayYear);
    }

    featuredPeriod.textContent = picks.length
      ? `${formatMonth(displayMonth, displayYear)} collection`
      : "New selections are coming soon.";

    if (!picks.length) {
      featuredStatus.hidden = false;
      featuredStatus.textContent = "No featured picks have been published yet.";
      return;
    }

    const fragment = document.createDocumentFragment();
    picks.forEach((item) => fragment.append(createFeaturedCard(item)));
    featuredContainer.append(fragment);
  } catch (error) {
    featuredPeriod.textContent = "Monthly collection";
    featuredStatus.hidden = false;
    featuredStatus.textContent = "Featured picks are temporarily unavailable. Please check back soon.";
  }
}

loadFeaturedPicks();
