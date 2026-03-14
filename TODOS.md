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

## Short-Term (P1) — Phase 1: Store Refactoring (Week 1)

### Extract `FileStore` Base Class
- **What:** Consolidate `datasheet_store.py` and `text_store.py` into a shared `FileStore` base class parameterized by store directory, file extension, and write mode (binary/text). Both stores become thin subclasses.
- **Why:** The two files are 90% identical — same `_sanitize`, `save` with MD5 dedup, `get_path`, `exists`. DRY violation.
- **Pros:** Single place to fix bugs, DRY, foundation for potential SQLite file references
- **Cons:** Adds a new abstraction layer. Existing imports change.
- **Effort:** S
- **Priority:** P1
- **Depends on:** File handle leak fix (P0)
- **Tests:** `_sanitize()` (path traversal, special chars, empty), `save()` (new file, dedup same content, collision different content), `get_path()` (hit, miss), `exists()`

### Extract `JsonStore` Base Class with Built-in Cache
- **What:** Consolidate `part_library._load/_save` and `block_diagram_store._load/_save` into a shared `JsonStore` base with thread-safe CRUD and in-memory caching. Domain-specific methods (consolidate_variants, search) stay in subclasses.
- **Why:** Two identical JSON store patterns. Cache eliminates redundant disk I/O.
- **Pros:** DRY, built-in cache (invalidate on write), single place for corruption handling
- **Cons:** New abstraction. Subclasses must call `super()._save()` to invalidate cache.
- **Effort:** M
- **Priority:** P1
- **Depends on:** Nothing
- **Tests:** load empty, load valid, load corrupted JSON (graceful), save + reload roundtrip, concurrent writes, cache invalidation after write

### Pre-compute `_search_text` Field at Insert Time
- **What:** In `upsert_parts()` and `upsert_placeholder_parts()`, compute a lowercase concatenation of all searchable fields and store as `_search_text`. `search()` becomes `if q in part["_search_text"]`.
- **Why:** Current search re-computes the haystack for every part on every call via string concatenation.
- **Effort:** S
- **Priority:** P1
- **Depends on:** JsonStore extraction

### Unit Tests for Stores + Variant Consolidation
- **What:** Write dedicated unit tests for `part_library.consolidate_variants()`, `_pick_primary()`, `_build_variant_entry()`, and the `FileStore`/`JsonStore` base classes
- **Why:** These are critical paths with zero dedicated tests. A bug in `_sanitize()` is a security issue.
- **Effort:** M (30-40 tests)
- **Priority:** P1
- **Depends on:** FileStore + JsonStore extraction

---

## Short-Term (P1) — Phase 2: Auth + Docker (Week 2)

### API Key + User Header Authentication
- **What:** Add FastAPI middleware: validates `Authorization: Bearer <key>` against keys stored in `.env`, extracts `X-User` header (trusted, unvalidated), injects user into `request.state`. `/health` endpoint bypasses auth.
- **Why:** Gets user identity flowing through the system for audit trail.
- **Pros:** Simple, no external dependencies, enables activity tracking
- **Cons:** `X-User` is honesty-based (documented trust model). API keys distributed manually.
- **Effort:** S
- **Priority:** P1
- **Depends on:** Nothing
- **Tests:** valid key → pass, invalid key → 403, missing key → 401, `/health` bypass, `X-User` extraction into `request.state`

### Single Dockerfile
- **What:** Single Dockerfile: build frontend → copy `dist/` into backend container → FastAPI serves static files via `StaticFiles` mount + API endpoints. One container, one health check, one log stream.
- **Why:** Internal engineering tool doesn't need nginx or multi-container orchestration.
- **Effort:** S-M
- **Priority:** P1
- **Depends on:** Nothing

### Upload Size Limits
- **What:** Reject uploads > 50MB. Stream large uploads to disk first, then process.
- **Why:** No file size limit means a 500MB PDF consumes all memory and fills disk
- **Effort:** S-M
- **Priority:** P1
- **Depends on:** Nothing

### localStorage Staging Persistence
- **What:** Save pending extraction results to `localStorage` in `ComponentLibrarian.jsx` so they survive browser refresh. Rehydrate on mount.
- **Why:** Staging state is in React component state — refresh loses everything. The PDF is already saved to disk; only the extraction result is lost.
- **Effort:** S (10 lines of frontend code)
- **Priority:** P1
- **Depends on:** Nothing

### Request ID Middleware + Structured Logging
- **What:** Add middleware that generates a UUID per request, inject into all log messages, switch to JSON log format
- **Why:** No way to trace a user action through the system. Essential for debugging.
- **Effort:** M
- **Priority:** P1
- **Depends on:** Nothing

### Document LLM Prompt Injection Risk
- **What:** Add a security note to `docs/architecture.md` about the risk of prompt injection via PDF content. Note that Pydantic output validation is the primary defense.
- **Why:** User PDF text is injected directly into AI prompts
- **Effort:** S
- **Priority:** P1
- **Depends on:** Nothing

---

## Short-Term (P1) — Phase 3: SQLite Swap (Week 3+)

### SQLite Migration (Phase 2 of Store Refactoring)
- **What:** Replace `JsonStore` backend from JSON files to SQLite (same public API). Write a one-time migration script that reads existing JSON files and populates SQLite tables. Keep JSON files as backup.
- **Why:** JSON files have no transactions, no concurrent access, no querying, and corrupt on crash.
- **Pros:** Transactions, concurrent reads, proper indexing, migration path to PostgreSQL
- **Cons:** Data migration effort, new dependency (sqlite3 is stdlib, so minimal)
- **Effort:** M (smaller than originally estimated because JsonStore API is already extracted)
- **Priority:** P1
- **Depends on:** JsonStore base class extraction (Phase 1)

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
