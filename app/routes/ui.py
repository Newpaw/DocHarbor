from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import SessionLocal, get_db
from app.models import DiscoveryCandidate, Job, JobEvent, ProcessedPage
from app.services.brave_search_service import BraveSearchRateLimitError
from app.services.discovery_service import DiscoveryService
from app.services.ingestion_service import IngestionService
from app.services.inspection_service import InspectionService


templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


def _capabilities() -> dict[str, bool]:
    settings = get_settings()
    return {
        "brave_available": bool(settings.brave_search_api_key),
        "openai_available": bool(settings.openai_api_key),
        "playwright_available": bool(
            settings.enable_playwright_fallback and importlib.util.find_spec("playwright") is not None
        ),
    }


def _to_bool(value: str | None) -> bool:
    return value in {"on", "true", "1", "yes"}


def _normalized_tag(value: str | None) -> str | None:
    tags = Job.normalize_tags(value)
    return tags[0] if tags else None


def _apply_tag_filter(query, tag: str | None):
    normalized = _normalized_tag(tag)
    if not normalized:
        return query, None
    return query.where(Job.tags_text.like(f"%,{normalized},%")), normalized


def _all_tags(db: Session) -> list[str]:
    jobs = db.execute(select(Job.tags_text).where(Job.tags_text.is_not(None))).all()
    tags: set[str] = set()
    for (tags_text,) in jobs:
        if tags_text:
            tags.update(tag for tag in tags_text.strip(",").split(",") if tag)
    return sorted(tags)


def _page_previews(pages: list[ProcessedPage], limit: int = 6) -> list[dict[str, str | int | None]]:
    previews: list[dict[str, str | int | None]] = []
    for page in sorted(pages, key=lambda item: item.id or 0, reverse=True):
        excerpt = None
        if page.markdown_path and Path(page.markdown_path).exists():
            content = Path(page.markdown_path).read_text(encoding="utf-8").strip()
            excerpt = content[:280].strip() if content else None
        previews.append(
            {
                "title": page.title or page.source_url,
                "url": page.source_url,
                "depth": page.depth,
                "word_count": page.word_count,
                "status": page.status,
                "excerpt": excerpt or page.extraction_notes or "Content is still being prepared.",
            }
        )
    return previews[:limit]


def _build_progress(job: Job, pages: list[ProcessedPage]) -> dict[str, object]:
    processed = job.pages_processed or len([page for page in pages if page.status == "completed"])
    total = job.pages_discovered or (1 if job.final_strategy != "multi_page_docs" and job.status in {"queued", "running", "completed", "failed"} else 0)

    if job.status == "completed":
        percent = 100
    elif total > 0:
        percent = max(8, min(96, round((processed / total) * 100)))
    elif job.status == "running":
        percent = 18
    elif job.status == "queued":
        percent = 6
    else:
        percent = 0

    if job.status == "failed":
        percent = max(percent, 12)

    stages = [
        {
            "label": "Queued",
            "state": "done" if job.status in {"running", "completed"} else ("active" if job.status == "queued" else "idle"),
        },
        {
            "label": "Fetching",
            "state": "done" if total > 0 else ("active" if job.status == "running" else "idle"),
        },
        {
            "label": "Extracting",
            "state": "done" if total > 0 and processed >= total else ("active" if processed > 0 or job.status == "running" else "idle"),
        },
        {
            "label": "Exporting",
            "state": "done" if job.status == "completed" else ("active" if job.status == "running" and total > 0 and processed >= total else "idle"),
        },
    ]

    if job.status == "failed":
        headline = "Job failed before the export finished."
    elif job.status == "completed":
        headline = "Export complete."
    elif processed > 0 and total > 0:
        headline = f"{processed} of {total} pages processed."
    elif total > 0:
        headline = f"{total} pages discovered. Extraction is starting."
    elif job.status == "running":
        headline = "Preparing the source and collecting pages."
    elif job.status == "queued":
        headline = "Waiting for the background worker to start."
    else:
        headline = "Waiting for processing to begin."

    return {
        "percent": percent,
        "processed": processed,
        "total": total,
        "headline": headline,
        "stages": stages,
    }


