# Module: Frontend

## Overview

The frontend is a React 18 single-page application built with Vite and Tailwind CSS v3. It uses React Router v6 for client-side routing. Every page is a standalone component that owns its own state — there is no global state manager (no Redux, no Zustand, no Context). Data flows from API calls into local `useState` hooks.

---

## Stack and Config

### Vite (`vite.config.js`)

The key config is the dev-server proxy:
```js
server: {
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```
All `fetch('/api/...')` calls in the browser go to the Vite dev server, which forwards them to FastAPI on port 8000. This eliminates CORS issues during development. In production (if ever deployed), Nginx or a similar reverse proxy would handle this instead.

### Tailwind (`tailwind.config.js`)

Tailwind is configured to read CSS custom properties from `src/index.css`:
```js
theme: {
  extend: {
    colors: {
      background:   'var(--color-background)',
      surface:      'var(--color-surface)',
      border:       'var(--color-border)',
      accent:       'var(--color-accent)',
      'text-primary':   'var(--color-text-primary)',
      'text-secondary': 'var(--color-text-secondary)',
    },
    fontFamily: {
      body:    ['Inter', 'sans-serif'],
      display: ['Space Grotesk', 'sans-serif'],
    }
  }
}
```

This means changing a theme color requires only changing the CSS variable in `index.css` — Tailwind utilities like `bg-surface`, `text-text-primary`, `border-border` update everywhere automatically.

### `src/index.css` — Design Tokens

```css
:root {
  --color-background:    #0a0e17;   /* near-black, main page bg */
  --color-surface:       #111827;   /* card/panel bg */
  --color-border:        #1f2937;   /* subtle borders */
  --color-text-primary:  #f1f5f9;   /* white-ish body text */
  --color-text-secondary:#64748b;   /* muted labels */
  --color-accent:        #3b82f6;   /* blue — primary actions */
  --color-accent-glow:   rgba(59, 130, 246, 0.15); /* hover glows */
}
```

The `html` element has `class="dark"` set in `index.html` (enforced, not toggled). No light mode exists.

### Fonts (`index.html`)

Fonts are loaded via `@fontsource` npm packages, not Google Fonts CDN:
```js
// in main.jsx:
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import '@fontsource/space-grotesk/600.css'
```

This is intentional for air-gap compliance — the app must work without internet access on secure networks. All font files are bundled into the Vite build output.

---

## Routing (`src/App.jsx`)

```jsx
<BrowserRouter>
  <Navbar />
  <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
    <Routes>
      <Route path="/"               element={<Home />} />
      <Route path="/librarian"      element={<ComponentLibrarian />} />
      <Route path="/part/:partNumber" element={<PartDetail />} />
      <Route path="/block-diagram"  element={<BlockDiagram />} />
      <Route path="/stackup"        element={<StackupDesigner />} />
      <Route path="/constraints"    element={<SiPiGuide />} />
      <Route path="/drc"            element={<SchematicDrc />} />
      <Route path="/fpga"           element={<FpgaBridge />} />
      <Route path="/bom"            element={<BomAnalyzer />} />
      <Route path="/com"            element={<Navigate to="/constraints" replace />} />
      <Route path="*"              element={<Navigate to="/" replace />} />
    </Routes>
  </main>
</BrowserRouter>
```

The `max-w-7xl` container keeps content readable on wide monitors. The `Navbar` is outside the `<main>` so it sits at the top independently.

---

## `components/Navbar.jsx`

Sticky top navigation bar. Links to all 7 modules. Uses React Router's `<NavLink>` to apply an active style to the current route (`aria-current="page"` + accent underline).

The navbar is the only place that mentions all 7 routes — there's no sidebar or drawer. Mobile: collapses to a hamburger menu with a dropdown.

---

## Primitive Components (`components/ui/`)

### `card.jsx`
```jsx
<Card variant="default" | "elevated" | "ghost">
  <CardHeader>...</CardHeader>
  <CardContent>...</CardContent>
</Card>
```
Uses `bg-surface border-border` for the default variant. `elevated` adds a subtle box-shadow. `ghost` is transparent (used inside other cards).

### `badge.jsx`
```jsx
<Badge variant="default" | "success" | "warning" | "error" | "info" | "space">
  text
</Badge>
```
`space` variant is a special deep-blue badge used for space-grade/radiation-qualified parts.

### `button.jsx`
```jsx
<Button variant="primary" | "secondary" | "ghost" | "danger" size="sm" | "md" | "lg">
  Click me
</Button>
```
`primary` uses `bg-accent`. `danger` uses `bg-red-600`. All variants handle disabled state and loading state (spinner). Accessible: `aria-busy`, `aria-disabled` set correctly.

---

## Shared Components

### `UploadZone.jsx`
Drag-and-drop PDF uploader. Uses HTML5 `dragover`/`drop` events + `<input type="file">` click fallback.

Props: `onFile(file)` callback, `accept` MIME type, `label`, `loading` boolean.

State: `isDragging` (for visual feedback). On drop, validates file type before calling `onFile`.

### `DataTable.jsx`
The main component parameter table used in the librarian. Shows `ComponentData` fields as columns.

Features:
- Inline editing: clicking a cell converts it to an `<input>` with `onBlur` save
- "Accept" and "Reject" buttons per row
- AI-populated cells shown with a subtle blue tint
- null values shown as `—`
- Resizable columns (drag column headers)

