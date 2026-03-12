# GDMS Space Hardware Assistant — System Architecture

## What This Application Is

The GDMS Space Hardware Assistant is a web-based design-engineering tool built to support aerospace/defense hardware teams throughout the entire PCB design lifecycle. Engineers use it to:

- Extract and store component parameters from datasheets into a searchable part library
- Detect FPGA pin-swap changes between tool exports and assess SI/PI risk
- Extract SI/PI design constraints from component datasheets
- Build and export block diagrams of system architectures
- Design and validate PCB stackups with impedance calculations
- Analyze BOMs for lifecycle risk and radiation tolerance
- Run schematic DRC against aerospace-grade rules
- Query an SI/PI design rule knowledge base

The system is architected as a **thin React frontend** talking to a **FastAPI backend** that does all heavy work: PDF parsing, AI inference, and file-backed persistence.

---

## High-Level Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React 18 + Vite + Tailwind CSS v3 | SPA, always-dark "Tactical Aerospace" theme |
| Routing | React Router v6 (BrowserRouter) | URL-based, 8 top-level routes |
| Backend | FastAPI (Python 3.14) | Async, 9 routers mounted under `/api` |
| AI | OpenAI-compatible client (`openai` package) | Pointed at local Ollama or cloud gateway via env vars |
| PDF Parsing | PyMuPDF (`fitz`) | Replaced pdfplumber which hung on complex TI datasheets |
| Persistence | JSON files in `backend/data/` | Thread-safe with `threading.Lock()` |
| Data Validation | Pydantic v2 | All models use `model_validate`, `model_dump` |
| Tests | pytest + FastAPI TestClient | 244+ passing tests; mocking via `unittest.mock.patch` |

---

## Repository Layout

```
GDMS-Space-Hardware-Assistant/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── .env                       # Local secrets (never committed)
│   ├── requirements.txt           # Python deps
│   ├── conftest.py                # pytest fixtures
│   ├── data/
│   │   ├── library.json           # Part library (thread-safe JSON store)
│   │   ├── diagrams.json          # Block diagram store
│   │   ├── datasheets/            # Uploaded PDF files
│   │   └── texts/                 # Extracted text files (audit trail)
│   ├── models/                    # Pydantic schemas
│   │   ├── component.py           # ComponentData, ComponentExtractionResult
│   │   ├── fpga.py                # PinSwap, PinDeltaResponse
│   │   ├── block_diagram.py       # BlockDiagram, Block, Connection, Port
│   │   ├── com_channel.py         # ChannelModel, Segment, COMResult
│   │   ├── bom.py                 # BOMReport, BOMLineItem, enums
│   │   ├── schematic_drc.py       # DRCReport, DRCViolation, NetlistSummary
│   │   ├── sipi_guide.py          # InterfaceSpec, DesignRule, LossBudgetResult
│   │   └── stackup.py             # Stackup, StackupLayer
│   ├── routers/                   # FastAPI route handlers (one per module)
│   │   ├── librarian.py           # Component library + datasheet upload
│   │   ├── fpga.py                # FPGA pin-swap comparison
│   │   ├── constraint.py          # SI/PI constraint extraction
│   │   ├── block_diagram.py       # Block diagram CRUD + generation
│   │   ├── com.py                 # COM channel analysis
│   │   ├── bom.py                 # BOM risk analysis
│   │   ├── drc.py                 # Schematic DRC
│   │   ├── sipi.py                # SI/PI design rule guide
│   │   └── stackup.py             # PCB stackup designer
│   └── services/                  # Business logic (no HTTP)
│       ├── ai_client.py           # OpenAI client factory
│       ├── ai_extractor.py        # Datasheet component extraction (chunked)
│       ├── pdf_extractor.py       # PyMuPDF wrapper
│       ├── part_library.py        # JSON library CRUD + variant consolidation
│       ├── datasheet_store.py     # PDF file storage with dedup
│       ├── text_store.py          # Extracted text storage with dedup
│       ├── xpedition_stub.py      # Xpedition COM automation stub
│       ├── csv_delta.py           # FPGA pin-swap delta engine (pandas)
│       ├── fpga_risk_assessor.py  # AI SI/PI risk classification
│       ├── xpedition_io_export.py # Xpedition I/O update script generator
│       ├── constraint_extractor.py # AI constraint extraction from datasheets
│       ├── xpedition_ces_export.py # Xpedition CES Python script generator
│       ├── block_diagram_store.py  # Block diagram JSON persistence
│       ├── block_diagram_generator.py # AI block diagram generation
│       ├── block_diagram_export.py    # Netlist CSV/script export
│       ├── com_extractor.py           # AI COM channel parameter extraction
│       ├── com_calculator.py          # Deterministic COM estimation
│       ├── com_export.py              # COM export (CES/HyperLynx/Markdown)
│       ├── bom_analyzer.py            # BOM parsing, cross-ref, risk scoring
│       ├── bom_export.py              # Annotated CSV + Markdown report
│       ├── netlist_parser.py          # Xpedition/OrCAD netlist parser
│       ├── drc_rules_engine.py        # Deterministic DRC rules (13 rules)
│       ├── drc_ai_checker.py          # AI-powered DRC violations
│       ├── sipi_knowledge_base.py     # Hardcoded SI/PI rule library
│       ├── loss_budget_calculator.py  # Analytical channel loss budgeting
│       └── stackup_engine.py          # Stackup templates + impedance formulas
├── frontend/
│   ├── index.html                 # Google Fonts, viewport, root div
│   ├── vite.config.js             # Dev server + `/api` proxy to :8000
│   ├── tailwind.config.js         # CSS custom property theme mapping
│   └── src/
│       ├── main.jsx               # React entry, renders <App>
│       ├── App.jsx                # BrowserRouter + route table
│       ├── index.css              # CSS custom properties (theme tokens)
│       ├── components/
│       │   ├── Navbar.jsx         # Sticky top navigation bar
│       │   ├── UploadZone.jsx     # Drag-and-drop / click PDF uploader
│       │   ├── DataTable.jsx      # Editable component parameter table
│       │   ├── DualCsvUpload.jsx  # Two-file CSV upload (FPGA bridge)
│       │   ├── DeltaTable.jsx     # Pin-swap results with risk badges
│       │   ├── ConstraintTable.jsx # Editable constraint rows
│       │   ├── SectionLabel.jsx   # Section header with optional badge
│       │   ├── SummaryCard.jsx    # Metric card (label + value)
│       │   ├── StackBar.jsx       # Horizontal progress/ratio bar
│       │   ├── ModuleGuide.jsx    # Usage guide overlay
│       │   └── ui/                # Primitive components
│       │       ├── card.jsx       # Card container with variants
│       │       ├── badge.jsx      # Status/type badge
│       │       └── button.jsx     # Accessible button
│       └── pages/
│           ├── Home.jsx           # Dashboard — module selection grid
│           ├── ComponentLibrarian.jsx # Datasheet upload + part library
│           ├── PartDetail.jsx     # Single-part detail view
│           ├── FpgaBridge.jsx     # FPGA pin-swap comparison tool
│           ├── SiPiGuide.jsx      # SI/PI design guide + constraint export
│           ├── BlockDiagram.jsx   # Block diagram builder + AI generation
│           ├── StackupDesigner.jsx # PCB stackup design tool
│           ├── BomAnalyzer.jsx    # BOM risk analysis tool
│           └── SchematicDrc.jsx   # Schematic DRC tool
└── docs/                          # Engineering documentation (this directory)
```

