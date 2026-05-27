"""SQLAlchemy 2.x engine, session factory, and declarative Base.

Backs the persistence layer used by ``app.services.*`` to record runs, files,
file summaries, intake bundles, and blueprints. The engine is built lazily
from current Settings on first access so tests can reconfigure the DSN.
"""
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models in ``app.models``."""

    pass


def _normalize_db_url(url: str) -> str:
    """Pin Postgres URLs to the psycopg (v3) driver so vendor-supplied DSNs work as-is."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):  # Heroku-style alias
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


@lru_cache(maxsize=1)
def _build_engine() -> Engine:
    """Construct the SQLAlchemy engine from current Settings (cached per process)."""
    settings = get_settings()
    db_url = _normalize_db_url(settings.database_url)
    eng = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
    )
    if db_url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _sqlite_fk_pragma(dbapi_conn, _conn_record):
            """Enable FK enforcement for every new SQLite connection."""
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return eng


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
