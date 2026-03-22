from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.routes import api, jobs, ui


settings = get_settings()
init_db()
app = FastAPI(title=settings.app_name)
app.include_router(ui.router)
app.include_router(api.router)
app.include_router(jobs.router)
app.mount("/static", StaticFiles(directory=Path("app/static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/healthz", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
