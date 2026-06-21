const $ = (selector) => document.querySelector(selector);

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function externalLink(url, label, className = "story-link") {
  return `<a class="${className}" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} <span aria-hidden="true">&nearr;</span></a>`;
}

function storyDetails(item, type) {
  const whyLabel = type === "movie" ? "Why watch" : type === "science" ? "Why it changed science" : "Why it matters";
  const links = (item.links || []).map((link) => externalLink(link.url, link.label)).join("");
  return `
    <details class="culture-accordion">
      <summary>
        <span class="accordion-thumb visual-${escapeHtml(item.visual || "helix")}" aria-hidden="true"><span>${escapeHtml(item.monogram || "DNA")}</span></span>
        <span class="accordion-summary-copy"><span class="item-category">${escapeHtml(item.category)}</span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.year || item.subtitle || "")}</small></span>
        <span class="accordion-toggle" aria-hidden="true"></span>
      </summary>
      <div class="accordion-story">
        <p>${escapeHtml(item.story)}</p>
        ${item.background ? `<p class="story-background"><strong>Background:</strong> ${escapeHtml(item.background)}</p>` : ""}
        <p class="why-story"><strong>${whyLabel}:</strong> ${escapeHtml(item.why)}</p>
        ${links ? `<div class="story-links" aria-label="External resources">${links}</div>` : ""}
      </div>
    </details>`;
}

function featuredCard(pick, item) {
  return `<article class="feature-pick visual-${escapeHtml(item.visual || "helix")}">
    <div class="feature-copy"><span class="feature-type">${escapeHtml(pick.label)}</span><h3>${escapeHtml(item.title)}</h3>
    <p>${escapeHtml(pick.teaser)}</p><a href="#${escapeHtml(pick.section)}">Explore the story <span aria-hidden="true">&darr;</span></a></div>
    <div class="feature-mark" aria-hidden="true">${escapeHtml(item.monogram || "DNA")}</div>
  </article>`;
}

function musicCard(item) {
  return `<a class="music-card visual-${escapeHtml(item.visual)}" href="${escapeHtml(item.youtube)}" target="_blank" rel="noopener noreferrer" aria-label="Play ${escapeHtml(item.title)} by ${escapeHtml(item.artist)} on YouTube">
    <span class="music-art" aria-hidden="true"><span class="music-monogram">${escapeHtml(item.monogram)}</span><span class="play-button">&#9654;</span></span>
    <span class="music-copy"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.artist)}</span><small>Play on YouTube &nearr;</small></span>
  </a>`;
}

function artCard(item, index) {
  return `<button class="art-card visual-${escapeHtml(item.visual)}" type="button" data-art-index="${index}" aria-label="Open ${escapeHtml(item.title)} in art viewer">
    <div class="art-image" role="img" aria-label="Abstract interpretation of ${escapeHtml(item.title)}"><span aria-hidden="true">${escapeHtml(item.monogram)}</span></div>
    <div class="art-caption"><span>${escapeHtml(item.category)}</span><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.artist)}</p><small>Open artwork</small></div>
  </button>`;
}

function wireCarousel(arts) {
  const carousel = $("#arts-carousel");
  const viewer = $("#art-viewer");
  const closeButton = $("#art-viewer-close");
  const scroll = (direction) => carousel.scrollBy({ left: direction * carousel.clientWidth * 0.78, behavior: "smooth" });
  $("#art-prev").addEventListener("click", () => scroll(-1));
  $("#art-next").addEventListener("click", () => scroll(1));
  carousel.addEventListener("click", (event) => {
    const card = event.target.closest("[data-art-index]");
    if (!card) return;
    const item = arts[Number(card.dataset.artIndex)];
    const image = $("#art-viewer-image");
    image.className = `art-viewer-image visual-${item.visual}`;
    image.setAttribute("aria-label", `Expanded abstract interpretation of ${item.title}`);
    image.innerHTML = `<span aria-hidden="true">${escapeHtml(item.monogram)}</span>`;
    $("#art-viewer-category").textContent = item.category;
    $("#art-viewer-title").textContent = item.title;
    $("#art-viewer-artist").textContent = item.artist;
    const sourceLink = $("#art-viewer-link");
    sourceLink.hidden = !item.link;
    if (item.link) sourceLink.href = item.link;
    viewer.showModal();
  });
  closeButton.addEventListener("click", () => viewer.close());
  viewer.addEventListener("click", (event) => {
    if (event.target === viewer) viewer.close();
  });
  carousel.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      scroll(event.key === "ArrowRight" ? 1 : -1);
    }
  });
}

async function loadCultureCenter() {
  try {
    let data = window.GENEDR_CULTURE_DATA;
    if (!data) {
      const response = await fetch("../data/movies-stories-music-arts.json");
      if (!response.ok) throw new Error("The collection could not be loaded.");
      data = await response.json();
    }
    const allItems = [...data.movies, ...data.detectiveStories, ...data.scienceStories];
    const featured = data.featured.picks.map((pick) => {
      const item = allItems.find((entry) => entry.id === pick.itemId) || data.arts.find((entry) => entry.id === pick.itemId);
      return item ? featuredCard(pick, item) : "";
    });
    $("#featured-picks").innerHTML = featured.join("");
    $("#featured-period").textContent = `${data.featured.month} ${data.featured.year} · ${featured.length} editor picks`;
    $("#movies-list").innerHTML = data.movies.map((item) => storyDetails(item, "movie")).join("");
    $("#detective-list").innerHTML = data.detectiveStories.map((item) => storyDetails(item, "detective")).join("");
    $("#music-list").innerHTML = data.music.map(musicCard).join("");
    $("#arts-carousel").innerHTML = data.arts.map(artCard).join("");
    $("#science-list").innerHTML = data.scienceStories.map((item) => storyDetails(item, "science")).join("");
    $("#review-date").textContent = `Last reviewed ${data.lastReviewed}`;
    wireCarousel(data.arts);
  } catch (error) {
    $("#culture-status").hidden = false;
    $("#culture-status").textContent = "The curated collections are temporarily unavailable. Please refresh or return soon.";
  }
}

loadCultureCenter();
