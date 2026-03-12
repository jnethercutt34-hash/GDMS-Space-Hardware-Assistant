# Module: Backend Core

This document covers the foundational backend infrastructure: the FastAPI application entry point, shared AI client, and PDF extraction service.

---

## `backend/main.py` — Application Entry Point

### Startup Sequence

The startup order matters because `load_dotenv()` must run before any module-level code reads `os.environ`:

```python
from dotenv import load_dotenv
load_dotenv()          # 1. Parse backend/.env into os.environ

logging.basicConfig(   # 2. Configure logging (before any service imports)
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),              # stderr
        logging.FileHandler("server.log"),    # backend/server.log
    ]
)

from fastapi import FastAPI  # 3. Now import FastAPI (and transitively all services)
# ...
from routers import librarian, fpga, constraint, block_diagram, com, bom, drc, sipi, stackup
```

**Why the order matters:** Services like `ai_extractor.py` read `_MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS", "6000"))` at module import time. If `load_dotenv()` runs after these imports, the env vars aren't set yet and defaults are used regardless of `.env` content.

### CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)
```

Both Vite ports (5173 and 5174) are whitelisted because Vite falls back to 5174 if 5173 is in use. If a different port is needed, add it here and restart the server.

### Router Registration

All 9 routers are mounted under `/api`:
```python
app.include_router(librarian.router,     prefix="/api", tags=["librarian"])
app.include_router(fpga.router,          prefix="/api", tags=["fpga"])
app.include_router(constraint.router,    prefix="/api", tags=["constraint"])
app.include_router(block_diagram.router, prefix="/api", tags=["block_diagram"])
app.include_router(com.router,           prefix="/api", tags=["com"])
app.include_router(bom.router,           prefix="/api", tags=["bom"])
app.include_router(drc.router,           prefix="/api", tags=["drc"])
app.include_router(sipi.router,          prefix="/api", tags=["sipi"])
app.include_router(stackup.router,       prefix="/api", tags=["stackup"])
```

**Auto-generated API docs:** FastAPI generates interactive Swagger UI at `http://localhost:8000/docs` and OpenAPI JSON at `http://localhost:8000/openapi.json`. Use these to test endpoints without a frontend.

### Global Exception Handler

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": str(exc)})
```

Catches any exception not already handled by a router's `try/except`. Logs the full traceback to `server.log` and returns a clean JSON 500 to the client. Without this, unhandled exceptions return FastAPI's default HTML error page, which the frontend can't parse as JSON.

### Health Check

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

Used by process monitors or load balancers to confirm the server is up. No auth, no logic.

---

## `services/ai_client.py` — Shared AI Client Factory

### Purpose

Every AI-using service (`ai_extractor.py`, `fpga_risk_assessor.py`, `constraint_extractor.py`, etc.) calls `get_client()` and `get_model()` from this module. This centralizes all AI configuration. A bug fix here (e.g. a new retry policy, a timeout setting) applies to every AI service automatically.

### `get_client() → OpenAI`

```python
def get_client() -> OpenAI:
    api_key = os.environ.get("INTERNAL_API_KEY")
    base_url = os.environ.get("INTERNAL_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise RuntimeError(
            "INTERNAL_API_KEY is not set. Add it to your .env file and restart the server."
        )

    return OpenAI(api_key=api_key, base_url=base_url)
```

**Why `RuntimeError` instead of returning None:** The callers (`extract_components_from_text`, `assess_pin_risks`, etc.) all have `try/except RuntimeError → HTTP 503`. Raising makes the error propagation path explicit and testable.

**Why a new client per call:** The `OpenAI` client is stateless and lightweight to construct. Creating it fresh each call avoids any connection lifecycle issues with long-running servers.

### `get_model() → str`

```python
def get_model() -> str:
    return os.environ.get("INTERNAL_MODEL_NAME", "gpt-4o-mini")
```

The default `gpt-4o-mini` is used when running against OpenAI's public API. For local Ollama: set `INTERNAL_MODEL_NAME=llama3.1:8b` in `.env`.

### Pointing at Different Backends

| Backend | INTERNAL_BASE_URL | INTERNAL_API_KEY | INTERNAL_MODEL_NAME |
|---------|-------------------|-----------------|-------------------|
| Local Ollama | `http://127.0.0.1:11434/v1` | `ollama` (any string) | `llama3.1:8b` |
| OpenAI | (omit, defaults to `https://api.openai.com/v1`) | real OpenAI key | `gpt-4o-mini` or `gpt-4o` |
| Internal gateway | internal URL | internal key | gateway-specific model name |

The `openai` Python package's `base_url` parameter overrides the endpoint, making it fully OpenAI-API-compatible. Any service that speaks the OpenAI Chat Completions API (`/v1/chat/completions`) works here.

---

## `services/pdf_extractor.py` — PDF Text Extraction

### Why PyMuPDF (fitz)

The original implementation used `pdfplumber`. It was replaced because:
- TI's `TPS7H1111-SEP` datasheet caused `pdfplumber` to hang indefinitely (no timeout mechanism)
- `pdfplumber` is 3-5× slower on large datasheets
- `fitz` (PyMuPDF) handles complex vector graphics and embedded objects without hanging

### `extract_text_from_pdf(pdf_bytes: bytes) → dict`

```python
doc = fitz.open(stream=pdf_bytes, filetype="pdf")   # open from bytes, not file path
for i in range(doc.page_count):
    text = doc[i].get_text() or ""    # empty string if page has only images
    text_pages.append(text)
doc.close()

return {
    "page_count": doc.page_count,
    "text": "\n\n".join(text_pages),  # pages joined with double newline
    "pages": text_pages,              # per-page list preserved for potential page-aware processing
}
```

**Text quality notes:**
- `get_text()` returns the text layer of the PDF, not OCR. Image-only PDFs (scanned datasheets) return empty strings per page.
- Tables in PDFs often extract as unstructured text with inconsistent spacing. The AI is tolerant of this because the system prompt focuses on pattern recognition (e.g. "100 krad" appears near "TID" regardless of table formatting).
- Multi-column layouts may interleave column text. This affects extraction quality but is unavoidable without layout-aware parsing.

### Memory and Performance

A typical 50-page datasheet is 2-5 MB as bytes. PyMuPDF processes this in ~200-500ms. The full extracted text is typically 50,000-200,000 characters. This fits comfortably in server memory for a single-user local deployment.

---

## `conftest.py` — pytest Fixtures

The `conftest.py` in the `backend/` directory provides shared test fixtures:
- `client` — `TestClient(app)` pre-configured FastAPI test client
- `tmp_library` — fixture that patches `_LIBRARY_PATH` to a temp file for isolation
- `tmp_datasheets` — fixture that patches the datasheet store directory to a temp dir

These ensure tests don't touch production data files and can run in parallel without conflicts.

---

## Logging

The application logs to two sinks simultaneously:
1. **stderr** (console) — visible when running `uvicorn` in a terminal
2. **`backend/server.log`** — persistent log file, UTF-8 encoded

Log format: `2026-03-11 14:23:01 [INFO] services.ai_extractor: Processing chunk 2/3 (5987 chars)`

Key things logged:
- Every AI call: raw LLM response (first 2000 chars), parsed JSON keys
- Truncation warnings: chunk count, cap warnings
- Per-request: unhandled exceptions (full traceback)
- Xpedition COM: dispatch success/failure

For debugging AI issues: `tail -f backend/server.log | grep ai_extractor`
