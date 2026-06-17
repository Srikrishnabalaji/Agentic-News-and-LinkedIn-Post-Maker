"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import PostStatus, RunStatus


class ImageOption(BaseModel):
    url: str
    thumb: str
    attribution: str
    source: str
    license: str
    source_url: str = ""


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int | None
    headline: str
    body: str
    format_type: str
    hashtags: list[str]
    char_count: int

    image_recommended: bool
    image_reason: str | None
    image_url: str | None
    image_attribution: str | None
    image_options: list[ImageOption]

    source_url: str | None
    source_name: str | None
    topic_key: str | None
    is_pivotal: bool

    status: PostStatus
    created_at: datetime
    updated_at: datetime
    posted_at: datetime | None
    linkedin_post_id: str | None


class PostUpdate(BaseModel):
    headline: str | None = None
    body: str | None = None
    hashtags: list[str] | None = None
    image_url: str | None = None
    image_attribution: str | None = None


class StatusUpdate(BaseModel):
    status: PostStatus


class ImageSearchRequest(BaseModel):
    query: str
    article_image: str | None = None
    source_name: str = ""
    page: int = 1  # 1-based; passed through to each provider for Load More


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: RunStatus
    num_candidates: int
    num_posts: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class PipelineResult(BaseModel):
    run_id: int
    num_posts: int
    email_sent: bool
