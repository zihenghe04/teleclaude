/* ============================================
   Notes App - Client-side SPA
   Hash-based routing, Markdown rendering, search
   ============================================ */

// ---- Configuration ----
const CONFIG = {
  siteName: 'My Notes',
  siteDescription: 'A personal space for notes, learnings, and collected wisdom.',
  notesPath: 'notes/',
  manifestFile: 'notes/notes.json',
};

// ---- State ----
let notesData = null;
let currentRoute = '';

// ---- Markdown Setup ----
function initMarked() {
  marked.setOptions({
    highlight: function (code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
    breaks: false,
    gfm: true,
  });
}

// ---- Router ----
function getRoute() {
  const hash = window.location.hash.slice(1) || '/';
  return hash;
}

function navigate(path) {
  window.location.hash = path;
}

async function handleRoute() {
  const route = getRoute();
  if (route === currentRoute) return;
  currentRoute = route;

  if (!notesData) {
    await loadNotesData();
  }

  if (route.startsWith('/note/')) {
    const slug = route.slice(6);
    await renderNoteView(slug);
  } else if (route.startsWith('/category/')) {
    const category = route.slice(10);
    renderHome(category);
  } else {
    renderHome();
  }
}

// ---- Data Loading ----
async function loadNotesData() {
  try {
    const res = await fetch(CONFIG.manifestFile);
    if (!res.ok) throw new Error('Failed to load notes manifest');
    notesData = await res.json();
  } catch (e) {
    console.error('Error loading notes data:', e);
    notesData = { notes: [], categories: [] };
  }
}

// ---- Render: Home ----
function renderHome(activeCategory) {
  const app = document.getElementById('app');
  const notes = notesData.notes || [];
  const categories = notesData.categories || [];

  const filteredNotes = activeCategory
    ? notes.filter((n) => n.category === activeCategory)
    : notes;

  // Sort by date descending
  filteredNotes.sort((a, b) => new Date(b.date) - new Date(a.date));

  const categoryMap = {};
  categories.forEach((c) => (categoryMap[c.id] = c));

  const totalNotes = notes.length;
  const totalCategories = categories.length;
  const totalTags = [...new Set(notes.flatMap((n) => n.tags || []))].length;

  app.innerHTML = `
    <section class="hero fade-in">
      <h1>${CONFIG.siteName}</h1>
      <p>${CONFIG.siteDescription}</p>
      <div class="hero-stats">
        <div class="hero-stat">
          <div class="stat-number">${totalNotes}</div>
          <div class="stat-label">Notes</div>
        </div>
        <div class="hero-stat">
          <div class="stat-number">${totalCategories}</div>
          <div class="stat-label">Categories</div>
        </div>
        <div class="hero-stat">
          <div class="stat-number">${totalTags}</div>
          <div class="stat-label">Tags</div>
        </div>
      </div>
    </section>

    <section class="filter-section fade-in">
      <div class="filter-tabs">
        <button class="filter-tab ${!activeCategory ? 'active' : ''}"
                onclick="navigate('/')">All</button>
        ${categories
          .map(
            (c) => `
          <button class="filter-tab ${activeCategory === c.id ? 'active' : ''}"
                  onclick="navigate('/category/${c.id}')">
            ${c.icon} ${c.name}
          </button>
        `
          )
          .join('')}
      </div>
    </section>

    <section class="notes-section">
      ${
        filteredNotes.length === 0
          ? `<div class="empty-state">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2z"/>
                <path d="M8 10h8M8 14h5"/>
              </svg>
              <h3>No notes yet</h3>
              <p>This category is empty.</p>
            </div>`
          : `<div class="notes-grid">
              ${filteredNotes.map((note) => renderNoteCard(note, categoryMap)).join('')}
            </div>`
      }
    </section>
  `;

  window.scrollTo(0, 0);
}

function renderNoteCard(note, categoryMap) {
  const cat = categoryMap[note.category] || { name: note.category, icon: '' };
  const catClass = `cat-${note.category}`;
  const accentClass = `card-accent-${note.category}`;
  const tags = (note.tags || [])
    .map((t) => `<span class="note-card-tag">${t}</span>`)
    .join('');

  return `
    <article class="note-card ${accentClass}" onclick="navigate('/note/${note.slug}')">
      <div class="note-card-header">
        <span class="note-card-category ${catClass}">${cat.icon} ${cat.name}</span>
        <span class="note-card-date">${formatDate(note.date)}</span>
      </div>
      <h3>${note.title}</h3>
      <p>${note.description || ''}</p>
      ${tags ? `<div class="note-card-tags">${tags}</div>` : ''}
    </article>
  `;
}

// ---- Render: Note View ----
async function renderNoteView(slug) {
  const app = document.getElementById('app');
  const note = (notesData.notes || []).find((n) => n.slug === slug);

  if (!note) {
    app.innerHTML = `
      <div class="note-view fade-in">
        <a href="#/" class="note-back">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back
        </a>
        <div class="empty-state">
          <h3>Note not found</h3>
          <p>The note you're looking for doesn't exist.</p>
        </div>
      </div>`;
    return;
  }

  // Show loading
  app.innerHTML = `
    <div class="note-view">
      <a href="#/" class="note-back">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        Back
      </a>
      <div class="loading"><div class="loading-spinner"></div></div>
    </div>`;

  try {
    const res = await fetch(CONFIG.notesPath + note.file);
    if (!res.ok) throw new Error('Failed to load note');
    const markdown = await res.text();
    const htmlContent = marked.parse(markdown);

    const cat = (notesData.categories || []).find(
      (c) => c.id === note.category
    ) || { name: note.category, icon: '' };
    const catClass = `cat-${note.category}`;
    const tags = (note.tags || [])
      .map((t) => `<span class="note-meta-tag">${t}</span>`)
      .join('');

    app.innerHTML = `
      <article class="note-view fade-in">
        <a href="#/" class="note-back">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back to notes
        </a>
        <header class="note-header">
          <h1>${note.title}</h1>
          <div class="note-meta">
            <span class="note-meta-category ${catClass}">${cat.icon} ${cat.name}</span>
            <span class="note-meta-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              ${formatDate(note.date)}
            </span>
            ${tags ? `<div class="note-meta-tags">${tags}</div>` : ''}
          </div>
        </header>
        <div class="note-content">${htmlContent}</div>
      </article>
    `;

    // Add copy buttons to code blocks
    addCopyButtons();

    // Build TOC
    buildTOC();

    // Update page title
    document.title = `${note.title} - ${CONFIG.siteName}`;

    window.scrollTo(0, 0);
  } catch (e) {
    console.error('Error loading note:', e);
    app.innerHTML = `
      <div class="note-view fade-in">
        <a href="#/" class="note-back">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back
        </a>
        <div class="empty-state">
          <h3>Error loading note</h3>
          <p>Something went wrong. Please try again.</p>
        </div>
      </div>`;
  }
}

// ---- Copy Button for Code Blocks ----
function addCopyButtons() {
  document.querySelectorAll('.note-content pre').forEach((pre) => {
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const code = pre.querySelector('code');
      if (code) {
        await navigator.clipboard.writeText(code.textContent);
        btn.textContent = 'Copied!';
        setTimeout(() => (btn.textContent = 'Copy'), 2000);
      }
    });
    pre.appendChild(btn);
  });
}