def _run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = (
            db.execute(
                select(Job)
                .options(selectinload(Job.discovery_candidates))
                .where(Job.id == job_id)
            )
            .scalar_one()
        )
        IngestionService().process_job(db, job)
    finally:
        db.close()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, tag: str | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    query, active_tag = _apply_tag_filter(select(Job).order_by(desc(Job.created_at)), tag)
    recent_jobs = db.execute(query.limit(5)).scalars().all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "capabilities": _capabilities(),
            "jobs": recent_jobs,
            "defaults": get_settings(),
            "active_tag": active_tag,
            "all_tags": _all_tags(db),
        },
    )


@router.post("/discover", response_class=HTMLResponse)
def discover(
    request: Request,
    software_name: str = Form(default=""),
    input_url: str = Form(default=""),
    user_notes: str = Form(default=""),
    tags: str = Form(default=""),
    max_depth: int = Form(default=2),
    max_pages: int = Form(default=30),
    same_domain_only: str | None = Form(default=None),
    js_fallback_enabled: str | None = Form(default=None),
    output_mode: str = Form(default="compiled_only"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not software_name and not input_url:
        raise HTTPException(status_code=400, detail="Provide a software name or a URL.")

    job = Job(
        software_name=software_name or None,
        input_url=input_url or None,
        user_notes=user_notes or None,
        max_depth=max_depth,
        max_pages=max_pages,
        same_domain_only=_to_bool(same_domain_only),
        js_fallback_enabled=_to_bool(js_fallback_enabled),
        output_mode=output_mode,
        status="discovering",
    )
    job.set_tags(tags)
    db.add(job)
    db.commit()
    db.refresh(job)

    if input_url:
        try:
            inspection = InspectionService().inspect_source(input_url)
        except Exception as exc:
            job.status = "failed"
            job.failure_count += 1
            db.add(
                JobEvent(
                    job_id=job.id,
                    level="ERROR",
                    event_type="inspection_failed",
                    message=f"Inspection failed: {exc}",
                    related_url=input_url,
                )
            )
            db.commit()
            return templates.TemplateResponse(
                request,
                "home.html",
                {
                    "capabilities": _capabilities(),
                    "jobs": db.execute(select(Job).order_by(desc(Job.created_at)).limit(5)).scalars().all(),
                    "defaults": get_settings(),
                    "error": f"Inspection failed for the provided URL: {exc}",
                    "all_tags": _all_tags(db),
                },
                status_code=400,
            )
        job.selected_source_url = inspection.normalized_url
        job.selected_source_type = inspection.detected_source_type
        job.proposed_strategy = inspection.recommended_ingestion_strategy
        job.crawl_prefix = inspection.recommended_crawl_prefix
        job.inspection_confidence = inspection.confidence
        job.inspection_reasoning = "\n".join(inspection.reasoning)
        job.status = "inspected"
        db.add(
            JobEvent(
                job_id=job.id,
                level="INFO",
                event_type="source_classified",
                message=f"Inspected direct URL as {inspection.detected_source_type}.",
                related_url=inspection.normalized_url,
            )
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "inspection.html",
            {
                "job": job,
                "inspection": inspection,
                "capabilities": _capabilities(),
            },
        )

    discovery = DiscoveryService()
    if not discovery.is_available():
        job.status = "failed"
        job.failure_count += 1
        db.add(
            JobEvent(
                job_id=job.id,
                level="ERROR",
                event_type="discovery_unavailable",
                message="Brave Search is not configured.",
            )
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "capabilities": _capabilities(),
                "jobs": db.execute(select(Job).order_by(desc(Job.created_at)).limit(5)).scalars().all(),
                "defaults": get_settings(),
                "error": "Brave Search is not configured. Use a direct URL or set BRAVE_SEARCH_API_KEY.",
                "all_tags": _all_tags(db),
            },
            status_code=400,
        )

    try:
        candidates = discovery.discover(software_name)
    except BraveSearchRateLimitError as exc:
        job.status = "failed"
        job.failure_count += 1
        db.add(
            JobEvent(
                job_id=job.id,
                level="ERROR",
                event_type="discovery_rate_limited",
                message=str(exc),
            )
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "capabilities": _capabilities(),
                "jobs": db.execute(select(Job).order_by(desc(Job.created_at)).limit(5)).scalars().all(),
                "defaults": get_settings(),
                "error": str(exc),
                "all_tags": _all_tags(db),
            },
            status_code=429,
        )
    except Exception as exc:
        job.status = "failed"
        job.failure_count += 1
        db.add(
            JobEvent(
                job_id=job.id,
                level="ERROR",
                event_type="discovery_failed",
                message=f"Discovery failed: {exc}",
            )
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "capabilities": _capabilities(),
                "jobs": db.execute(select(Job).order_by(desc(Job.created_at)).limit(5)).scalars().all(),
                "defaults": get_settings(),
                "error": f"Discovery failed: {exc}",
                "all_tags": _all_tags(db),
            },
            status_code=400,
        )
    if not candidates:
        job.status = "failed"
        job.failure_count += 1
        db.add(
            JobEvent(
                job_id=job.id,
                level="ERROR",
                event_type="discovery_failed",
                message="Discovery returned no candidates.",
            )
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "capabilities": _capabilities(),
                "jobs": db.execute(select(Job).order_by(desc(Job.created_at)).limit(5)).scalars().all(),
                "defaults": get_settings(),
                "error": "Discovery returned no documentation candidates.",
                "all_tags": _all_tags(db),
            },
            status_code=404,
        )

    for candidate in candidates:
        candidate.job_id = job.id
        db.add(candidate)
        db.add(
            JobEvent(
                job_id=job.id,
                level="INFO",
                event_type="candidate_found",
                message=f"Candidate found: {candidate.title}",
                related_url=candidate.url,
            )
        )

    job.status = "awaiting_selection"
    db.commit()
    db.refresh(job)

    return templates.TemplateResponse(
        request,
        "discovery.html",
        {
            "job": job,
            "candidates": db.execute(
                select(DiscoveryCandidate)
                .where(DiscoveryCandidate.job_id == job.id)
                .order_by(desc(DiscoveryCandidate.confidence_score))
            ).scalars().all(),
            "capabilities": _capabilities(),
        },
    )


