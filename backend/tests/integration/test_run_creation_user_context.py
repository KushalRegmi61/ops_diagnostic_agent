"""HTTP-level tests for user_context on the run-creation endpoint.

Uses the production SQLite engine + drop_all/create_all pattern per CLAUDE.md
(TestClient + dependency_overrides[get_db] is broken in this repo).
"""
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import FileRecord, Run


def setup_function(_):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _seed_file(file_id: str) -> None:
    """Insert a minimal parser-ok FileRecord so create_run links cleanly."""
    with SessionLocal() as db:
        db.add(FileRecord(
            id=file_id,
            run_id=None,
            file_name="seed.txt",
            mime_type="text/plain",
            blob_path="/dev/null",
            parser_status="ok",
        ))
        db.commit()


def test_create_run_persists_user_context():
    _seed_file("f_seed1")
    client = TestClient(app)
    resp = client.post(
        "/api/runs",
        json={"file_ids": ["f_seed1"], "user_context": "focus onboarding"},
    )
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.run_context_json is not None
        assert "focus onboarding" in run.run_context_json


def test_create_run_without_user_context_persists_none():
    _seed_file("f_seed2")
    client = TestClient(app)
    resp = client.post("/api/runs", json={"file_ids": ["f_seed2"]})
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run is not None
        assert run.run_context_json is None


def test_create_run_blank_user_context_persists_none():
    _seed_file("f_seed3")
    client = TestClient(app)
    resp = client.post(
        "/api/runs",
        json={"file_ids": ["f_seed3"], "user_context": "   "},
    )
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.run_context_json is None


def test_create_run_rejects_oversize_user_context():
    _seed_file("f_seed4")
    client = TestClient(app)
    resp = client.post(
        "/api/runs",
        json={"file_ids": ["f_seed4"], "user_context": "x" * 2001},
    )
    assert resp.status_code == 422
