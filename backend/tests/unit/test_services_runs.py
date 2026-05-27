"""Unit tests for create_run + get_blueprint (no LLM, no graph) and start_run RunContext reconstruction."""
import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, SessionLocal, engine
from app.models import BlueprintRecord, FileRecord, Run
from app.schemas import Blueprint, BlueprintClaim, RunContext, Source
from app.services.runs import (
    FileNotFoundForRunError,
    create_run,
    get_blueprint,
)


def setup_function(_):
    """Reset the shared test DB schema before each function-scoped test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def db():
    """Yield a session bound to a fresh in-memory SQLite schema."""
    _engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine)
    s = _SessionLocal()
    yield s
    s.close()


def _add_file(db, fid: str) -> None:
    """Insert a parsed-ok FileRecord with the given file_id."""
    db.add(FileRecord(
        id=fid, run_id=None, file_name=f"{fid}.md",
        mime_type="text/markdown", blob_path=f"/tmp/{fid}",
        parser_status="ok",
    ))
    db.flush()


def test_create_run_links_files(db):
    """create_run assigns the new run_id to every referenced FileRecord."""
    _add_file(db, "f1")
    _add_file(db, "f2")
    run_id = create_run(db, file_ids=["f1", "f2"])
    assert run_id.startswith("r_")
    assert db.get(FileRecord, "f1").run_id == run_id
    assert db.get(FileRecord, "f2").run_id == run_id


def test_create_run_rejects_unknown_file(db):
    """create_run raises FileNotFoundForRunError if any file_id is missing."""
    with pytest.raises(FileNotFoundForRunError):
        create_run(db, file_ids=["f_ghost"])


def test_get_blueprint_returns_none_when_missing(db):
    """get_blueprint returns None when no BlueprintRecord matches the run."""
    assert get_blueprint(db, run_id="r_nope") is None


def test_get_blueprint_round_trips(db):
    """Persisted Blueprint JSON round-trips back into a Pydantic Blueprint model."""
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


# ---------------------------------------------------------------------------
# start_run RunContext reconstruction tests
# ---------------------------------------------------------------------------


def test_start_run_reconstructs_run_context_from_db(tmp_path):
    """When Run.run_context_json is set, start_run passes a RunContext into build_graph."""
    from app.services.runs import start_run

    with SessionLocal() as db:
        db.add(Run(
            id="r_ctx1",
            status="queued",
            run_context_json='{"user_context":"focus onboarding"}',
        ))
        db.add(FileRecord(
            id="f_ctx1",
            run_id="r_ctx1",
            file_name="ignored.txt",
            mime_type="text/plain",
            blob_path=str(tmp_path / "missing.txt"),  # forces parser_status path skip
            parser_status="error",  # makes _load_files_and_parse skip parsing
        ))
        db.commit()

    captured: dict = {}

    def fake_build_graph(*, provider, parsed_files, run_context=None, **kwargs):
        captured["run_context"] = run_context
        captured["parsed_files"] = parsed_files

        class _FakeGraph:
            def invoke(self, state, config=None):
                return {**state, "file_summaries": {}}

        return _FakeGraph()

    with (
        patch("app.services.runs.build_graph", side_effect=fake_build_graph),
        patch("app.services.runs.build_checkpointer", return_value=None),
        patch("app.services.runs.get_provider") as gp,
    ):
        gp.return_value.name = "fake"
        with SessionLocal() as db:
            start_run(db, run_id="r_ctx1")

    assert isinstance(captured["run_context"], RunContext)
    assert captured["run_context"].user_context == "focus onboarding"


def test_start_run_passes_none_when_no_context_persisted(tmp_path):
    """When Run.run_context_json is NULL, start_run passes run_context=None into build_graph."""
    from app.services.runs import start_run

    with SessionLocal() as db:
        db.add(Run(id="r_ctx2", status="queued", run_context_json=None))
        db.add(FileRecord(
            id="f_ctx2",
            run_id="r_ctx2",
            file_name="ignored.txt",
            mime_type="text/plain",
            blob_path=str(tmp_path / "missing.txt"),
            parser_status="error",
        ))
        db.commit()

    captured: dict = {}

    def fake_build_graph(*, provider, parsed_files, run_context=None, **kwargs):
        captured["run_context"] = run_context

        class _FakeGraph:
            def invoke(self, state, config=None):
                return {**state, "file_summaries": {}}

        return _FakeGraph()

    with (
        patch("app.services.runs.build_graph", side_effect=fake_build_graph),
        patch("app.services.runs.build_checkpointer", return_value=None),
        patch("app.services.runs.get_provider") as gp,
    ):
        gp.return_value.name = "fake"
        with SessionLocal() as db:
            start_run(db, run_id="r_ctx2")

    assert captured["run_context"] is None
