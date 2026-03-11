# Session Handoff — GDMS Space Hardware Assistant
**Last updated: 2026-03-11**

---

## Phase 1: Component Librarian — COMPLETE (23 tests)

| Step | Description | Status |
|---|---|---|
| 1 | React UI — PDF upload zone, DataTable, GDMS branding | ✅ |
| 2 | FastAPI — `POST /api/upload-datasheet`, pdfplumber extraction | ✅ |
| 3 | OpenAI-compatible AI extraction, Pydantic `ComponentData` schema | ✅ |
| 4 | Xpedition COM stub — `POST /api/push-to-databook`, `PushResultPanel` | ✅ |
| 5 | Part Library — searchable card grid, JSON persistence, auto-save on upload | ✅ |

---

## Phase 2: FPGA I/O Bridge — COMPLETE (37 tests)

| Step | Description | Status |
|---|---|---|
| 1 | `FpgaBridge.jsx`, `DualCsvUpload.jsx`, `DeltaTable.jsx` | ✅ |
| 2 | `POST /api/compare-fpga-pins`, pandas delta engine, `csv_delta.py` | ✅ |
| 3 | AI SI/PI risk assessment per pin swap — `fpga_risk_assessor.py` | ✅ |
| 4 | Xpedition I/O Designer `.py` export + download button — `xpedition_io_export.py`, `POST /api/export-io-script` | ✅ |

---

## Frontend Redesign — COMPLETE

Entire frontend redesigned to match the **"Tactical Aerospace" always-dark design system** defined in `docs/Frontend.md`.

### What changed
- **Theme** — CSS custom properties in `index.css`; Tailwind config extended; `<html class="dark">` forced
- **Fonts** — Inter (body) + Space Grotesk (headings) self-hosted via `@fontsource` npm packages (air-gap compliant — no external CDN). Google Fonts CDN links removed from `index.html`
- **Font imports** — `frontend/src/main.jsx` imports `@fontsource/inter` and `@fontsource/space-grotesk` at weights 400/500/600/700
- **UI primitives** — `src/components/ui/card.jsx`, `badge.jsx`, `button.jsx` (shadcn-style wrappers)
- **Navbar** — `src/components/Navbar.jsx` with `NavLink` (React Router v6), sticky top bar, responsive hamburger at xl breakpoint (1280px), 2-column grid mobile dropdown
- **React Router** — `App.jsx` uses `BrowserRouter` + `Routes` + `Route`; URL-based navigation for all 7 modules
- **Layout** — `max-w-7xl` centered main content, `py-10` padding, `mb-14` section rhythm
- **Shared components** — `SectionLabel.jsx`, `SummaryCard.jsx`, `StackBar.jsx` extracted and used across all module pages
- **Shared utility** — `src/lib/downloadBlob.js` — single `downloadBlob(blob, filename)` used by all export buttons

---

## Phase 3: SI/PI Constraint Editor — COMPLETE (26 tests)

| Step | Description | Status |
|---|---|---|
| 1 | Pydantic models — `ConstraintRule`, `ConstraintExtractionResult` in `models/constraint.py` | ✅ |
| 2 | AI constraint extractor — `services/constraint_extractor.py` | ✅ |
| 3 | Xpedition CES export — `services/xpedition_ces_export.py` | ✅ |
| 4 | FastAPI router — `routers/constraint.py` | ✅ |
| 5 | React page — `pages/ConstraintEditor.jsx` + `ConstraintTable.jsx` | ✅ |
| 6 | Tests — `tests/test_constraint.py` — 26 tests | ✅ |

---

## Phase 4: Block Diagram Builder — COMPLETE (33 tests)

| Step | Description | Status |
|---|---|---|
| 1 | Pydantic models — `BlockDiagram`, `Block` (x/y coords, ports), `Connection` in `models/block_diagram.py` | ✅ |
| 2 | AI block diagram generator — `services/block_diagram_generator.py` | ✅ |
| 3 | Diagram store — `services/block_diagram_store.py` — CRUD operations | ✅ |
| 4 | Export — `services/block_diagram_export.py` — netlist CSV + Xpedition script | ✅ |
| 5 | FastAPI router — `routers/block_diagram.py` — CRUD + generate + export | ✅ |
| 6 | React page — `pages/BlockDiagram.jsx` — drag-and-drop canvas, SVG connection lines, manual add-block form | ✅ |
| 7 | Tests — `tests/test_block_diagram.py` — 33 tests | ✅ |

