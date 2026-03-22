from __future__ import annotations

import importlib.util

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import DiscoveryCandidate, Job, JobEvent, ProcessedPage
from app.schemas import CapabilityStatus


router = APIRouter(prefix="/api", tags=["api"])


@router.get("/capabilities", response_model=CapabilityStatus)
def capabilities() -> CapabilityStatus:
    settings = get_settings()
    return CapabilityStatus(
        brave_available=bool(settings.brave_search_api_key),
        openai_available=bool(settings.openai_api_key),
        playwright_available=bool(
            settings.enable_playwright_fallback and importlib.util.find_spec("playwright") is not None
        ),
    )


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)) -> list[dict]:
    jobs = db.execute(select(Job).order_by(desc(Job.created_at))).scalars().all()
    return [serialize_job(job) for job in jobs]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return serialize_job(job)


@router.get("/jobs/{job_id}/candidates")
def list_candidates(job_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": candidate.id,
            "title": candidate.title,
            "url": candidate.url,
            "domain": candidate.domain,
            "reason": candidate.reason,
            "confidence_score": candidate.confidence_score,
            "likely_source_type": candidate.likely_source_type,
            "appears_official": candidate.appears_official,
        }
        for candidate in db.execute(
            select(DiscoveryCandidate)
            .where(DiscoveryCandidate.job_id == job_id)
            .order_by(desc(DiscoveryCandidate.confidence_score))
        ).scalars().all()
    ]


@router.get("/jobs/{job_id}/pages")
def list_pages(job_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": page.id,
            "source_url": page.source_url,
            "normalized_url": page.normalized_url,
            "title": page.title,
            "depth": page.depth,
            "status": page.status,
            "http_status": page.http_status,
            "content_type": page.content_type,
            "word_count": page.word_count,
            "markdown_path": page.markdown_path,
            "extraction_notes": page.extraction_notes,
            "warning_message": page.warning_message,
            "created_at": page.created_at.isoformat(),
        }
        for page in db.execute(
            select(ProcessedPage).where(ProcessedPage.job_id == job_id).order_by(ProcessedPage.depth, ProcessedPage.id)
        ).scalars().all()
    ]


@router.get("/jobs/{job_id}/logs")
def list_logs(job_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": event.id,
            "timestamp": event.timestamp.isoformat(),
            "level": event.level,
            "event_type": event.event_type,
            "message": event.message,
            "related_url": event.related_url,
        }
        for event in db.execute(
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(desc(JobEvent.timestamp))
        ).scalars().all()
    ]


def serialize_job(job: Job) -> dict:
    return {
        "id": job.id,
        "software_name": job.software_name,
        "tags": job.tags,
        "input_url": job.input_url,
        "selected_source_url": job.selected_source_url,
        "selected_source_type": job.selected_source_type,
        "proposed_strategy": job.proposed_strategy,
        "final_strategy": job.final_strategy,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "max_depth": job.max_depth,
        "max_pages": job.max_pages,
        "same_domain_only": job.same_domain_only,
        "js_fallback_enabled": job.js_fallback_enabled,
        "output_mode": job.output_mode,
        "crawl_prefix": job.crawl_prefix,
        "compiled_markdown_path": job.compiled_markdown_path,
        "zip_path": job.zip_path,
        "manifest_path": job.manifest_path,
        "warning_count": job.warning_count,
        "failure_count": job.failure_count,
        "pages_discovered": job.pages_discovered,
        "pages_processed": job.pages_processed,
        "inspection_confidence": job.inspection_confidence,
        "inspection_reasoning": job.inspection_reasoning,
    }