// ---- Table of Contents ----
function buildTOC() {
  const content = document.querySelector('.note-content');
  if (!content) return;

  const headings = content.querySelectorAll('h2, h3');
  if (headings.length < 3) return; // Skip TOC for short articles

  // Add IDs to headings
  headings.forEach((h, i) => {
    if (!h.id) {
      h.id = 'heading-' + i;
    }
  });

  const tocHTML = `
    <nav class="toc-wrapper">
      <div class="toc">
        <div class="toc-title">Table of Contents</div>
        ${Array.from(headings)
          .map(
            (h) => `
          <a href="#${h.id}" class="toc-${h.tagName.toLowerCase()}"
             onclick="smoothScroll(event, '${h.id}')">
            ${h.textContent}
          </a>
        `
          )
          .join('')}
      </div>
    </nav>
  `;

  const noteView = document.querySelector('.note-view');
  if (noteView) {
    noteView.insertAdjacentHTML('beforeend', tocHTML);
  }

  // Scroll spy
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          document.querySelectorAll('.toc a').forEach((a) => a.classList.remove('active'));
          const tocLink = document.querySelector(`.toc a[href="#${entry.target.id}"]`);
          if (tocLink) tocLink.classList.add('active');
        }
      });
    },
    { rootMargin: '-80px 0px -70% 0px' }
  );

  headings.forEach((h) => observer.observe(h));
}

function smoothScroll(e, id) {
  e.preventDefault();
  const el = document.getElementById(id);
  if (el) {
    const top = el.getBoundingClientRect().top + window.scrollY - 80;
    window.scrollTo({ top, behavior: 'smooth' });
  }
}

// ---- Search ----
function toggleSearch() {
  const overlay = document.getElementById('searchOverlay');
  const input = document.getElementById('searchInput');
  const isActive = overlay.classList.contains('active');

  if (isActive) {
    overlay.classList.remove('active');
    input.value = '';
    document.getElementById('searchResults').innerHTML = '';
  } else {
    overlay.classList.add('active');
    setTimeout(() => input.focus(), 100);
  }
}

function initSearch() {
  const overlay = document.getElementById('searchOverlay');
  const input = document.getElementById('searchInput');
  const results = document.getElementById('searchResults');

  // Close on background click
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) toggleSearch();
  });

  // Keyboard shortcut
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      toggleSearch();
    }
    if (e.key === 'Escape' && overlay.classList.contains('active')) {
      toggleSearch();
    }
  });

  // Search input
  input.addEventListener('input', (e) => {
    const query = e.target.value.trim().toLowerCase();
    if (!query) {
      results.innerHTML = '';
      return;
    }

    const notes = notesData ? notesData.notes || [] : [];
    const filtered = notes.filter((n) => {
      const searchable = [
        n.title,
        n.description || '',
        ...(n.tags || []),
        n.category,
      ]
        .join(' ')
        .toLowerCase();
      return searchable.includes(query);
    });

    if (filtered.length === 0) {
      results.innerHTML = `<div class="search-empty">No results found for "${e.target.value}"</div>`;
      return;
    }

    results.innerHTML = filtered
      .map(
        (n) => `
      <a class="search-result-item" href="#/note/${n.slug}" onclick="toggleSearch()">
        <div class="result-title">${n.title}</div>
        <div class="result-desc">${n.description || ''}</div>
      </a>
    `
      )
      .join('');
  });
}

// ---- Theme ----
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';

  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);

  // Toggle highlight.js theme
  document.getElementById('hljs-light').disabled = next === 'dark';
  document.getElementById('hljs-dark').disabled = next === 'light';
}

function initTheme() {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');

  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('hljs-light').disabled = theme === 'dark';
  document.getElementById('hljs-dark').disabled = theme === 'light';
}

// ---- Helpers ----
function formatDate(dateStr) {
  const date = new Date(dateStr + 'T00:00:00');
  const options = { year: 'numeric', month: 'short', day: 'numeric' };
  return date.toLocaleDateString('en-US', options);
}

// ---- Init ----
async function init() {
  initTheme();
  initMarked();
  initSearch();
  await handleRoute();
  window.addEventListener('hashchange', handleRoute);
}

// Start the app
init();
