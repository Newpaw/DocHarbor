from datetime import datetime

from pydantic import BaseModel, HttpUrl


class CapabilityStatus(BaseModel):
    brave_available: bool
    openai_available: bool
    playwright_available: bool


class DiscoveryCandidateRead(BaseModel):
    id: int
    title: str
    url: str
    domain: str
    reason: str
    confidence_score: float
    likely_source_type: str
    appears_official: bool


class InspectionResult(BaseModel):
    selected_url: str
    normalized_url: str
    detected_source_type: str
    confidence: float
    reasoning: list[str]
    recommended_ingestion_strategy: str
    recommended_crawl_prefix: str | None = None


class ProcessedPageRead(BaseModel):
    id: int
    source_url: str
    normalized_url: str
    title: str | None
    depth: int
    status: str
    http_status: int | None
    content_type: str | None
    word_count: int
    markdown_path: str | None
    extraction_notes: str | None
    warning_message: str | None
    created_at: datetime


class JobEventRead(BaseModel):
    id: int
    timestamp: datetime
    level: str
    event_type: str
    message: str
    related_url: str | None


class JobRead(BaseModel):
    id: int
    software_name: str | None
    input_url: str | None
    selected_source_url: str | None
    selected_source_type: str | None
    proposed_strategy: str | None
    final_strategy: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    max_depth: int
    max_pages: int
    same_domain_only: bool
    js_fallback_enabled: bool
    output_mode: str
    crawl_prefix: str | None
    compiled_markdown_path: str | None
    zip_path: str | None
    manifest_path: str | None
    warning_count: int
    failure_count: int
    pages_discovered: int
    pages_processed: int
    inspection_confidence: float | None
    inspection_reasoning: str | None


class DiscoverRequest(BaseModel):
    software_name: str | None = None
    input_url: HttpUrl | None = None
    user_notes: str | None = None
    max_depth: int = 2
    max_pages: int = 30
    same_domain_only: bool = True
    js_fallback_enabled: bool = False
    output_mode: str = "compiled_only"


class ProcessRequest(BaseModel):
    final_strategy: str
    source_type: str
    crawl_prefix: str | None = None
    max_depth: int = 2
    max_pages: int = 30
    same_domain_only: bool = True
    js_fallback_enabled: bool = False
    output_mode: str = "compiled_only"
