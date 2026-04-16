## Welcome

This is your personal knowledge base — a place to collect notes, learnings, and resources as you grow. The site is powered by pure HTML/CSS/JS with no build step, hosted for free on GitHub Pages.

## How It Works

The site reads a **manifest file** (`notes/notes.json`) that lists all your notes. Each note is a **Markdown file** in the `notes/` directory. When you click a note card, the app fetches and renders the Markdown on the fly.

```
docs/
├── index.html          # Main entry point
├── css/style.css       # All styles
├── js/app.js           # Application logic
├── favicon.svg         # Site icon
└── notes/
    ├── notes.json      # Notes manifest (the index)
    ├── getting-started.md
    ├── python-tips.md
    └── ...
```

## Adding a New Note

### Step 1: Write Your Note

Create a new `.md` file in the `docs/notes/` directory:

```markdown
## Introduction

Your content here. Full Markdown is supported:

- **Bold**, *italic*, `inline code`
- Lists, tables, blockquotes
- Code blocks with syntax highlighting
- Images and links
```

### Step 2: Update the Manifest

Open `docs/notes/notes.json` and add an entry to the `notes` array:

```json
{
  "slug": "my-new-note",
  "title": "My New Note Title",
  "description": "A brief description that shows on the card.",
  "category": "tech",
  "tags": ["tag1", "tag2"],
  "date": "2026-04-16",
  "file": "my-new-note.md"
}
```

Fields:
- **slug** — URL identifier (must be unique, use kebab-case)
- **title** — Display title on the card and note page
- **description** — Short description shown on the card
- **category** — Must match a category `id` in the `categories` array
- **tags** — Array of tag strings for filtering and search
- **date** — Publication date in `YYYY-MM-DD` format
- **file** — Filename of the Markdown file in `notes/`

### Step 3: Commit and Push

```bash
git add docs/notes/my-new-note.md docs/notes/notes.json
git commit -m "Add note: My New Note Title"
git push
```

The site will update automatically via GitHub Pages.

## Managing Categories

Categories are defined in the `categories` array in `notes.json`:

```json
"categories": [
  { "id": "tech", "name": "Tech", "icon": "💻" },
  { "id": "guide", "name": "Guide", "icon": "📖" },
  { "id": "resource", "name": "Resources", "icon": "📚" },
  { "id": "thoughts", "name": "Thoughts", "icon": "💡" },
  { "id": "project", "name": "Projects", "icon": "🚀" }
]
```

To add a new category, simply add a new object to this array.

## Features

- **Dark / Light mode** — Toggle with the sun/moon button, respects system preference
- **Search** — Press `Ctrl+K` (or `Cmd+K`) to open search, filters by title, description, and tags
- **Category filter** — Click category pills on the home page to filter
- **Table of Contents** — Auto-generated for notes with 3+ headings (visible on wide screens)
- **Code highlighting** — Syntax highlighting for 180+ languages via highlight.js
- **Copy code** — Hover over code blocks to reveal a copy button
- **Responsive** — Works on desktop, tablet, and mobile
- **Print-friendly** — Clean print layout with navigation hidden

## Customization

### Site Name and Description

Edit `CONFIG` at the top of `js/app.js`:

```javascript
const CONFIG = {
  siteName: 'My Notes',
  siteDescription: 'A personal space for notes, learnings, and collected wisdom.',
  notesPath: 'notes/',
  manifestFile: 'notes/notes.json',
};
```

### Colors and Theming

All colors are defined as CSS custom properties in `css/style.css`. Modify the `:root` and `[data-theme="dark"]` blocks to change the color scheme.

## Deployment

This site is designed for **GitHub Pages**:

1. Go to your repo **Settings → Pages**
2. Under "Source", select **GitHub Actions**
3. The included workflow (`.github/workflows/pages.yml`) will deploy automatically on push

Your site will be available at: `https://<username>.github.io/<repo-name>/`
