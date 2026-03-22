from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_name: str = "DocHarbor"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///data/app.db"
    export_root: Path = Path("data/jobs")

    brave_search_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    default_max_depth: int = 2
    default_max_pages: int = 30
    fetch_timeout_seconds: int = 20
    enable_playwright_fallback: bool = False
    default_same_domain_only: bool = True
    user_agent: str = Field(
        default="DocHarborBot/0.1 (+https://local-doc-harbor.invalid)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.export_root.mkdir(parents=True, exist_ok=True)
    return settings
