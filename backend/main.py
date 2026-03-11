import logging

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
from fastapi.responses import JSONResponse

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
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

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
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}
