"""ORM smoke tests for agent-output tables against real SQLite.

Covers FileSummaryRecord, IntakeBundleRecord, and BlueprintRecord; payloads are
stored as JSON-encoded strings.
"""
import json

from app.database import Base, SessionLocal, engine
from app.models import BlueprintRecord, FileSummaryRecord, IntakeBundleRecord, Run


def setup_module():
    """Reset the production SQLite schema once before any test in this module."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_persist_file_summary_record():
    """FileSummaryRecord round-trips its payload_json string."""
    with SessionLocal() as s:
        # Need a Run + File to satisfy FK constraints later; for this test of
        # FileSummaryRecord alone we use a file_id that exists in files table.
        # Skip FK constraint by inserting against SQLite (lenient) — if test
        # fails due to FK, add a parent File first.
        rec = FileSummaryRecord(file_id="f1", payload_json=json.dumps({"x": 1}))
        s.add(rec)
        s.commit()
        assert s.get(FileSummaryRecord, "f1").payload_json == '{"x": 1}'


def test_persist_intake_bundle_record():
    """IntakeBundleRecord persists when its parent Run row exists."""
    with SessionLocal() as s:
        # Need a Run row first to satisfy FK
        s.add(Run(id="r1", status="created"))
        s.commit()
        rec = IntakeBundleRecord(run_id="r1", payload_json="{}")
        s.add(rec)
        s.commit()
        assert s.get(IntakeBundleRecord, "r1") is not None


def test_persist_blueprint_record():
    """BlueprintRecord persists when its parent Run row exists."""
    with SessionLocal() as s:
        s.add(Run(id="r2", status="created"))
        s.commit()
        rec = BlueprintRecord(run_id="r2", payload_json="{}")
        s.add(rec)
        s.commit()
        assert s.get(BlueprintRecord, "r2") is not None
