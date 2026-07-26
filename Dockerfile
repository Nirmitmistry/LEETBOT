# ── Stage 1: Build frontend ──────────────────────────────────────────────────
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --production=false
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend ─────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/
COPY ingestion/ ./ingestion/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
