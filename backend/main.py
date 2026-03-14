import logging
import os

from dotenv import load_dotenv

# Load .env before any module that reads environment variables is imported.
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("server.log", encoding="utf-8"),
    ],
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from middleware.auth import AuthMiddleware
from middleware.request_id import RequestIDMiddleware
from middleware.upload_limit import UploadLimitMiddleware
from routers import librarian, fpga, constraint, block_diagram, com, bom, drc, sipi, stackup

app = FastAPI(
    title="GDMS Space Hardware Assistant API",
    description="Backend for the Component Librarian and future GDMS modules.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-User", "X-Request-ID"],
)

# Middleware stack is LIFO — added last = runs first on the way in.
# Execution order: UploadLimit → RequestID → Auth → handler
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(UploadLimitMiddleware)

app.include_router(librarian.router, prefix="/api", tags=["librarian"])
app.include_router(fpga.router, prefix="/api", tags=["fpga"])
app.include_router(constraint.router, prefix="/api", tags=["constraint"])
app.include_router(block_diagram.router, prefix="/api", tags=["block_diagram"])
app.include_router(com.router, prefix="/api", tags=["com"])
app.include_router(bom.router, prefix="/api", tags=["bom"])
app.include_router(drc.router, prefix="/api", tags=["drc"])
app.include_router(sipi.router, prefix="/api", tags=["sipi"])
app.include_router(stackup.router, prefix="/api", tags=["stackup"])


logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Static file serving (Docker production mode) ──────────────────────────
# When STATIC_DIR is set (e.g. in Docker), serve the React SPA.
# In dev mode (no STATIC_DIR), the Vite dev server handles frontend.
_STATIC_DIR = os.environ.get("STATIC_DIR")
if _STATIC_DIR and os.path.isdir(_STATIC_DIR):
    # Serve static assets (JS, CSS, images) at /assets/
    app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="assets")

    # SPA fallback — serve index.html for all non-API, non-file routes
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        # If the path points to an actual file, serve it
        file_path = os.path.join(_STATIC_DIR, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html (SPA client-side routing)
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
