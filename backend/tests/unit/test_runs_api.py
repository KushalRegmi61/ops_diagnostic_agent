"""Unit tests for GET /api/runs/{id} and GET /api/runs/{id}/blueprint.

POST /api/runs that actually invokes the graph is covered by the end-to-end
integration test in Task 23.
"""
import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.main import app
from app.models import BlueprintRecord, Run
from app.schemas import Blueprint, BlueprintClaim, Source


def setup_function(_):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _session() -> Session:
    return Session(bind=engine)


def test_get_run_404_when_missing():
    r = TestClient(app).get("/api/runs/r_nope")
    assert r.status_code == 404


def test_get_run_returns_status():
    s = _session()
    s.add(Run(id="r_1", status="complete", langfuse_trace_id="r_1"))
    s.commit(); s.close()

    r = TestClient(app).get("/api/runs/r_1")
    assert r.status_code == 200
    assert r.json() == {"run_id": "r_1", "status": "complete", "langfuse_trace_id": "r_1"}


def test_get_blueprint_404_when_no_run():
    r = TestClient(app).get("/api/runs/r_nope/blueprint")
    assert r.status_code == 404


def test_get_blueprint_404_when_no_blueprint():
    s = _session()
    s.add(Run(id="r_2", status="no_blueprint"))
    s.commit(); s.close()

    r = TestClient(app).get("/api/runs/r_2/blueprint")
    assert r.status_code == 404
    assert "no blueprint" in r.json()["detail"]


def test_get_blueprint_returns_payload():
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    claim = BlueprintClaim(text="t", sources=[src])
    bp = Blueprint(opportunity_ref=0, summary=claim, steps=[claim],
                   required_systems=[claim], success_metrics=[claim], risks=[claim])

    s = _session()
    s.add(Run(id="r_3", status="complete"))
    s.add(BlueprintRecord(run_id="r_3", payload_json=json.dumps(bp.model_dump())))
    s.commit(); s.close()

    r = TestClient(app).get("/api/runs/r_3/blueprint")
    assert r.status_code == 200
    assert r.json()["summary"]["text"] == "t"


def test_post_run_rejects_empty_file_ids():
    r = TestClient(app).post("/api/runs", json={"file_ids": []})
    assert r.status_code == 400


def test_post_run_404_when_file_unknown():
    r = TestClient(app).post("/api/runs", json={"file_ids": ["f_ghost"]})
    assert r.status_code == 404