### `DualCsvUpload.jsx`
Two side-by-side upload zones labeled "Baseline" and "Updated". Each independently accepts a CSV file. Once both are selected, a "Compare" button appears. Emits both files together via `onBothSelected(baseline, updated)`.

### `DeltaTable.jsx`
Table for FPGA pin-swap results. Columns: Signal Name, Old Pin, New Pin, Old Bank, New Bank, Risk Assessment.

Risk badge coloring:
- `AI_Risk_Assessment.startsWith("High")` → `<Badge variant="error">`
- `AI_Risk_Assessment.startsWith("Medium")` → `<Badge variant="warning">`
- otherwise → `<Badge variant="success">`

Sortable by any column. Expandable rows show the full AI assessment text.

### `ConstraintTable.jsx`
Editable table for SI/PI constraints. Columns: Parameter, Value, Tolerance, Unit, Net Class, Notes.

Each row has:
- Editable cells (click to edit, blur to save)
- Delete row button
- Validation highlight (red border) on empty required fields

"Add Row" button appends a blank entry. State lives in the parent page component; the table just fires callbacks.

### `SectionLabel.jsx`
A styled section header:
```jsx
<SectionLabel badge="3" badgeVariant="info">Part Library</SectionLabel>
```
Shows a horizontal rule with the label overlaid. Optional badge (e.g. count of items).

### `SummaryCard.jsx`
Metric display card used in BOM summary:
```jsx
<SummaryCard label="Critical" value={4} valueColor="red" />
```
Large number, smaller label below. Color prop controls the number color.

### `StackBar.jsx`
Horizontal segmented bar:
```jsx
<StackBar segments={[
  {label: "Low", count: 45, color: "green"},
  {label: "Medium", count: 12, color: "yellow"},
  {label: "High", count: 5, color: "orange"},
  {label: "Critical", count: 2, color: "red"},
]} total={64} />
```
Width of each segment is proportional to count/total. Used in BOM Analyzer for risk distribution.

### `ModuleGuide.jsx`
Collapsible usage guide overlay that appears at the top of a page. Contains step-by-step instructions. Engineers can collapse it after reading. State is saved to `localStorage` so it stays collapsed on refresh.

---

## Page Components

### `pages/Home.jsx`
Dashboard with a 3-column grid of module cards. Each card shows: module name, icon, brief description, and a "Launch" link. Cards animate on hover. No data fetching — purely static.

### `pages/ComponentLibrarian.jsx`
The most complex page. Manages three states:
1. **Upload state** — PDF files queued for processing (multi-file queue)
2. **Staging state** — extracted parts waiting for Accept/Reject
3. **Library state** — all accepted parts in the library

Key behaviors:
- Multi-PDF queue: files are uploaded sequentially, not in parallel (to avoid overwhelming the local LLM)
- After upload: extracted `rows` and `consolidated` data staged for review
- `DataTable` shows editable extracted parameters
- Accept sends to `/api/library/accept-parts`; Reject discards without saving
- Library section debounces search input (300ms) before calling `/api/library/search?q=`
- Part cards navigate to `/part/:partNumber`

### `pages/PartDetail.jsx`
Single-part view. Fetches `GET /api/library/{part_number}` (decoded from URL params). Shows:
- Full parameter table (all `ComponentData` fields)
- Variants section (collapsible, shows diff fields only)
- Datasheet link (opens `GET /api/datasheets/{filename}` in new tab)
- PATCH controls for Program/Part_Type fields

### `pages/FpgaBridge.jsx`
Upload both CSVs → compare → show results. Loading spinner while AI assesses (can take 30s+ for large pin lists). Error display if CSV is malformed.

### `pages/SiPiGuide.jsx`
Tab-based layout:
- **Extract Constraints** tab: PDF upload → constraint table → export
- **Design Guide** tab: interface picker + rules display + loss budget calculator + AI advisor

### `pages/BlockDiagram.jsx`
Four input modes (from library, from text, from PDF, manual). Canvas-based diagram viewer after generation. Saved diagrams list with load/delete controls.

### `pages/StackupDesigner.jsx`
Template picker → layer editor → impedance calculator → save. Impedance calculator runs client-side using the same formula as the backend (duplicated for instant feedback without a server round-trip).

### `pages/BomAnalyzer.jsx`
Upload → analyze → summary cards → detailed BOM table. Export controls shown after analysis completes.

### `pages/SchematicDrc.jsx`
Upload netlist → parse preview → full DRC → violation list. Filterable by severity and category. Export controls.

---

## `lib/downloadBlob.js`

Utility for triggering browser file downloads from API responses:
```js
export function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
```

Used by every export button after receiving `PlainTextResponse` content from the backend. The fetch call reads the response body as text, then passes it to `downloadBlob`.

---

## API Call Pattern (No Library)

All API calls use the native `fetch` API directly. The pattern is consistent across all pages:

```js
const [loading, setLoading] = useState(false)
const [error, setError] = useState(null)
const [data, setData] = useState(null)

async function handleUpload(file) {
  setLoading(true)
  setError(null)
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/upload-datasheet', { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    setData(await res.json())
  } catch (e) {
    setError(e.message)
  } finally {
    setLoading(false)
  }
}
```

Error messages from FastAPI's `HTTPException.detail` field are surfaced directly to the user. This means backend error messages should be engineer-readable.
