# Session Handoff — GDMS Space Hardware Assistant
**Last updated: 2026-03-09**

---

## Phase 1: Component Librarian — COMPLETE (26 tests)

| Step | Description | Status |
|---|---|---|
| 1 | React UI — PDF upload zone, DataTable, GDMS branding | ✅ |
| 2 | FastAPI — `POST /api/upload-datasheet`, pdfplumber extraction | ✅ |
| 3 | OpenAI-compatible AI extraction, Pydantic `ComponentData` schema | ✅ |
| 4 | Xpedition COM stub — `POST /api/push-to-databook`, `PushResultPanel` | ✅ |
| 5 | Part Library — searchable card grid, JSON persistence, auto-save on upload | ✅ |

---

## Phase 2: FPGA I/O Bridge — Steps 1 & 2 Complete (16 tests)

| Step | Description | Status |
|---|---|---|
| 1 | `FpgaBridge.jsx`, `DualCsvUpload.jsx`, `DeltaTable.jsx` | ✅ |
| 2 | `POST /api/compare-fpga-pins`, pandas delta engine, `csv_delta.py` | ✅ |
| 3 | AI SI/PI risk assessment per pin swap | 🔲 **Next** |
| 4 | Xpedition I/O Designer `.vbs`/`.py` export + download button | 🔲 |

---

## Frontend Redesign — COMPLETE

Entire frontend redesigned to match the **"Tactical Aerospace" always-dark design system** defined in `docs/Frontend.md`.

### What changed
- **Theme** — CSS custom properties in `index.css` (`--background`, `--primary`, `--muted-foreground`, etc.); Tailwind config extended to consume them; `<html class="dark">` forced in `index.html`
- **Fonts** — Inter (body) + Space Grotesk (headings) loaded via Google Fonts; `.font-heading` / `.font-body` utility classes added
- **UI primitives** — `src/components/ui/card.jsx`, `badge.jsx`, `button.jsx` (shadcn-style wrappers over Tailwind)
- **Navbar** — new `src/components/Navbar.jsx` with sticky top bar (Satellite icon + logo + nav links); replaced old sidebar layout in `App.jsx`
- **Layout** — `max-w-7xl` centered main content with `py-10` padding; `mb-14` section rhythm
- **All pages + components** — hero sections with Badge + h1 + subtitle; all hardcoded `gray-*`/`gdms-*` colours replaced with semantic tokens; lucide-react icons throughout

### New Part Library feature (Component Librarian)
- **`ComponentData.Summary`** — optional field; AI extractor prompt asks for a one-sentence component description
- **`services/part_library.py`** — thread-safe JSON store at `backend/data/library.json`; `upsert_parts()` deduplicates by Part_Number
- **Auto-save** — `POST /api/upload-datasheet` saves parts to library on every successful extraction
- **`GET /api/library`** — returns all stored parts
- **`GET /api/library/search?q=...`** — case-insensitive substring search across all fields
- **PartLibrary UI** — search input (300ms debounce), responsive card grid (1→2→3 cols), spec chips, AI summary, source filename; auto-refreshes after each upload

---

## Current Codebase State

### Test suite
```
backend/ $ python -m pytest tests/ -q
42 passed, 40 warnings
```
- 26 tests — Phase 1 (librarian, AI extractor, PDF extractor, Xpedition stub)
- 16 tests — Phase 2 (FPGA delta engine)

### Servers
| Process | URL | Command |
|---|---|---|
| FastAPI backend | `http://localhost:8000` | `cd backend && python -m uvicorn main:app --reload` |
| Vite frontend | `http://localhost:5174` | `cd frontend && npm run dev` |

> **CORS note:** `main.py` still only allows `http://localhost:5173`. If Vite stays on 5174, add it to the `allow_origins` list in `backend/main.py`.

