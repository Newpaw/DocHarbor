import json
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.models import Job, ProcessedPage
from app.services.url_utils import sanitize_filename


class ExportService:
    def build_job_dir(self, export_root: Path, job_id: int) -> Path:
        job_dir = export_root / str(job_id)
        (job_dir / "pages").mkdir(parents=True, exist_ok=True)
        (job_dir / "logs").mkdir(parents=True, exist_ok=True)
        (job_dir / "raw").mkdir(parents=True, exist_ok=True)
        return job_dir

    def write_page_markdown(self, job_dir: Path, page: ProcessedPage, markdown: str) -> Path:
        title = sanitize_filename(page.title or f"page-{page.id}")
        path = job_dir / "pages" / f"{title}.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def write_compiled_markdown(self, job_dir: Path, job: Job, pages: list[ProcessedPage]) -> Path:
        sections: list[str] = []
        toc: list[str] = []
        document_title = job.software_name or job.selected_source_url or f"Job {job.id}"

        header = [
            f"# {document_title}",
            "",
            f"- Source: {job.selected_source_url or job.input_url or 'N/A'}",
            f"- Captured at: {datetime.utcnow().isoformat()}Z",
            f"- Processing mode: {job.final_strategy or job.proposed_strategy or 'unknown'}",
            f"- Source type: {job.selected_source_type or 'unknown'}",
            f"- Page count: {len(pages)}",
            "",
        ]

        for index, page in enumerate(pages, start=1):
            anchor = sanitize_filename(page.title or f"page-{index}")
            toc.append(f"- [{page.title or f'Page {index}'}](#{anchor.lower()})")

        if toc:
            header.extend(["## Table of Contents", "", *toc, ""])

        for index, page in enumerate(pages, start=1):
            markdown = ""
            if page.markdown_path:
                markdown = Path(page.markdown_path).read_text(encoding="utf-8")
            sections.extend(
                [
                    f"## {page.title or f'Page {index}'}",
                    "",
                    f"- Source URL: {page.source_url}",
                    f"- Normalized URL: {page.normalized_url}",
                    f"- Crawl depth: {page.depth}",
                    "",
                    markdown or "_No content exported._",
                    "",
                ]
            )

        compiled = "\n".join(header + sections).strip() + "\n"
        path = job_dir / "compiled.md"
        path.write_text(compiled, encoding="utf-8")
        return path

    def write_manifest(self, job_dir: Path, job: Job, pages: list[ProcessedPage], candidates: list[dict]) -> Path:
        manifest = {
            "job": {
                "id": job.id,
                "software_name": job.software_name,
                "input_url": job.input_url,
                "selected_source_url": job.selected_source_url,
                "source_type": job.selected_source_type,
                "proposed_strategy": job.proposed_strategy,
                "final_strategy": job.final_strategy,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "max_depth": job.max_depth,
                "max_pages": job.max_pages,
                "same_domain_only": job.same_domain_only,
                "js_fallback_enabled": job.js_fallback_enabled,
                "output_mode": job.output_mode,
                "warning_count": job.warning_count,
                "failure_count": job.failure_count,
            },
            "candidates": candidates,
            "pages": [
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
                }
                for page in pages
            ],
        }
        path = job_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path

    def write_zip(self, job_dir: Path) -> Path:
        zip_path = job_dir / "artifacts.zip"
        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
            for path in job_dir.rglob("*"):
                if path == zip_path or path.is_dir():
                    continue
                archive.write(path, path.relative_to(job_dir))
        return zip_path
