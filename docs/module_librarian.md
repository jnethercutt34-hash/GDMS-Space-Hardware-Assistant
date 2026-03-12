# Module: Component Librarian

The Component Librarian is the heart of the application. It converts raw PDF datasheets into structured, searchable part records stored in a persistent library. Engineers upload datasheets, the AI extracts parameters, they review and accept, and the data lands in `library.json`.

---

## Files

| File | Role |
|------|------|
| `routers/librarian.py` | HTTP entry points |
| `services/ai_extractor.py` | LLM-based parameter extraction + chunked pipeline |
| `services/part_library.py` | Persistent JSON store with CRUD and variant logic |
| `services/pdf_extractor.py` | PyMuPDF text extraction |
| `services/datasheet_store.py` | PDF file storage |
| `services/text_store.py` | Extracted text storage |
| `services/xpedition_stub.py` | Xpedition Databook push (COM automation) |
| `services/bom_analyzer.py` | BOM CSV parsing (shared with BOM module) |
| `models/component.py` | Pydantic schemas |

---

## API Endpoints

### `POST /api/upload-datasheet`
Accepts a PDF file. Does NOT auto-save to library — returns extracted data for engineer review.

**Request:** `multipart/form-data` with `file` field (must be `application/pdf`)

**Processing pipeline:**
1. Save PDF bytes to `backend/data/datasheets/` (deduplication by MD5)
2. Extract text via PyMuPDF → `{page_count, text, pages}`
3. Save extracted text to `backend/data/texts/` (audit trail)
4. Run `extract_components_from_text_chunked(text)` → `(rows, warnings)`
5. Run `consolidate_variants(rows)` → merge variant PNs into one record
6. Return `{filename, stored_filename, page_count, extracted_text, rows, consolidated, primary_part, variant_count, warnings}`

**Error responses:**
- `400` — not a PDF
- `503` — `INTERNAL_API_KEY` not set
- `502` — AI/network error

### `POST /api/library/accept-parts`
Commits engineer-reviewed parts to the library.

**Body:** `{parts: [...], source_file: str, datasheet_file: str | null}`

**Logic:** Calls `upsert_parts()` which consolidates variants and writes under `threading.Lock()`.

### `GET /api/library`
Returns all parts as JSON array. No filtering.

### `GET /api/library/search?q=<query>`
Case-insensitive substring search across all fields of all parts and their `variants[]` sub-entries.

### `GET /api/library/{part_number}`
Exact match on `Part_Number` field.

### `PATCH /api/library/{part_number}`
Update mutable metadata fields: `Program`, `Part_Type`. Uses `patch_part()` which merges under lock.

### `POST /api/push-to-databook`
Sends component rows to Xpedition Databook via COM automation.

**Body:** `{rows: [ComponentData...]}`

**Response:** `{results: [{Part_Number, status, message}]}`

The stub returns `"simulation_only"` status unless Xpedition is installed and the COM dispatch succeeds.

### `GET /api/datasheets/{filename}`
Serves the stored PDF file back as `application/pdf` for in-browser viewing.

### `POST /api/library/import-bom`
Import ICs from an Xpedition BOM CSV as placeholder parts (no datasheet data). Skips passives using ref-des prefix heuristics (`R`, `C`, `L`, `F`, `TP`, `FID`, `MH`) and description keyword matching.

---

## `services/ai_extractor.py` — Deep Dive

### Why chunking exists

A typical datasheet is 30,000–200,000 characters. `llama3.1:8b` has an 8k token context window. At ~4 chars/token, 6,000 characters ≈ 1,500 tokens — safe alongside the system prompt and response. Previously the code hard-truncated to 4,000 chars, silently discarding 95%+ of content.

### Constants (from `.env`)

```python
_MAX_TEXT_CHARS  = int(os.environ.get("MAX_PDF_CHARS", "4000"))  # legacy, unused in main path
_MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS",     "6000"))
_CHUNK_OVERLAP   = int(os.environ.get("CHUNK_OVERLAP_CHARS", "300"))
_MAX_CHUNKS      = int(os.environ.get("MAX_CHUNKS",          "5"))
```

### `_chunk_text(text, chunk_size, overlap, max_chunks) → List[str]`

**Fast path:** If `len(text) <= chunk_size`, returns `[text]` immediately.

**Normal path:**
- `stride = chunk_size - overlap`
- Slide a window of `chunk_size` across the text, stepping `stride` chars each time
- Example: 20,000 char doc, chunk=6000, overlap=300, stride=5700 → ~4 chunks
- Overlap ensures that parameters that straddle a chunk boundary are still captured in at least one chunk

**Cap logic:** If more chunks than `max_chunks` would result:
- Keep first `max_chunks - 1` normal-sized chunks
- Append one final oversized chunk covering `text[(max_chunks-1)*stride:]`
- Log a WARNING (visible in `server.log` and stderr)
- The caller (`extract_components_from_text_chunked`) also adds a user-visible warning string

### `extract_components_from_text(text) → (List[ComponentData], List[str])`

Single-chunk AI call. This is the base extractor called by the chunked version.