---

## Request Flow — End-to-End

### Datasheet Upload Flow (the most complex path)

```
User drops PDF → ComponentLibrarian.jsx
  ↓  POST /api/upload-datasheet (multipart)
  routers/librarian.py::upload_datasheet()
    ↓ datasheet_store.save(bytes, filename)  → writes backend/data/datasheets/<file>.pdf
    ↓ pdf_extractor.extract_text_from_pdf(bytes)  → PyMuPDF, returns {text, pages, page_count}
    ↓ text_store.save(text, stored_filename)  → writes backend/data/texts/<file>.txt
    ↓ ai_extractor.extract_components_from_text_chunked(text)
        if len(text) ≤ 6000 chars:
          → extract_components_from_text(text)   [single LLM call]
        else:
          → _chunk_text(text, 6000, 300, 5)      [overlapping windows]
          → loop: extract_components_from_text(chunk) per chunk
          → _merge_component_results(chunk_results)  [deduplicate by PN]
        Each LLM call:
          → ai_client.get_client()  → OpenAI(api_key, base_url)
          → client.chat.completions.create(model, messages, response_format=json_object)
          → parse JSON → validate Pydantic ComponentData
          → _enrich_from_text() regex fallback on each component
    ↓ part_library.consolidate_variants(rows)  → pick primary PN, store variants[]
    ↓ return {rows, consolidated, warnings, stored_filename, ...}
  ↓  Frontend shows DataTable for engineer to review
  ↓  Engineer clicks Accept → POST /api/library/accept-parts
  routers/librarian.py::accept_parts()
    ↓ part_library.upsert_parts(parts, source_file, datasheet_file)
      → threading.Lock() → load JSON → upsert → save JSON
```

### AI Client Pattern (used by every AI service)

All AI calls follow the same pattern through `services/ai_client.py`:
```
get_client() → checks INTERNAL_API_KEY (raises RuntimeError if missing)
             → returns OpenAI(api_key=..., base_url=INTERNAL_BASE_URL)
get_model()  → returns INTERNAL_MODEL_NAME (default: gpt-4o-mini)
```

The router always catches `RuntimeError` → HTTP 503, and any other exception → HTTP 502.

---

## Environment Variables

All config lives in `backend/.env` (never committed):