@router.post("/jobs/{job_id}/inspect", response_class=HTMLResponse)
def inspect_candidate(
    job_id: int,
    request: Request,
    candidate_id: int = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    job = db.get(Job, job_id)
    candidate = db.get(DiscoveryCandidate, candidate_id)
    if not job or not candidate or candidate.job_id != job.id:
        raise HTTPException(status_code=404, detail="Job or candidate not found.")

    try:
        inspection = InspectionService().inspect_source(candidate.url)
    except Exception as exc:
        job.status = "failed"
        job.failure_count += 1
        db.add(
            JobEvent(
                job_id=job.id,
                level="ERROR",
                event_type="inspection_failed",
                message=f"Candidate inspection failed: {exc}",
                related_url=candidate.url,
            )
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "discovery.html",
            {
                "job": job,
                "candidates": db.execute(
                    select(DiscoveryCandidate)
                    .where(DiscoveryCandidate.job_id == job.id)
                    .order_by(desc(DiscoveryCandidate.confidence_score))
                ).scalars().all(),
                "capabilities": _capabilities(),
                "error": f"Inspection failed for the selected candidate: {exc}",
            },
            status_code=400,
        )
    job.selected_source_url = inspection.normalized_url
    job.selected_source_type = inspection.detected_source_type
    job.proposed_strategy = inspection.recommended_ingestion_strategy
    job.crawl_prefix = inspection.recommended_crawl_prefix
    job.selected_domain = candidate.domain
    job.inspection_confidence = inspection.confidence
    job.inspection_reasoning = "\n".join(inspection.reasoning)
    job.status = "inspected"
    db.add(
        JobEvent(
            job_id=job.id,
            level="INFO",
            event_type="candidate_selected",
            message=f"Selected candidate: {candidate.title}",
            related_url=candidate.url,
        )
    )
    db.commit()
    db.refresh(job)

    return templates.TemplateResponse(
        request,
        "inspection.html",
        {
            "job": job,
            "inspection": inspection,
            "selected_candidate": candidate,
            "capabilities": _capabilities(),
        },
    )


@router.post("/jobs/{job_id}/process")
def process_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    final_strategy: str = Form(...),
    source_type: str = Form(...),
    crawl_prefix: str = Form(default=""),
    max_depth: int = Form(default=2),
    max_pages: int = Form(default=30),
    same_domain_only: str | None = Form(default=None),
    js_fallback_enabled: str | None = Form(default=None),
    output_mode: str = Form(default="compiled_only"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job.selected_source_type = source_type
    job.final_strategy = final_strategy
    job.crawl_prefix = crawl_prefix or None
    job.max_depth = max_depth
    job.max_pages = max_pages
    job.same_domain_only = _to_bool(same_domain_only)
    job.js_fallback_enabled = _to_bool(js_fallback_enabled)
    job.output_mode = output_mode
    job.status = "queued"
    db.add(
        JobEvent(
            job_id=job.id,
            level="INFO",
            event_type="job_queued",
            message=f"Queued processing with strategy {final_strategy}.",
        )
    )
    db.commit()

    background_tasks.add_task(_run_job, job.id)
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@router.get("/jobs", response_class=HTMLResponse)
def job_history(request: Request, tag: str | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    query, active_tag = _apply_tag_filter(select(Job).order_by(desc(Job.created_at)), tag)
    jobs = db.execute(query).scalars().all()
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "jobs": jobs,
            "capabilities": _capabilities(),
            "active_tag": active_tag,
            "all_tags": _all_tags(db),
        },
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = (
        db.execute(
            select(Job)
            .options(
                selectinload(Job.discovery_candidates),
                selectinload(Job.processed_pages),
                selectinload(Job.events),
            )
            .where(Job.id == job_id)
        )
        .scalar_one_or_none()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    pages = sorted(job.processed_pages, key=lambda item: (item.depth, item.id))
    warning_events = [event for event in job.events if event.level == "WARNING"][-6:]
    error_events = [event for event in job.events if event.level == "ERROR"][-6:]
    template = "results.html" if job.status == "completed" else "status.html"
    return templates.TemplateResponse(
        request,
        template,
        {
            "job": job,
            "pages": pages,
            "events": job.events[-20:],
            "progress": _build_progress(job, pages),
            "page_previews": _page_previews(pages),
            "warning_events": warning_events,
            "error_events": error_events,
            "capabilities": _capabilities(),
        },
    )


@router.get("/jobs/{job_id}/pages", response_class=HTMLResponse)
def pages(request: Request, job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    pages = db.execute(
        select(ProcessedPage).where(ProcessedPage.job_id == job_id).order_by(ProcessedPage.depth, ProcessedPage.id)
    ).scalars().all()
    return templates.TemplateResponse(
        request,
        "pages.html",
        {"job": job, "pages": pages, "capabilities": _capabilities()},
    )


@router.get("/jobs/{job_id}/logs", response_class=HTMLResponse)
def logs(request: Request, job_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    events = db.execute(
        select(JobEvent).where(JobEvent.job_id == job_id).order_by(desc(JobEvent.timestamp))
    ).scalars().all()
    return templates.TemplateResponse(
        request,
        "logs.html",
        {"job": job, "events": events, "capabilities": _capabilities()},
    )


@router.get("/jobs/{job_id}/download/{artifact}")
def download_artifact(job_id: int, artifact: str, db: Session = Depends(get_db)) -> FileResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    mapping = {
        "compiled": job.compiled_markdown_path,
        "manifest": job.manifest_path,
        "zip": job.zip_path,
    }
    path = mapping.get(artifact)
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path, filename=Path(path).name)


@router.post("/jobs/{job_id}/tags")
def update_job_tags(
    job_id: int,
    tags: str = Form(default=""),
    redirect_to: str = Form(default="/jobs"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.set_tags(tags)
    db.add(
        JobEvent(
            job_id=job.id,
            level="INFO",
            event_type="tags_updated",
            message=f"Updated tags: {', '.join(job.tags) if job.tags else 'none'}",
        )
    )
    db.commit()
    return RedirectResponse(url=redirect_to or "/jobs", status_code=303)


@router.post("/jobs/{job_id}/delete")
def delete_job(
    job_id: int,
    redirect_to: str = Form(default="/jobs"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job_dir = get_settings().export_root / str(job.id)
    db.delete(job)
    db.commit()
    shutil.rmtree(job_dir, ignore_errors=True)
    return RedirectResponse(url=redirect_to or "/jobs", status_code=303)