**Flow:**
1. Send text + system prompt to LLM with `response_format={"type": "json_object"}`
2. Parse JSON response
3. Try `ComponentExtractionResult.model_validate(parsed)` (clean path)
4. If validation fails, run salvage strategies:
   - `_find_components_in_parsed()`: tries `{"components": [...]}`, bare list, flat dict with `Part_Number`
   - `_salvage_flat_response()`: normalizes keys and tries to recover a single component
5. For every validated component, run `_enrich_from_text()` regex fallback

**What `_enrich_from_text()` does:**
Fills in fields the LLM missed by scanning the chunk text with regex:
- `Pin_Count`: looks for `"\d+[- ]?[Pp]in"` pattern
- `Operating_Temperature_Range`: looks for `-55 to +125 C` or `-40 to +85 C` patterns
- `Radiation_TID`: looks for `"\d+ krad\(?Si\)?"` pattern
- `Radiation_SEL_Threshold`: looks for SEL immune + LET threshold patterns
- `Voltage_Rating`: looks for input voltage range patterns
- `Thermal_Resistance`: looks for `θJA ... C/W` patterns

**Key detail:** `_enrich_from_text` receives the **chunk text** (not the full document), so its regex scans are bounded to what's relevant. This is intentional — it was changed from the old truncated full-text approach when chunking was introduced.

### `_merge_component_results(chunk_results) → (List[ComponentData], List[str])`

Merges results from N chunks into a single deduplicated list.

**Deduplication key:** `Part_Number.lower()` — case-insensitive to handle `TPS7H1111` vs `tps7h1111`

**Merge policy:** First non-None value wins per field. If chunk 1 found `Voltage_Rating="3.3 V"` and chunk 2 also found it, chunk 1's value is kept. If chunk 1 has `None` and chunk 2 has `"3.3 V"`, chunk 2's value fills it in.

**Ordering:** Parts appear in the order they were first seen across chunks.

**Warnings:** Deduplicated (same string from multiple chunks counts once). Uses `dict` as an ordered set (`{warning: None}`).

### `extract_components_from_text_chunked(text) → (List[ComponentData], List[str])`

The public entry point called by the router.

**Fast path:** `len(text) <= _MAX_CHUNK_CHARS` → delegates to `extract_components_from_text(text)` directly (single call, no overhead).

**Chunked path:**
1. Call `_chunk_text(text, _MAX_CHUNK_CHARS, _CHUNK_OVERLAP, _MAX_CHUNKS)` — note constants passed explicitly so test mocking works
2. If `len(chunks) >= _MAX_CHUNKS`, prepend a cap warning to the output
3. Loop over chunks, calling `extract_components_from_text(chunk)` for each
4. `RuntimeError` (missing API key) re-raised immediately — don't attempt remaining chunks
5. Any other exception per chunk → logged as WARNING, chunk skipped, continue
6. Call `_merge_component_results(chunk_results)`
7. Return `merged_rows, all_warnings + merged_warnings`

### The System Prompt

The system prompt is static and built by `_build_system_prompt()`. It:
- Specifies the exact JSON schema the LLM must return
- Provides field extraction hints (what patterns to look for per field)
- Specifies that `Part_Number` and `Manufacturer` are required
- Instructs multi-variant handling: one entry per package/ordering variant
- Instructs primary part ordering: base/generic PN first, military/ordering PNs after
- Ends with "Return ONLY the JSON object." to prevent markdown wrapping

### Field Alias Normalization (`_FIELD_ALIASES`, `_normalize_keys`)

Small LLMs often return `"part number"` instead of `"Part_Number"`, `"voltage"` instead of `"Voltage_Rating"`, etc. The `_FIELD_ALIASES` dict maps 50+ LLM variations to canonical field names. `_normalize_keys()` applies this before Pydantic validation.

---

## `services/part_library.py` — Deep Dive

### Storage

Single JSON array at `backend/data/library.json`. Each element is a part dict (a serialized `ComponentData` plus metadata fields). The file is loaded fresh on every read — there is no in-memory cache. This is intentional: it keeps the implementation simple and ensures multiple processes (or test runs) see the same state.

Thread safety: every write is wrapped in `threading.Lock()`. Reads are not locked (JSON file reads are atomic enough at this scale).

### Variant Consolidation Logic

When a datasheet covers multiple ordering numbers (e.g. `TPS7H1111-SEP`, `TPS7H1111MPWPTSEP`, `5962R2120301VXC`), the AI returns multiple `ComponentData` rows. `consolidate_variants()` merges them into one library entry.

**`_pick_primary(parts)`** scores each part number:
- +1000 if it matches `^5962[A-Z]?\d` (military SMD ordering number)
- +500 if it contains `HFT`, `/EM`, `EVM`, `DBV`, `DBG` (eval/sample variants)
- +`len(base_pn) * 10` where `base_pn` strips known suffixes (`SEP`, `RH`, `MPWPT`, etc.)
- +`len(full_pn)` as tiebreaker

Lower score = more generic/base = chosen as primary. The rest become `variants[]`.

