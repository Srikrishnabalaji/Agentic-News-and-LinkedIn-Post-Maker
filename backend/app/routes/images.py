"""Image search and upload endpoints."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, HTTPException, UploadFile

from ..generator.images import find_images
from ..schemas import ImageOption, ImageSearchRequest

router = APIRouter(prefix="/images", tags=["images"])

# Resolved at startup; Railway containers are ephemeral but the uploads
# only need to live for the current review session (same day).
_UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/search", response_model=list[ImageOption])
def search_images(payload: ImageSearchRequest):
    # 20 options per page fills the expanded modal grid with real variety.
    return find_images(
        payload.query, payload.article_image, payload.source_name,
        max_options=20, page=payload.page,
    )


@router.post("/upload", response_model=ImageOption)
async def upload_image(file: UploadFile):
    """Accept an image file from the reviewer's computer.

    Returns an ImageOption whose URL points to /uploads/<filename> so the
    frontend can display it in the LinkedIn preview like any other image.
    The file lives for the duration of the process (session-scoped).
    """
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            415,
            f"Unsupported file type: {file.content_type}. "
            f"Allowed: {', '.join(_ALLOWED_TYPES)}",
        )

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, "File exceeds 10 MB limit")

    os.makedirs(_UPLOADS_DIR, exist_ok=True)
    ext = (file.filename or "upload").rsplit(".", 1)[-1].lower() or "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(_UPLOADS_DIR, filename)
    with open(dest, "wb") as fh:
        fh.write(data)

    url = f"/uploads/{filename}"
    return ImageOption(
        url=url,
        thumb=url,
        attribution=f"Uploaded: {file.filename}",
        source="Upload",
        license="Your own file — no restrictions",
        source_url="",
    )
