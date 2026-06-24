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


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    post_id: int
    impressions: int
    reactions: int
    comments: int
    reposts: int
    updated_at: datetime | None = None


class MetricsUpdate(BaseModel):
    impressions: int | None = None
    reactions: int | None = None
    comments: int | None = None
    reposts: int | None = None


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
    is_update: bool = False
    category: str = "security"

    status: PostStatus
    created_at: datetime
    updated_at: datetime
    posted_at: datetime | None
    linkedin_post_id: str | None

    metrics: MetricsOut | None = None


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


class RSSSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    category: str
    authority: float
    audience: str
    enabled: bool
    is_custom: bool


class RSSSourceCreate(BaseModel):
    name: str
    url: str
    category: str = "security"
    authority: float = 0.8
    audience: str = "consumer"


class RSSSourceUpdate(BaseModel):
    name: str | None = None
    authority: float | None = None
    enabled: bool | None = None


class SourceSuggestion(BaseModel):
    name: str
    url: str
    authority: float = 0.8
    category: str = "security"


class AISuggestRequest(BaseModel):
    category: str = "security"


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    source_name: str
    summary: str | None
    lead_image_url: str | None
    published_at: datetime | None
    category: str
    score: float
    status: str


class CandidateListOut(BaseModel):
    candidates: list[CandidateOut]
    dismissed_count: int
    has_more: bool


class CandidateGenerateRequest(BaseModel):
    candidate_ids: list[int]


class LiveSearchResult(BaseModel):
    title: str
    url: str
    content: str = ""
    published_date: str | None = None
    source: str = ""


class SearchGenerateRequest(BaseModel):
    url: str
    title: str
    summary: str = ""
    category: str = "security"


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
