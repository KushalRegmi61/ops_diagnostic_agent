"""SQLAlchemy 2.x engine, session factory, and declarative Base.

Backs the persistence layer used by `app.services.*` to record runs, files,
file summaries, intake bundles, and blueprints. The engine is constructed
once from the configured `database_url` (typically SQLite for local dev).
"""
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models in `app.models`."""

    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a Session and guarantees close() on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
