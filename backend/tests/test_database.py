from sqlalchemy import text

from app.database import SessionLocal, engine


def test_engine_connects():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_factory_yields_session():
    with SessionLocal() as session:
        assert session.is_active
