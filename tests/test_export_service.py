from datetime import datetime

from app.models import Job, ProcessedPage
from app.services.export_service import ExportService


def test_manifest_and_zip_generation(tmp_path) -> None:
    service = ExportService()
    job = Job(
        id=7,
        software_name="FastAPI",
        selected_source_url="https://fastapi.tiangolo.com/",
        selected_source_type="multi_page_docs",
        final_strategy="multi_page_docs",
        status="completed",
        created_at=datetime.utcnow(),
        max_depth=2,
        max_pages=10,
        same_domain_only=True,
        js_fallback_enabled=False,
        output_mode="full_package",
        warning_count=0,
        failure_count=0,
    )
    page = ProcessedPage(
        id=1,
        job_id=7,
        source_url="https://fastapi.tiangolo.com/tutorial/",
        normalized_url="https://fastapi.tiangolo.com/tutorial",
        title="Tutorial",
        depth=0,
        status="completed",
        word_count=10,
    )
    job_dir = service.build_job_dir(tmp_path, job.id)
    page_path = service.write_page_markdown(job_dir, page, "# Tutorial")
    page.markdown_path = str(page_path)
    compiled = service.write_compiled_markdown(job_dir, job, [page])
    manifest = service.write_manifest(job_dir, job, [page], [])
    archive = service.write_zip(job_dir)

    assert compiled.exists()
    assert manifest.exists()
    assert archive.exists()
