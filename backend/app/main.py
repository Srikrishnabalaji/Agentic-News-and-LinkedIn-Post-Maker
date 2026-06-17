"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routes import images, posts, runs

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(
    title="QuantrixLabs LinkedIn Agent",
    description="Generates, curates, and surfaces daily cybersecurity "
                "LinkedIn drafts for human review.",
    version="1.0.0",
)

# Open access for now (per project decision); tighten with auth when needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts.router)
app.include_router(images.router)
app.include_router(runs.router)


@app.on_event("startup")
def _startup():
    init_db()
    # Ensure the uploads directory exists so the static mount never fails.
    _uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(_uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")


@app.get("/health", tags=["meta"])
def health():
    if settings.has_gemini:
        active_model = settings.gemini_model
    elif settings.has_openai:
        active_model = settings.openai_model
    elif settings.has_anthropic:
        active_model = settings.anthropic_model
    else:
        active_model = "mock"
    return {
        "status": "ok",
        "generator": active_model,
        "gemini": settings.has_gemini,
        "anthropic": settings.has_anthropic,
        "email": settings.has_email,
    }


# Serve the built frontend (single-service deploy) when present. The API
# routers above are registered first, so they take precedence. In local dev
# the Vite server handles the UI and this directory simply won't exist.
_STATIC_DIR = os.getenv("STATIC_DIR", os.path.join(os.path.dirname(__file__), "static"))
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")