**`_build_variant_entry(variant, primary)`** stores only the fields that differ from the primary (Package_Type, Pin_Count, Radiation_TID, Thermal_Resistance), not the full record. This keeps `library.json` compact.

### `upsert_parts(new_parts, source_file, datasheet_file)`

The write path for accepted datasheet extractions:
1. Consolidate all rows into one entry
2. Under lock: load JSON, build `{Part_Number: index}` dict
3. Remove any old entries whose Part_Number matches a variant PN (cleanup from pre-consolidation era)
4. If primary PN already in library: overwrite (re-upload updates data)
5. If new: append
6. Save

Returns count of newly added entries (0 if it was an update).

### `upsert_placeholder_parts(parts, source_file)`

Used by BOM import. Adds skeleton entries with `needs_datasheet: True`. Existing parts are **never** overwritten — BOM data is less complete than datasheet data. Returns `{"added": N, "skipped": M}`.

---

## `services/pdf_extractor.py`

Thin wrapper around PyMuPDF (`fitz`). Opens the PDF from bytes (not a file path), extracts text from each page with `page.get_text()`, joins pages with `"\n\n"`.

**Why PyMuPDF instead of pdfplumber:** TI's TPS7H1111-SEP datasheet (and similar complex vector-graphic PDFs) caused `pdfplumber` to hang indefinitely. PyMuPDF handles these reliably and is 3-5× faster.

**Return format:**
```python
{
    "page_count": int,
    "text": str,      # full text, pages joined by "\n\n"
    "pages": [str],   # per-page text list
}
```

---

## `services/datasheet_store.py` and `services/text_store.py`

Both follow the same pattern:

1. `_sanitize(filename)` strips unsafe characters with `re.sub(r"[^\w\-. ()]+", "_", name)`, enforces `.pdf` or `.txt` extension
2. `save(content, filename)` → if name collision with different MD5 → append `_{hash8}` before extension
3. `get_path(filename)` → returns full filesystem path or `None`
4. `exists(filename)` → delegates to `get_path`

`text_store` derives the `.txt` filename from the stored PDF filename by stripping `.pdf` and appending `.txt`. Example: `TPS7H1111_ab12cd34.pdf` → `TPS7H1111_ab12cd34.txt`.

---

## `models/component.py`

```python
class ComponentData(BaseModel):
    model_config = {"extra": "ignore", "coerce_numbers_to_str": True}
    Part_Number: str
    Manufacturer: str
    Value: Optional[str]
    Tolerance: Optional[str]
    Voltage_Rating: Optional[str]
    Package_Type: Optional[str]
    Pin_Count: Optional[str]
    Operating_Temperature_Range: Optional[str]
    Thermal_Resistance: Optional[str]
    Radiation_TID: Optional[str]
    Radiation_SEL_Threshold: Optional[str]
    Radiation_SEU_Rate: Optional[str]
    Summary: Optional[str]
```

Key config:
- `extra = "ignore"` — LLM responses often have extra fields; they're silently dropped
- `coerce_numbers_to_str = True` — LLM might return `{"Pin_Count": 28}` (int); Pydantic coerces to `"28"`
- All fields except `Part_Number` and `Manufacturer` are optional (None → rendered as `—` in UI)

`ComponentExtractionResult` is just `{"components": [ComponentData, ...]}` — the wrapper the LLM is instructed to return.

---

## `services/xpedition_stub.py`

The Xpedition integration. Uses `win32com.client` to automate the Xpedition EDA tool via COM.

**Lazy import pattern:** `win32com.client` is imported inside `try/except ImportError` inside the function call, not at module level. This means the server starts fine on Linux/Mac or machines without Xpedition installed.

**`simulate_xpedition_push(json_str)`:**
1. Try to import `win32com.client` and dispatch `"Mgc.Application"`
2. If Xpedition is available: attempt real databook push
3. If import fails or COM dispatch fails: return `{"status": "simulation_only", "message": "..."}`
4. If real push succeeds: return `{"status": "success", "message": "..."}`

**How to enable real Xpedition push:** Install Xpedition on the machine, install `pywin32` (`pip install pywin32`), launch the server from that machine. No code changes needed.

---

## Frontend — `pages/ComponentLibrarian.jsx`

The page has two main sections:

**Upload Section:**
- `UploadZone` component — drag-and-drop or click to select PDFs
- Supports multi-PDF queue: PDFs are uploaded and processed in sequence
- After each upload, the AI extraction result is shown in a staging area
- Engineers can Accept (sends to `/api/library/accept-parts`) or Reject (discards)
- AI warnings (truncation notices, validation failures) shown as yellow alert banners

**Library Section:**
- Search bar → `GET /api/library/search?q=` with debounce
- Responsive card grid showing all library parts
- Each card shows primary PN, manufacturer, package, radiation data, and variant count
- Clicking a part navigates to `/part/:partNumber`

**`pages/PartDetail.jsx`:**
- Loads `GET /api/library/{part_number}`
- Shows full parameter table
- Shows variants in a collapsible section
- Shows linked datasheet PDF (link to `GET /api/datasheets/{filename}`)
