# TODOS — GDMS Space Hardware Assistant

> Generated from CEO Plan Review (SCOPE EXPANSION mode) — 2026-03-14
> Revised by Engineering Plan Review (BIG CHANGE mode) — 2026-03-14

---

## Immediate Fixes (P0) — Day 1

### Fix 30 Broken Tests (3 root causes)
- **What:** Fix mock targets and model fixtures across 3 test files:
  1. `test_fpga.py` (18 failures): change mock path from `services.fpga_risk_assessor._get_client` to `services.fpga_risk_assessor.get_client`
  2. `test_constraint.py` (7 failures): change mock path from `services.constraint_extractor._get_client` to `services.constraint_extractor.get_client`
  3. `test_com_channel.py` (5 failures): fix `COMResult` model fixtures from `ild_db` → `total_il_db`, plus fix any `com_extractor` import issues
- **Why:** 30 broken tests erode confidence in the entire suite and mask regressions
- **Effort:** S-M (1-2 hours, needs per-file attention — not a blind find-and-replace)
- **Priority:** P0
- **Depends on:** Nothing

### Fix `_MAX_TEXT_CHARS` Silent Data Truncation Bug
- **What:** Remove the `_MAX_TEXT_CHARS` truncation in `extract_components_from_text()` (`ai_extractor.py:262`). The chunking layer already guarantees safe chunk sizes (6000 chars).
- **Why:** Each 6000-char chunk is silently re-truncated to 4000 chars, discarding 33% of data per chunk
- **Effort:** S (remove truncation logic, ~10 lines)
- **Priority:** P0 — data loss bug
- **Depends on:** Nothing

### Add AI Client Timeout
- **What:** Pass `timeout=60` to the `OpenAI()` constructor in `ai_client.py`
- **Why:** AI calls can hang indefinitely if Ollama or cloud API is slow
- **Effort:** S (1 line)
- **Priority:** P0
- **Depends on:** Nothing

### Sanitize Global Exception Handler
- **What:** Change `main.py:55` from `str(exc)` to a generic "Internal server error" message
- **Why:** `str(exc)` can leak internal paths, class names, and implementation details
- **Effort:** S (1 line)
- **Priority:** P0
- **Depends on:** Nothing

### Fix File Handle Leaks in Store Files
- **What:** Wrap `open(dest, "rb").read()` in `with` statements in `datasheet_store.py:34` and `text_store.py:38`
- **Why:** Leaked file handles accumulate under load. On Windows, leaked handles can prevent file deletion/renaming.
- **Effort:** XS (2 lines per file)
- **Priority:** P0
- **Depends on:** Nothing

### Write Unit Tests for `_enrich_from_text()` Regex Patterns
- **What:** 12-15 unit tests covering the 6 regex branches in `ai_extractor.py:_enrich_from_text()`: pin count, temp range (-55/+125 and -40/+85), TID, SEL threshold (2 patterns), voltage rating, thermal resistance
- **Why:** This function is the safety net for when the LLM misses fields. Zero branches have tests.
- **Effort:** S-M
- **Priority:** P0
- **Depends on:** Nothing

---

## Short-Term (P1) — Phase 1: Store Refactoring (Week 1) ✅ DONE

### ✅ Extract `FileStore` Base Class
- **Completed:** `backend/services/file_store.py` — MD5 dedup, sanitize, binary/text modes
- `datasheet_store.py` and `text_store.py` rewritten as thin wrappers
- 19 tests in `test_file_store.py`

### ✅ Extract `JsonStore` Base Class with Built-in Cache
- **Completed:** `backend/services/json_store.py` — thread-safe CRUD, in-memory cache, corruption handling
- `block_diagram_store.py` rewritten as thin wrapper
- `part_library.py` rewritten to use JsonStore
- 20 tests in `test_json_store.py` (incl. concurrent writes, corruption, cache invalidation)

### ✅ Pre-compute `_search_text` Field at Insert Time
- **Completed:** `_build_search_text()` in `part_library.py` — computed at upsert time, used by `search()`

### ✅ Unit Tests for Stores + Variant Consolidation
- **Completed:** 25 tests in `test_part_library_internals.py` (_base_pn, _pick_primary, _build_variant_entry, consolidate_variants, _build_search_text)
- **Total new tests:** 64 (365 total, up from 301)

---

## Short-Term (P1) — Phase 2: Auth + Docker (Week 2) ✅ DONE

### ✅ API Key + User Header Authentication
- **Completed:** `backend/middleware/auth.py` — Bearer token validation, X-User extraction, dev mode bypass
- 10 tests in `test_middleware.py`

