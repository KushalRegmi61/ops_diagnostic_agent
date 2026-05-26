"""SQLAlchemy 2.x engine, session factory, and declarative Base.

Backs the persistence layer used by ``app.services.*`` to record runs, files,
file summaries, intake bundles, and blueprints. The engine is built lazily
from current Settings on first access so tests can reconfigure the DSN.
"""
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models in ``app.models``."""

    pass


@lru_cache(maxsize=1)
def _build_engine() -> Engine:
    """Construct the SQLAlchemy engine from current Settings (cached per process)."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    )


# Module-level handles built on first access. Tests that reconfigure the DSN
# must call _build_engine.cache_clear() AND rebind the module attributes.
engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a Session and guarantees close() on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
