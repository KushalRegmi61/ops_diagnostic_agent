"""Payload tables cascade-delete with their parent; created_at is tz-aware."""
from datetime import timezone

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import BlueprintRecord, IntakeBundleRecord, Run


def setup_function(_function) -> None:
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_run_created_at_is_timezone_aware() -> None:
    db = SessionLocal()
    try:
        run = Run(id="r_tz_check")
        db.add(run)
        db.commit()
        fetched = db.get(Run, "r_tz_check")
        assert fetched is not None
        assert fetched.created_at.tzinfo is not None, "created_at must be tz-aware"
        # UTC offset is zero.
        assert fetched.created_at.utcoffset() == timezone.utc.utcoffset(None), \
            "created_at must be UTC"
    finally:
        db.close()


def test_deleting_run_cascades_to_blueprint_and_bundle() -> None:
    db = SessionLocal()
    try:
        run = Run(id="r_cascade")
        db.add(run)
        db.flush()
        db.add(IntakeBundleRecord(run_id="r_cascade", payload_json="{}"))
        db.add(BlueprintRecord(run_id="r_cascade", payload_json="{}"))
        db.commit()

        db.delete(db.get(Run, "r_cascade"))
        db.commit()

        assert db.get(IntakeBundleRecord, "r_cascade") is None
        assert db.get(BlueprintRecord, "r_cascade") is None
    finally:
        db.close()