### File tree
```
backend/
├── .env.example                  ← copy to .env, fill INTERNAL_API_KEY / BASE_URL / MODEL_NAME
├── data/
│   └── library.json              ← auto-created; persistent part library store
├── models/
│   ├── component.py              ← ComponentData (incl. Summary field), ComponentExtractionResult
│   └── fpga.py                   ← PinSwap, PinDeltaResponse
├── routers/
│   ├── librarian.py              ← /upload-datasheet, /push-to-databook, /library, /library/search
│   └── fpga.py                   ← /compare-fpga-pins
├── services/
│   ├── pdf_extractor.py          ← pdfplumber wrapper
│   ├── ai_extractor.py           ← OpenAI-compatible extraction + Pydantic validation
│   ├── xpedition_stub.py         ← win32com COM stub (lazy import)
│   ├── csv_delta.py              ← pandas inner-join delta engine
│   └── part_library.py           ← JSON file store, upsert_parts(), search()
└── tests/
    ├── test_librarian.py         ← 26 tests (Phase 1 + Part Library)
    └── test_fpga.py              ← 16 tests (Phase 2)

frontend/src/
├── App.jsx                       ← top Navbar + max-w-7xl layout (no sidebar)
├── index.css                     ← CSS custom properties + font utilities
├── pages/
│   ├── ComponentLibrarian.jsx    ← Phase 1 UI + Part Library section
│   └── FpgaBridge.jsx            ← Phase 2 UI
└── components/
    ├── Navbar.jsx                ← sticky top nav (Satellite icon, page links)
    ├── UploadZone.jsx            ← PDF drag-and-drop (lucide icons, themed)
    ├── DataTable.jsx             ← 8-col Databook parameter table
    ├── DualCsvUpload.jsx         ← two CSV drop zones + submit button
    ├── DeltaTable.jsx            ← 6-col pin-swap table, risk badges
    └── ui/
        ├── card.jsx              ← Card, CardHeader, CardTitle, CardContent, CardFooter
        ├── badge.jsx             ← Badge (default / secondary / outline)
        └── button.jsx            ← Button (default / outline / ghost / destructive, asChild)
```

### Known gaps
- `AI_Risk_Assessment` is `null` on all delta rows — `DeltaTable` shows "Pending AI review" (Phase 2 Step 3 not started)
- No "Export Xpedition Update Script" button on FPGA page yet (Phase 2 Step 4)
- `win32com` (`pywin32`) not in `requirements.txt` — install manually on the Xpedition machine
- CORS origin list in `main.py` only includes `http://localhost:5173` — add `5174` if Vite stays there

---

## Exact Next Steps When Resuming

### 1. Phase 2 — Step 3: AI Risk Assessment  ← **START HERE**

Reference: `docs/02_Phase_2_FPGA_Bridge.md`, Step 3.

1. **Create `backend/services/fpga_risk_assessor.py`**
   - Reuse `_get_client()` from `ai_extractor.py`
   - System prompt: act as SI/PI engineer reviewing FPGA pin swaps
   - Pydantic wrapper: `RiskAssessmentResult(assessments: List[PinRisk])` where `PinRisk(Signal_Name: str, AI_Risk_Assessment: str)`
   - Use `response_format={"type": "json_object"}` with schema embedded in prompt
   - Return swaps list with `AI_Risk_Assessment` populated

2. **Wire into `backend/routers/fpga.py`**
   - After `compute_pin_delta(...)`, call `assess_pin_risks(swapped_pins)`
   - 503 for missing key, 502 for other errors

3. **Risk string convention** (matches existing `DeltaTable.jsx` badge logic):
   - `"High Risk: …"` → red badge
   - `"Medium Risk: …"` → yellow badge
   - `"Low Risk: …"` → green badge

4. Add tests in `test_fpga.py` using the `_make_openai_mock()` helper pattern already in `test_librarian.py`

### 2. Phase 2 — Step 4: Xpedition I/O Designer Export

1. `backend/services/xpedition_io_export.py` — generates `.py` script string using `win32com.client`
2. `POST /api/export-io-script` — returns script as downloadable file
3. "Export Xpedition Update Script" button in `FpgaBridge.jsx`

### 3. Fix CORS (quick)
In `backend/main.py`, update:
```python
allow_origins=["http://localhost:5173", "http://localhost:5174"],
```
