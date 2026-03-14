# ===========================================================================
# GDMS Space Hardware Assistant — Single-container build
#
# Stage 1: Build React frontend with Vite
# Stage 2: Python backend serving API + static frontend
#
# Build:  docker build -t gdms-sha .
# Run:    docker run -p 8000:8000 --env-file .env gdms-sha
#
# The container serves:
#   /api/*     → FastAPI backend
#   /health    → health check
#   /*         → React SPA (static files)
# ===========================================================================

# ── Stage 1: Frontend build ────────────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Backend + static files ────────────────────────────────────────
FROM python:3.12-slim

# System deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./

# Frontend static files from Stage 1
COPY --from=frontend /app/frontend/dist ./static

# Data directory (mount as volume for persistence)
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV STATIC_DIR=/app/static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