```
INTERNAL_API_KEY=ollama              # Required — API key or "ollama" for local
INTERNAL_BASE_URL=http://127.0.0.1:11434/v1   # Ollama or cloud gateway
INTERNAL_MODEL_NAME=llama3.1:8b      # Model to use

MAX_CHUNK_CHARS=6000                 # Max chars per AI chunk (≈1500 tokens)
CHUNK_OVERLAP_CHARS=300              # Overlap between chunks (context continuity)
MAX_CHUNKS=5                         # Hard cap on chunks per document
```

---

## AI Integration Architecture

The system uses a **single OpenAI-compatible client** pointed at whatever endpoint is configured. This means it can run:

- **Local/offline**: Ollama with `llama3.1:8b` — no internet required
- **Internal gateway**: Corporate API proxy (same code, different `base_url`)
- **Cloud**: OpenAI/Anthropic-compatible gateway

Every AI service follows this contract:
- `temperature=0.0` (deterministic output for consistency)
- `response_format={"type": "json_object"}` (forces JSON mode)
- System prompt provides exact JSON schema + field hints
- Robust salvage logic handles partial/malformed LLM responses
- HTTP 503 = API key not configured, HTTP 502 = API/network error

---

## Persistence Layer

All data is stored as JSON files — no database. This keeps the system portable and auditable.

| File | Protected by | Contents |
|------|-------------|---------|
| `data/library.json` | `threading.Lock()` | Part library array |
| `data/diagrams.json` | `threading.Lock()` | Block diagrams array |
| `data/datasheets/` | filename dedup (MD5) | Uploaded PDFs |
| `data/texts/` | filename dedup (MD5) | Extracted text files |

The deduplication pattern: if a file with the same name already exists but has different MD5 content, a `_{hash8}` suffix is appended before the extension. Same-content files return the existing name without re-writing.

---

## Frontend Architecture

The frontend is a single-page application with **URL-based routing** (React Router v6). The `Navbar` is sticky and always visible. Pages are full-width within a `max-w-7xl` centered container.

### Design System — "Tactical Aerospace"
- **Always dark** — `html` element has `class="dark"` forced in `index.html`; no light mode
- **CSS custom properties** defined in `src/index.css`, consumed by `tailwind.config.js`
- Color tokens: `--color-background`, `--color-surface`, `--color-border`, `--color-text-primary`, `--color-text-secondary`, `--color-accent`, `--color-accent-glow`
- Typography: Inter (body, `font-body`) + Space Grotesk (headings, `font-display`) — loaded via `@fontsource` npm packages (no Google Fonts network requests — air-gap safe)

### API Communication
- Vite dev server proxies all `/api/*` requests to `http://localhost:8000`
- No auth headers on frontend calls (backend is local-only)
- All uploads use `FormData` with `fetch()` POST
- JSON responses are consumed directly without a client library (no Axios/React Query)

---

## The 8 Functional Modules

| Route | Module | Backend Router | Core Purpose |
|-------|--------|---------------|-------------|
| `/librarian` | Component Librarian | `librarian.py` | Datasheet → AI extraction → Part library |
| `/fpga` | FPGA I/O Bridge | `fpga.py` | Pin-swap delta + AI risk assessment |
| `/constraints` | SI/PI Constraint Editor | `constraint.py` + `sipi.py` | Extract constraints + design rule guide |
| `/block-diagram` | Block Diagram Builder | `block_diagram.py` | AI system diagram generation + CRUD |
| `/stackup` | Stackup Designer | `stackup.py` | Layered PCB stackup + impedance calc |
| `/bom` | BOM Analyzer | `bom.py` | Lifecycle + radiation risk scoring |
| `/drc` | Schematic DRC | `drc.py` | Deterministic + AI design rule checks |
| `/` | Home | — | Dashboard with module cards |

---

## Testing Strategy

Tests live in `backend/tests/`. Each module has a dedicated test file:

```
tests/
├── test_librarian.py      # Upload flow, library CRUD, BOM import, Xpedition push
├── test_chunked_extraction.py  # _chunk_text, _merge_component_results, chunked flow
├── test_fpga.py           # Pin delta, risk assessor, export script
├── test_constraint.py     # Constraint extraction endpoint
├── test_block_diagram.py  # CRUD + generation + export
├── test_bom.py            # BOM parsing, cross-ref, risk scoring, export
├── test_com_channel.py    # Channel extraction, COM calculation, export
├── test_drc.py            # Netlist parsing, DRC rule engine, report export
└── test_constraint.py     # Constraint extraction
```

All AI calls are mocked with `unittest.mock.patch`. Router tests use `fastapi.testclient.TestClient`. No real API calls or file I/O occur in tests (datasheet_store, text_store are patched where needed).

Run all tests:
```bash
cd backend
python3 -m pytest tests/ -v
```

---

## Running the Stack

```bash
# Backend
cd backend
python3 -m uvicorn main:app --reload
# Starts on http://localhost:8000
# API docs: http://localhost:8000/docs

# Frontend
cd frontend
npm install
npm run dev
# Starts on http://localhost:5173 (or 5174 if port busy)
```

The backend loads `.env` first via `python-dotenv` before any imports, so all `os.environ.get()` calls in services see the correct values at module load time.