### Canvas features (P3 implementation)
- **Mouse drag**: `onMouseDown` on each block tile + `onMouseMove`/`onMouseUp` on canvas container. Drag state held in `useRef` (no re-render lag during move). Block x/y updated live in `current` state.
- **SVG connection overlay**: `ConnectionLines` component renders cubic bezier arcs between block right-edge → left-edge with arrowhead markers and signal name labels at midpoint. Drawn inside an absolutely-positioned SVG over the canvas.
- **Dot-grid background** via SVG `<pattern>` for spatial reference.
- **Add Block form** inline below canvas — label, category dropdown (FPGA/Memory/Power/Connector/Processor/Optics/Custom), optional part number. Auto-places blocks in a grid layout.
- **Selected block panel** in sidebar showing position, port count, and delete button.

---

## Phase 5: COM Channel Analysis — COMPLETE (33 tests)

| Step | Description | Status |
|---|---|---|
| 1 | Pydantic models — `ChannelSegment`, `ChannelModel`, `COMResult` in `models/com_channel.py` | ✅ |
| 2 | AI channel extractor — `services/com_extractor.py` | ✅ |
| 3 | COM calculator — `services/com_calculator.py` — simplified IEEE 802.3 Annex 93A estimation | ✅ |
| 4 | Export — `services/com_export.py` — CES script, HyperLynx CSV, summary report | ✅ |
| 5 | FastAPI router — `routers/com.py` | ✅ |
| 6 | React page — `pages/ComAnalysis.jsx` — channel builder UI, COM result display, export buttons | ✅ |
| 7 | Tests — `tests/test_com_channel.py` — 33 tests | ✅ |

**Note:** `COMResult.total_il_db` — field was renamed from `ild_db` (audit P1 fix). Frontend and calculator both use `total_il_db`.

---

## Phase 6: BOM Analyzer — COMPLETE (43 tests)

| Step | Description | Status |
|---|---|---|
| 1 | Pydantic models — `BOMLineItem`, `BOMAnalysisResult`, `BOMReport`, `BOMSummary` in `models/bom.py` | ✅ |
| 2 | BOM parser & library cross-reference — `services/bom_analyzer.py` — auto-detects column mapping, exact + fuzzy library matching | ✅ |
| 3 | AI risk assessor — `services/bom_risk_assessor.py` — batch lifecycle/radiation/alternate assessment | ✅ |
| 4 | Risk level assignment — Critical/High/Medium/Low scoring | ✅ |
| 5 | Export generators — `services/bom_export.py` — annotated BOM CSV + Markdown risk summary | ✅ |
| 6 | FastAPI router — `routers/bom.py` — `POST /api/bom/analyze`, `POST /api/bom/export` | ✅ |
| 7 | React page — `pages/BomAnalyzer.jsx` — drag-drop upload, summary cards, stacked bars, sortable/filterable table, export | ✅ |
| 8 | Tests — `tests/test_bom.py` — 43 tests | ✅ |

### Fuzzy match optimization (P3)
Replaced the O(n×m) `SequenceMatcher` loop with a `_TrigramIndex` class:
- Index built once in O(m) at the start of `cross_reference_library()`
- Each BOM item queries only trigram-matched candidates before running `SequenceMatcher`
- Falls back to full key list only for part numbers shorter than 3 characters
- Validated: `TPS62140` query returns `['TPS62140', 'TPS62141']` — correct, not `LM317`

---

## Phase 7: Schematic DRC — COMPLETE

| Step | Description | Status |
|---|---|---|
| 1 | Pydantic models — `Netlist`, `DRCViolation`, `DRCReport`, `AIViolationBatch` in `models/schematic_drc.py` | ✅ |
| 2 | Netlist parser — `services/netlist_parser.py` — parses Xpedition ASC, OrCAD, CSV netlists | ✅ |
| 3 | Deterministic rule engine — `services/drc_rules_engine.py` — 13 rules (see below) | ✅ |
| 4 | AI heuristic checker — `services/drc_ai_checker.py` — LLM-based heuristic checks | ✅ |
| 5 | FastAPI router — `routers/drc.py` — `POST /api/drc/analyze`, `POST /api/drc/upload-netlist`, `POST /api/drc/export` | ✅ |
| 6 | React page — `pages/SchematicDrc.jsx` — netlist upload, PASS/WARNING/FAIL banner, summary cards, violations table | ✅ |

### DRC Rules (13 deterministic)

