from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models

    models  # pragma: no cover
    Base.metadata.create_all(bind=engine)
    _apply_migrations()


def _apply_migrations() -> None:
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("jobs")}
    if "tags_text" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE jobs ADD COLUMN tags_text TEXT"))
