import json

from app.database import Base, SessionLocal, engine
from app.models import BlueprintRecord, FileSummaryRecord, IntakeBundleRecord, Run


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_persist_file_summary_record():
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
    with SessionLocal() as s:
        # Need a Run row first to satisfy FK
        s.add(Run(id="r1", status="created"))
        s.commit()
        rec = IntakeBundleRecord(run_id="r1", payload_json="{}")
        s.add(rec)
        s.commit()
        assert s.get(IntakeBundleRecord, "r1") is not None


def test_persist_blueprint_record():
    with SessionLocal() as s:
        s.add(Run(id="r2", status="created"))
        s.commit()
        rec = BlueprintRecord(run_id="r2", payload_json="{}")
        s.add(rec)
        s.commit()
        assert s.get(BlueprintRecord, "r2") is not None