| Rule | Description | Severity |
|---|---|---|
| PWR-001 | Unconnected power pins on ICs | Error |
| PWR-002 | Missing decoupling capacitors on power nets | Warning |
| PWR-003 | Power net high fan-out (>20) without ferrite/filter | Warning |
| GND-001 | Multiple ground net names (possible unintentional split) | Info |
| TERM-001 | High-speed net (CLK, LVDS, PCIe, etc.) without termination resistor | Warning |
| CONN-001 | Single-pin nets (floating signals) | Warning |
| CONN-002 | Unconnected IC pins not marked NC | Warning |
| NAME-001 | Auto-generated net names (N$*, NET*, unnamed) | Info |
| SPC-001 | No SEL current-limiter/eFuse on CMOS power paths | Warning |
| SPC-002 | No hardware watchdog timer IC | Warning |
| SPC-003 | No reset supervisor / voltage monitor IC | Info |
| SPC-004 | Single voltage regulator (single-point power failure) | Info |
| SPC-005 | Memory ICs (SRAM/FLASH/DDR) without EDAC/ECC mitigation | Warning |

`ViolationCategory.SpaceCompliance` enum value added to `schematic_drc.py` for SPC-001 through SPC-005.

---

## Code Audit Fixes Applied (2026-03-10)

### P0 — Env var / config bugs
- `drc_ai_checker.py` — fixed hardcoded `"gpt-4o"` model, now uses `get_model()`
- `bom_risk_assessor.py` — removed local `_get_client()`, uses shared `ai_client.py`
- `com_extractor.py` — removed local `_get_client()`, uses shared `ai_client.py`

### P1 — Data model correctness
- `models/component.py` — added `Operating_Temperature_Range: Optional[str]` field
- `models/com_channel.py` — renamed `ild_db` → `total_il_db` (was misleadingly named)
- `services/bom_analyzer.py` — fixed reference from `Operating_Temperature` → `Operating_Temperature_Range`
- `services/com_calculator.py` — fixed field name `total_il_db=` in `COMResult` construction

### P2 — Shared AI client, CORS, logging, fonts
- `backend/services/ai_client.py` — created shared `get_client()` / `get_model()` factory
- All AI services now import from `services.ai_client` (no more per-file `_get_client()` copies)
- `backend/main.py` — added `logging.basicConfig()` with ISO timestamp format; tightened CORS `allow_methods` and `allow_headers`
- `frontend/src/main.jsx` — replaced Google Fonts CDN with `@fontsource/inter` and `@fontsource/space-grotesk` self-hosted imports
- `frontend/index.html` — removed Google Fonts `<link>` tags

### P3 — Radiation fields, space DRC rules, performance, drag canvas
- `models/component.py` — added `Radiation_TID`, `Radiation_SEL_Threshold`, `Radiation_SEU_Rate` fields
- `services/ai_extractor.py` — updated extraction prompt with explicit radiation field guidance
- `services/drc_rules_engine.py` — added 5 space-compliance rules (SPC-001 to SPC-005) and pattern libraries
- `models/schematic_drc.py` — added `ViolationCategory.SpaceCompliance`
- `routers/drc.py` — updated `total_rules_checked` from 8 → 13
- `services/bom_analyzer.py` — added `_TrigramIndex` class; `cross_reference_library()` now uses trigram candidate filtering before `SequenceMatcher`
- `pages/BlockDiagram.jsx` — full rewrite with mouse drag-and-drop, SVG bezier connection lines, add-block form, selected-block sidebar panel

### Infrastructure
- `.gitignore` — created (Python, Node, secrets, data, logs)
- 24 orphaned root scripts/data files moved to `done/`
- `frontend/src/lib/downloadBlob.js` — shared download utility
- `frontend/src/components/SectionLabel.jsx`, `SummaryCard.jsx`, `StackBar.jsx` — shared UI components

---

## Current Codebase State

### Build status
```
frontend/ $ npm run build
✓ 1796 modules transformed   ← clean, no warnings
```

### Test suite
```
backend/ $ python -m pytest tests/ -q
265 passed (all 7 phases covered)
```
- 23 tests — Phase 1 (librarian, AI extractor, PDF extractor, Xpedition stub)
- 37 tests — Phase 2 (FPGA delta engine, AI risk assessor, I/O export)
- 26 tests — Phase 3 (constraint models, AI extraction, CES export, router)
- 33 tests — Phase 4 (block diagram models, generator, store, export, router)
- 33 tests — Phase 5 (COM models, calculator, export, router)
- 43 tests — Phase 6 (BOM models, parsing, cross-ref, risk, export, router)
- 70 tests — Phase 7 (DRC models, netlist parser, 13 rules, AI checker, router, export)

