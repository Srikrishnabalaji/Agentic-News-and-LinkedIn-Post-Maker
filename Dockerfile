# ---- Stage 1: build the React frontend ----
FROM node:22-alpine AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build           # outputs /fe/dist

# ---- Stage 2: Python backend serving API + built frontend ----
FROM python:3.11-slim AS backend
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# Bundle the compiled frontend so FastAPI can serve it (single service).
COPY --from=frontend /fe/dist ./app/static

EXPOSE 8000
# Railway injects $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
