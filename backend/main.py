from dotenv import load_dotenv

# Load .env before any module that reads environment variables is imported.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import librarian, fpga

app = FastAPI(
    title="GDMS Space Hardware Assistant API",
    description="Backend for the Component Librarian and future GDMS modules.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(librarian.router, prefix="/api", tags=["librarian"])
app.include_router(fpga.router, prefix="/api", tags=["fpga"])


@app.get("/health")
def health():
    return {"status": "ok"}