### Servers
| Process | URL | Command |
|---|---|---|
| FastAPI backend | `http://localhost:8000` | `cd backend && python -m uvicorn main:app --reload` |
| Vite frontend | `http://localhost:5174` | `cd frontend && npm run dev` |

### Environment variables (`.env` / system)
| Variable | Purpose |
|---|---|
| `INTERNAL_API_KEY` | API key for OpenAI-compatible gateway (required) |
| `INTERNAL_BASE_URL` | Gateway base URL (default: `https://api.openai.com/v1`) |
| `INTERNAL_MODEL_NAME` | Model name (default: `gpt-4o-mini`) |

---

## File Tree

```
backend/
├── .env.example                  ← copy to .env, fill INTERNAL_API_KEY / BASE_URL / MODEL_NAME
├── main.py                       ← FastAPI app, CORS, logging, all 7 phase routers
├── data/
│   └── library.json              ← auto-created; persistent part library store
├── models/
│   ├── component.py              ← ComponentData (incl. Operating_Temperature_Range,
│   │                                Radiation_TID, Radiation_SEL_Threshold, Radiation_SEU_Rate)
│   ├── fpga.py                   ← PinSwap, PinDeltaResponse
│   ├── constraint.py             ← ConstraintRule, ConstraintExtractionResult
│   ├── block_diagram.py          ← BlockDiagram, Block (x/y/ports), Connection
│   ├── com_channel.py            ← ChannelSegment, ChannelModel, COMResult (total_il_db)
│   ├── bom.py                    ← BOMLineItem, BOMAnalysisResult, BOMReport, BOMSummary
│   └── schematic_drc.py          ← Netlist, DRCViolation, DRCReport, ViolationCategory
│                                    (incl. SpaceCompliance), AIViolationBatch
├── routers/
│   ├── librarian.py              ← /upload-datasheet, /push-to-databook, /library, /library/search
│   ├── fpga.py                   ← /compare-fpga-pins, /export-io-script
│   ├── constraint.py             ← /extract-constraints, /export-ces-script
│   ├── block_diagram.py          ← CRUD + /generate, /export-netlist
│   ├── com.py                    ← /com/extract-channel, /com/calculate, /com/export
│   ├── bom.py                    ← /bom/analyze, /bom/export
│   └── drc.py                    ← /drc/analyze, /drc/upload-netlist, /drc/export
├── services/
│   ├── ai_client.py              ← shared get_client() / get_model() factory
│   ├── pdf_extractor.py          ← pdfplumber wrapper
│   ├── ai_extractor.py           ← extraction prompt (incl. radiation field guidance)
│   ├── xpedition_stub.py         ← win32com COM stub (lazy import)
│   ├── csv_delta.py              ← pandas inner-join delta engine
│   ├── fpga_risk_assessor.py     ← AI SI/PI risk assessment for pin swaps
│   ├── xpedition_io_export.py    ← generates .py script for Xpedition I/O Designer
│   ├── part_library.py           ← JSON file store, upsert_parts(), search()
│   ├── constraint_extractor.py   ← AI SI/PI constraint extraction
│   ├── xpedition_ces_export.py   ← generates .py script for CES
│   ├── block_diagram_generator.py← AI diagram generation from parts or text
│   ├── block_diagram_store.py    ← in-memory CRUD for block diagrams
│   ├── block_diagram_export.py   ← netlist CSV + Xpedition script generators
│   ├── com_extractor.py          ← AI channel parameter extraction (shared ai_client)
│   ├── com_calculator.py         ← COM estimation (IEEE 802.3 Annex 93A)
│   ├── com_export.py             ← CES script, HyperLynx CSV, summary report
│   ├── bom_analyzer.py           ← BOM parsing, trigram-indexed fuzzy match, risk assignment
│   ├── bom_risk_assessor.py      ← AI batch lifecycle/radiation risk (shared ai_client)
│   ├── bom_export.py             ← annotated BOM CSV + Markdown risk report
│   ├── netlist_parser.py         ← parses Xpedition ASC / OrCAD / CSV netlists
│   ├── drc_rules_engine.py       ← 13 deterministic DRC rules (PWR/GND/TERM/CONN/NAME/SPC)
│   └── drc_ai_checker.py         ← LLM heuristic DRC checks (shared ai_client)
└── tests/
    ├── test_librarian.py         ← 23 tests
    ├── test_fpga.py              ← 37 tests
    ├── test_constraint.py        ← 26 tests
    ├── test_block_diagram.py     ← 33 tests
    ├── test_com_channel.py       ← 33 tests
    ├── test_bom.py               ← 43 tests
    └── test_drc.py               ← 70 tests

frontend/src/
├── main.jsx                      ← @fontsource/inter + @fontsource/space-grotesk imports
├── App.jsx                       ← BrowserRouter + Routes (7 modules, / → Librarian)
├── index.css                     ← CSS custom properties + font utilities
├── lib/
│   └── downloadBlob.js           ← shared export download utility
├── pages/
│   ├── ComponentLibrarian.jsx    ← Phase 1 UI + Part Library
│   ├── FpgaBridge.jsx            ← Phase 2 UI + Export
│   ├── ConstraintEditor.jsx      ← Phase 3 UI + CES export
│   ├── BlockDiagram.jsx          ← Phase 4 UI — drag canvas, SVG lines, add-block form
│   ├── ComAnalysis.jsx           ← Phase 5 UI — channel builder, COM result, exports
│   ├── BomAnalyzer.jsx           ← Phase 6 UI — BOM upload, summary, risk table, exports
│   └── SchematicDrc.jsx          ← Phase 7 UI — netlist upload, violation table, exports
└── components/
    ├── Navbar.jsx                ← NavLink, responsive hamburger (xl breakpoint)
    ├── SectionLabel.jsx          ← shared step-heading component
    ├── SummaryCard.jsx           ← shared metric card (title/value/sub/warn)
    ├── StackBar.jsx              ← shared proportional horizontal bar with legend
    ├── UploadZone.jsx            ← PDF drag-and-drop
    ├── DataTable.jsx             ← Databook parameter table
    ├── DualCsvUpload.jsx         ← two CSV drop zones
    ├── DeltaTable.jsx            ← pin-swap table, risk badges
    ├── ConstraintTable.jsx       ← SI/PI constraint table
    └── ui/
        ├── card.jsx
        ├── badge.jsx
        └── button.jsx
```

