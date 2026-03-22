from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    software_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    proposed_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    final_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    selected_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_depth: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_pages: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    same_domain_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    js_fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    output_mode: Mapped[str] = mapped_column(String(50), default="compiled_only", nullable=False)
    crawl_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    compiled_markdown_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    zip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inspection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    inspection_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    discovery_candidates: Mapped[list["DiscoveryCandidate"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    processed_pages: Mapped[list["ProcessedPage"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["JobEvent"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobEvent.timestamp",
    )

    @property
    def tags(self) -> list[str]:
        if not self.tags_text:
            return []
        return [tag for tag in self.tags_text.strip(",").split(",") if tag]

    @staticmethod
    def normalize_tags(raw: str | list[str] | None) -> list[str]:
        if raw is None:
            return []
        items = raw if isinstance(raw, list) else raw.split(",")
        seen: set[str] = set()
        normalized: list[str] = []
        for item in items:
            tag = item.strip().lower()
            if not tag:
                continue
            if tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)
        return normalized

    def set_tags(self, raw: str | list[str] | None) -> None:
        tags = self.normalize_tags(raw)
        self.tags_text = f",{','.join(tags)}," if tags else None


class DiscoveryCandidate(Base):
    __tablename__ = "discovery_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    likely_source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    appears_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    job: Mapped[Job] = relationship(back_populates="discovery_candidates")


class ProcessedPage(Base):
    __tablename__ = "processed_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    markdown_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="processed_pages")


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    level: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="events")
