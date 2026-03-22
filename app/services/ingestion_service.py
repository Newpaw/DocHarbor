from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job, JobEvent, ProcessedPage
from app.services.crawler_service import CrawlerService
from app.services.extraction_service import ExtractionService
from app.services.export_service import ExportService
from app.services.fetch_service import FetchService
from app.services.pdf_service import PDFService


class IngestionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.fetch_service = FetchService()
        self.crawler_service = CrawlerService()
        self.extraction_service = ExtractionService()
        self.export_service = ExportService()
        self.pdf_service = PDFService()

    def process_job(self, db: Session, job: Job) -> None:
        job.status = "running"
        self._log(db, job.id, "INFO", "job_started", "Processing job started.")
        db.commit()

        job_dir = self.export_service.build_job_dir(self.settings.export_root, job.id)
        try:
            if job.final_strategy == "multi_page_docs":
                pages = self._process_multi_page(db, job, job_dir)
            else:
                pages = [self._process_single_resource(db, job, job.selected_source_url or job.input_url or "", job_dir)]

            self._log(db, job.id, "INFO", "export_started", "Building final export artifacts.")
            db.commit()
            compiled_path = self.export_service.write_compiled_markdown(job_dir, job, pages)
            manifest_path = self.export_service.write_manifest(
                job_dir,
                job,
                pages,
                [
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
                    for candidate in job.discovery_candidates
                ],
            )
            zip_path = self.export_service.write_zip(job_dir) if job.output_mode == "full_package" else None

            job.compiled_markdown_path = str(compiled_path)
            job.manifest_path = str(manifest_path)
            job.zip_path = str(zip_path) if zip_path else None
            job.pages_processed = len(pages)
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            self._log(db, job.id, "INFO", "export_completed", "Export finished successfully.")
            db.commit()
        except Exception as exc:
            job.status = "failed"
            job.failure_count += 1
            job.finished_at = datetime.utcnow()
            self._log(db, job.id, "ERROR", "job_failed", f"Job failed: {exc}")
            db.commit()
            raise

    def _process_multi_page(self, db: Session, job: Job, job_dir: Path) -> list[ProcessedPage]:
        start_url = job.selected_source_url or job.input_url or ""
        self._log(db, job.id, "INFO", "crawl_started", f"Starting crawl from {start_url}", start_url)
        db.commit()
        pages, warnings = self.crawler_service.crawl(
            start_url,
            allowed_prefix=job.crawl_prefix,
            max_depth=job.max_depth,
            max_pages=job.max_pages,
            same_domain_only=job.same_domain_only,
        )
        job.pages_discovered = len(pages)
        self._log(
            db,
            job.id,
            "INFO",
            "crawl_discovered",
            f"Discovered {len(pages)} page(s) within the crawl scope.",
            start_url,
        )
        db.commit()

        for warning in warnings:
            job.warning_count += 1
            self._log(db, job.id, "WARNING", "crawl_warning", warning)
        if warnings:
            db.commit()

        processed_pages: list[ProcessedPage] = []
        for crawled_page in pages:
            record = ProcessedPage(
                job_id=job.id,
                source_url=crawled_page.source_url,
                normalized_url=crawled_page.normalized_url,
                depth=crawled_page.depth,
                status="processing",
                http_status=crawled_page.response.status_code,
                content_type=crawled_page.response.content_type,
            )
            db.add(record)
            db.flush()

            extracted = self.extraction_service.extract_html(
                crawled_page.response.text,
                crawled_page.normalized_url,
            )
            record.title = extracted.title
            record.status = "completed"
            record.word_count = len(extracted.markdown.split())
            record.extraction_notes = "\n".join(extracted.notes) if extracted.notes else None
            markdown_path = self.export_service.write_page_markdown(job_dir, record, extracted.markdown)
            record.markdown_path = str(markdown_path)
            processed_pages.append(record)
            job.pages_processed = len(processed_pages)
            self._log(db, job.id, "INFO", "page_processed", f"Processed {record.source_url}", record.source_url)
            db.commit()

        return processed_pages

    def _process_single_resource(self, db: Session, job: Job, url: str, job_dir: Path) -> ProcessedPage:
        self._log(db, job.id, "INFO", "fetch_started", f"Fetching single resource {url}", url)
        db.commit()
        response = self.fetch_service.fetch(url)
        page = ProcessedPage(
            job_id=job.id,
            source_url=url,
            normalized_url=response.final_url,
            depth=0,
            status="processing",
            http_status=response.status_code,
            content_type=response.content_type,
        )
        job.pages_discovered = 1
        db.add(page)
        db.flush()

        if job.final_strategy == "pdf":
            title, markdown, notes = self.pdf_service.extract_markdown(response.content, response.final_url)
        elif job.final_strategy == "markdown":
            extracted = self.extraction_service.extract_markdown(response.text, response.final_url)
            title, markdown, notes = extracted.title, extracted.markdown, extracted.notes
        elif job.final_strategy == "plain_text":
            extracted = self.extraction_service.extract_plain_text(response.text, response.final_url)
            title, markdown, notes = extracted.title, extracted.markdown, extracted.notes
        else:
            extracted = self.extraction_service.extract_html(response.text, response.final_url)
            title, markdown, notes = extracted.title, extracted.markdown, extracted.notes

        page.title = title
        page.status = "completed"
        page.word_count = len(markdown.split())
        page.extraction_notes = "\n".join(notes) if notes else None
        markdown_path = self.export_service.write_page_markdown(job_dir, page, markdown)
        page.markdown_path = str(markdown_path)
        job.pages_processed = 1
        self._log(db, job.id, "INFO", "page_processed", f"Processed {url}", url)
        db.commit()
        return page

    def _log(
        self,
        db: Session,
        job_id: int,
        level: str,
        event_type: str,
        message: str,
        related_url: str | None = None,
    ) -> None:
        db.add(
            JobEvent(
                job_id=job_id,
                level=level,
                event_type=event_type,
                message=message,
                related_url=related_url,
            )
        )
