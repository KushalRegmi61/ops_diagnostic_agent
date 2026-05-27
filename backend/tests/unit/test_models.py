"""Unit tests for SQLAlchemy ORM models."""
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import Run


def setup_function(_):
    """Reset the schema per test for isolation (matches existing API-test pattern)."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_run_run_context_json_default_none():
    """A fresh Run row has run_context_json = None by default."""
    with Session(bind=engine) as db:
        db.add(Run(id="r_test", status="created"))
        db.commit()
        loaded = db.get(Run, "r_test")
        assert loaded is not None
        assert loaded.run_context_json is None


def test_run_run_context_json_roundtrips_text():
    """run_context_json stores arbitrary JSON string and round-trips."""
    payload = '{"user_context":"focus onboarding"}'
    with Session(bind=engine) as db:
        db.add(Run(id="r_test", status="created", run_context_json=payload))
        db.commit()
        loaded = db.get(Run, "r_test")
        assert loaded is not None
        assert loaded.run_context_json == payload
