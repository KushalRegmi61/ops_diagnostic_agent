"""SQLAlchemy engine + SessionLocal sanity checks against the real SQLite engine."""
from sqlalchemy import text

from app.database import SessionLocal, engine


def test_engine_connects():
    """The configured SQLite engine accepts a basic SELECT 1 round-trip."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_factory_yields_session():
    """SessionLocal() yields an active SQLAlchemy session usable as a context manager."""
    with SessionLocal() as session:
        assert session.is_active