### ✅ Single Dockerfile
- **Completed:** Multi-stage Dockerfile (Node frontend build → Python backend), SPA fallback in `main.py`, `.dockerignore`

### ✅ Upload Size Limits
- **Completed:** `backend/middleware/upload_limit.py` — 50MB default, configurable via `MAX_UPLOAD_BYTES`
- 3 tests in `test_middleware.py`

### ✅ localStorage Staging Persistence
- **Completed:** `ComponentLibrarian.jsx` — staged parts saved/restored from localStorage

### ✅ Request ID Middleware + Structured Logging
- **Completed:** `backend/middleware/request_id.py` — UUID per request, X-Request-ID header, access logging
- 3 tests in `test_middleware.py`

### ✅ Document LLM Prompt Injection Risk
- **Completed:** `docs/security_prompt_injection.md` — attack surface, defenses, limitations, recommendations

---

## Short-Term (P1) — Phase 3: SQLite Swap (Week 3+) ✅ DONE

### ✅ SQLite Migration (Phase 2 of Store Refactoring)
- **Completed:** `backend/services/sqlite_store.py` — SqliteStore drop-in replacement for JsonStore
- WAL mode, JSON blob per row, same public API + internal `_lock`/`_load`/`_save`
- Auto-migration on startup via `backend/services/migrate.py` (idempotent)
- JSON files kept as backup, `store.db` added to `.gitignore`
- 25 tests in `test_sqlite_store.py`
- Also fixed: middleware rewritten as pure ASGI (fixes BaseHTTPMiddleware deadlock), BOM test mock path fix
- **Total: 406 tests passing**

---

## Medium-Term (P2)

### Project Entity (Cross-Module Intelligence)
- **What:** Add a `Project` model that links a block diagram, stackup, library subset, BOM, and DRC results under a named project
- **Why:** Foundation for cross-module data flow, design review packages, project-scoped views
- **Pros:** Enables cross-module intelligence
- **Cons:** New abstraction layer, touches every module page, migration of existing data into default project
- **Effort:** L
- **Priority:** P2 (deferred from P1 — premature abstraction for current single-user usage)
- **Depends on:** SQLite migration

### SSO/LDAP Authentication (upgrade from API key auth)
- **What:** Upgrade from API key auth to corporate Active Directory / LDAP integration for real user authentication and RBAC
- **Why:** API key auth gets identity flowing, but a team tool ultimately needs corporate SSO for compliance and access control
- **Pros:** Real user identity, RBAC, audit trail, compliance
- **Cons:** Heavy lift, corporate IT dependency, needs LDAP/AD infrastructure
- **Effort:** XL
- **Priority:** P2
- **Depends on:** Docker deployment + API key auth (P1) already in place

### Xpedition Bridge Daemon
- **What:** Python daemon on engineer's machine receiving push requests via WebSocket, executing Xpedition COM automation in real time
- **Why:** Eliminates manual script download-and-run workflow
- **Pros:** Real-time push, zero manual steps, immediate feedback
- **Cons:** COM automation is fragile, needs real Xpedition license for testing
- **Effort:** XL
- **Priority:** P2
- **Depends on:** Docker deployment + API key auth

### OCR Support for Scanned PDFs
- **What:** Add Tesseract OCR as fallback in `pdf_extractor.py` when PyMuPDF returns empty text
- **Why:** Scanned military datasheets are common in aerospace and currently return nothing
- **Effort:** M
- **Priority:** P2
- **Depends on:** Nothing

### Cross-Module Navigation Links
- **What:** BOM line → library entry, library entry → block diagrams, DRC violation → stackup/constraint
- **Why:** Connective tissue that makes 8 tools feel like one
- **Effort:** S per link
- **Priority:** P2
- **Depends on:** Project Entity

---

## Vision (P3)

### Design Review Package Export
- **What:** One-click export that bundles library, stackup, DRC, BOM into a single PDF/HTML document
- **Why:** Engineers need this for design reviews and program milestones
- **Effort:** M
- **Priority:** P3
- **Depends on:** Project Entity

### Inline PDF Viewer with Highlight
- **What:** Split-pane view: extracted parameters on left, PDF page on right with relevant section highlighted
- **Why:** Engineers could verify AI extraction at a glance without opening a new tab
- **Effort:** L
- **Priority:** P3
- **Depends on:** Nothing

### Activity Feed / Recent Actions
- **What:** "Recent Activity" panel on Home page showing last N actions across all modules
- **Why:** Quick access to recent work, especially useful for multi-user
- **Effort:** S
- **Priority:** P3
- **Depends on:** API key + user header auth (P1) for user attribution
