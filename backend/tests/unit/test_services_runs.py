"""Unit tests for create_run + get_blueprint (no LLM, no graph)."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import BlueprintRecord, FileRecord
from app.schemas import Blueprint, BlueprintClaim, Source
from app.services.runs import (
    FileNotFoundForRunError,
    create_run,
    get_blueprint,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def _add_file(db, fid: str) -> None:
    db.add(FileRecord(
        id=fid, run_id=None, file_name=f"{fid}.md",
        mime_type="text/markdown", blob_path=f"/tmp/{fid}",
        parser_status="ok",
    ))
    db.flush()


def test_create_run_links_files(db):
    _add_file(db, "f1")
    _add_file(db, "f2")
    run_id = create_run(db, file_ids=["f1", "f2"])
    assert run_id.startswith("r_")
    assert db.get(FileRecord, "f1").run_id == run_id
    assert db.get(FileRecord, "f2").run_id == run_id


def test_create_run_rejects_unknown_file(db):
    with pytest.raises(FileNotFoundForRunError):
        create_run(db, file_ids=["f_ghost"])


def test_get_blueprint_returns_none_when_missing(db):
    assert get_blueprint(db, run_id="r_nope") is None


def test_get_blueprint_round_trips(db):
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    claim = BlueprintClaim(text="t", sources=[src])
    bp = Blueprint(
        opportunity_ref=0, summary=claim, steps=[claim],
        required_systems=[claim], success_metrics=[claim], risks=[claim],
    )
    db.add(BlueprintRecord(run_id="r_x", payload_json=json.dumps(bp.model_dump())))
    db.flush()

    loaded = get_blueprint(db, run_id="r_x")
    assert loaded is not None
    assert loaded.summary.text == "t"
    assert loaded.summary.sources[0].file_id == "f1"