---

## Known Issues / TODO

1. **Python 3.14 deprecation warnings** — `asyncio.iscoroutinefunction` deprecation from FastAPI/Starlette (~150 warnings during test runs). Will resolve when FastAPI updates for Python 3.16.

2. **Xpedition integration testing** — Generated `.py` scripts (CES, I/O Designer, netlist seed) have not been tested against a live Xpedition instance.

---

## Session 2026-03-11 Changes

### Phase 7 DRC Tests — COMPLETE (70 tests)
- Created `tests/test_drc.py` — 70 tests, all passing
- Removed broken `tests/test_schematic_drc.py` (old incomplete file with failing tests)
- Coverage: Pydantic models (7), netlist parser CSV/ASC/OrCAD (18), all 13 deterministic rules (26), AI checker mocked (4), router endpoints (5), export formats (5), integration helpers (5)

### Block Diagram Persistent Store — Already Done
- `block_diagram_store.py` was already JSON-file backed (`data/diagrams.json`). Handoff doc was outdated — no code change needed.

### Block Diagram Port-to-Port Wiring UI — COMPLETE
Full rewrite of `pages/BlockDiagram.jsx` adding interactive port wiring:
- **Port dots**: Clickable colored dots on block edges (green=IN on left, red=OUT on right, blue=BIDIR)
- **Wiring mode**: Click a port to start wiring → amber dashed bezier follows cursor → click a port on another block to complete
- **Signal name modal**: After connecting, a modal prompts for optional signal name
- **Wiring mode indicator**: Amber banner at top shows wiring state with ESC-to-cancel hint
- **Connection deletion**: Delete button in connections table + click on connection line SVG hit area
- **Port management**: "Add Port" form in selected-block sidebar (name + direction dropdown); delete port via ✕ button
- **Dynamic block height**: Blocks grow vertically based on port count
- **Port-aware connection lines**: SVG bezier curves now route from exact port positions, not just block center-edge
- **Backward compatible**: AI-generated diagrams and API connections still work; existing connections without port IDs fall back to center-edge routing

---

## Future Work

- **Production deployment** — Docker containerization, authentication, production CORS
- **pywin32 local listener** — daemon that watches for generated scripts and auto-executes them in Xpedition
