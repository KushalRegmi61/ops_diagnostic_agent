"""Runs service.

Orchestrates:
  create_run    → row in `runs`, links files via run_id.
  start_run     → loads parsed files, builds the diagnostic graph with the Redis
                  checkpointer, invokes it, persists file_summaries / bundle /
                  blueprint as JSON rows.
  get_blueprint → reads the persisted Blueprint for a run.
"""
import json
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.checkpointer import build_checkpointer
from app.graph import build_graph, initial_state
from app.llm import get_provider
from app.models import BlueprintRecord, FileRecord, FileSummaryRecord, IntakeBundleRecord, Run
from app.parsers import parse as parse_file
from app.schemas import Blueprint, FileRef


class RunNotFoundError(Exception):
    pass


class FileNotFoundForRunError(Exception):
    pass


def create_run(db: Session, *, file_ids: list[str]) -> str:
    """Create a new run and link the given uploaded files to it.

    Raises FileNotFoundForRunError if any file_id is missing in the DB.
    """
    run_id = f"r_{uuid.uuid4().hex[:12]}"
    db.add(Run(id=run_id, status="created"))

    for fid in file_ids:
        rec = db.get(FileRecord, fid)
        if rec is None:
            raise FileNotFoundForRunError(f"file {fid} not in DB")
        rec.run_id = run_id
    db.flush()
    return run_id


def _load_files_and_parse(db: Session, run_id: str) -> tuple[list[FileRef], dict]:
    rows = db.query(FileRecord).filter(FileRecord.run_id == run_id).all()
    if not rows:
        raise RunNotFoundError(f"run {run_id} has no files")

    refs: list[FileRef] = []
    parsed: dict = {}
    for r in rows:
        refs.append(FileRef(
            file_id=r.id, file_name=r.file_name,
            mime_type=r.mime_type, blob_path=r.blob_path,
            parser_status=r.parser_status,  # type: ignore[arg-type]
        ))
        if r.parser_status != "ok":
            continue
        parsed[r.id] = parse_file(
            file_id=r.id, file_name=r.file_name,
            path=Path(r.blob_path), mime_type=r.mime_type,
        )
    return refs, parsed


def start_run(db: Session, *, run_id: str, redo_cap: int = 1, revision_cap: int = 1) -> Blueprint | None:
    """Invoke the diagnostic graph for an existing run and persist outputs.

    Returns the final Blueprint (or None if the chain produced no blueprint).
    """
    run = db.get(Run, run_id)
    if run is None:
        raise RunNotFoundError(f"run {run_id} not found")

    refs, parsed_files = _load_files_and_parse(db, run_id)
    run.status = "running"
    db.flush()

    get_provider.cache_clear()
    provider = get_provider()
    checkpointer = build_checkpointer()
    graph = build_graph(
        provider=provider, parsed_files=parsed_files,
        redo_cap=redo_cap, revision_cap=revision_cap,
        checkpointer=checkpointer,
    )

    config = {"configurable": {"thread_id": run_id}}
    final_state = graph.invoke(initial_state(run_id, refs), config=config)

    # Persist file summaries.
    for file_id, summary in (final_state.get("file_summaries") or {}).items():
        existing = db.get(FileSummaryRecord, file_id)
        payload = json.dumps(summary.model_dump())
        if existing:
            existing.payload_json = payload
        else:
            db.add(FileSummaryRecord(file_id=file_id, payload_json=payload))

    # Persist IntakeBundle.
    bundle = final_state.get("bundle")
    if bundle is not None:
        existing_b = db.get(IntakeBundleRecord, run_id)
        payload = json.dumps(bundle.model_dump())
        if existing_b:
            existing_b.payload_json = payload
        else:
            db.add(IntakeBundleRecord(run_id=run_id, payload_json=payload))

    # Persist Blueprint.
    blueprint = final_state.get("blueprint")
    if blueprint is not None:
        existing_bp = db.get(BlueprintRecord, run_id)
        payload = json.dumps(blueprint.model_dump())
        if existing_bp:
            existing_bp.payload_json = payload
        else:
            db.add(BlueprintRecord(run_id=run_id, payload_json=payload))

    run.status = "complete" if blueprint is not None else "no_blueprint"
    db.flush()
    return blueprint


def get_blueprint(db: Session, *, run_id: str) -> Blueprint | None:
    rec = db.get(BlueprintRecord, run_id)
    if rec is None:
        return None
    return Blueprint.model_validate_json(rec.payload_json)
