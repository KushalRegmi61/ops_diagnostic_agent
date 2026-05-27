"""Runs service.

Orchestrates:
  create_run    → row in `runs`, links files via run_id.
  start_run     → loads parsed files, builds the diagnostic graph with the Redis
                  checkpointer, invokes it, persists file_summaries / bundle /
                  blueprint as JSON rows.
  get_blueprint → reads the persisted Blueprint for a run.
"""
import json
import time
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.checkpointer import build_checkpointer
from app.graph import build_graph, initial_state
from app.llm import get_provider
from app.models import BlueprintRecord, FileRecord, FileSummaryRecord, IntakeBundleRecord, Run
from app.observability import trace_run
from app.parsers import parse as parse_file
from app.schemas import Blueprint, FileRef, RunContext
from app.structured_logging import bind_context, clear_context, get_logger


logger = get_logger(__name__)


class RunNotFoundError(Exception):
    """Raised when a run_id has no row in `runs` or no associated files."""

    pass


class FileNotFoundForRunError(Exception):
    """Raised when a file_id supplied to create_run does not exist in `files`."""

    pass


def create_run(db: Session, *, file_ids: list[str], user_context: str | None = None) -> str:
    """Create a new run and link the given uploaded files to it.

    ``user_context`` is normalized: blank/whitespace becomes None, populated values
    are persisted as the JSON dump of a RunContext model.

    Raises FileNotFoundForRunError if any file_id is missing in the DB.
    """
    from app.schemas import RunContext  # local import to avoid widening top-level imports

    run_id = f"r_{uuid.uuid4().hex[:12]}"
    logger.info(
        "run.create.started",
        run_id=run_id,
        file_count=len(file_ids),
        file_ids=file_ids,
        user_context_chars=len(user_context) if user_context else 0,
    )
    ctx = RunContext(user_context=user_context) if user_context else None
    ctx_json = ctx.model_dump_json() if ctx and ctx.has_steering() else None
    db.add(Run(id=run_id, status="created", run_context_json=ctx_json))

    for fid in file_ids:
        rec = db.get(FileRecord, fid)
        if rec is None:
            logger.warning("run.create.file_missing", run_id=run_id, file_id=fid)
            raise FileNotFoundForRunError(f"file {fid} not in DB")
        rec.run_id = run_id
    db.flush()
    logger.info("run.create.completed", run_id=run_id, has_steering=ctx_json is not None)
    return run_id


def _emit(on_event, type: str, message: str, stage: str, level: str = "info", **data) -> None:
    """Best-effort progress callback used by WebSocket streaming."""
    if on_event is not None:
        on_event(type=type, message=message, stage=stage, level=level, data=data)


def _load_files_and_parse(db: Session, run_id: str, on_event=None) -> tuple[list[FileRef], dict]:
    """Load FileRecord rows for a run and re-parse those whose upload-time parse succeeded."""
    logger.info("run.files.load.started", run_id=run_id)
    _emit(on_event, "run_files_load_started", "Loading files for this run", "load_files")
    rows = db.query(FileRecord).filter(FileRecord.run_id == run_id).all()
    if not rows:
        logger.warning("run.files.load.empty", run_id=run_id)
        _emit(on_event, "run_files_load_empty", "No files are linked to this run", "load_files", "warning")
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
            logger.warning(
                "run.file.parse.skipped",
                run_id=run_id,
                file_id=r.id,
                parser_status=r.parser_status,
            )
            _emit(
                on_event,
                "run_file_parse_skipped",
                f"Skipped {r.file_name}: parser status is {r.parser_status}",
                "parse",
                "warning",
                file_id=r.id,
                file_name=r.file_name,
                parser_status=r.parser_status,
            )
            continue
        started = time.perf_counter()
        logger.info("run.file.parse.started", run_id=run_id, file_id=r.id, file_name=r.file_name)
        _emit(
            on_event,
            "run_file_parse_started",
            f"Parsing {r.file_name}",
            "parse",
            file_id=r.id,
            file_name=r.file_name,
        )
        parsed[r.id] = parse_file(
            file_id=r.id, file_name=r.file_name,
            path=Path(r.blob_path), mime_type=r.mime_type,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "run.file.parse.completed",
            run_id=run_id,
            file_id=r.id,
            file_type=parsed[r.id].type,
            segment_count=len(parsed[r.id].segments),
            elapsed_ms=elapsed_ms,
        )
        _emit(
            on_event,
            "run_file_parse_completed",
            f"Parsed {r.file_name}",
            "parse",
            file_id=r.id,
            file_name=r.file_name,
            file_type=parsed[r.id].type,
            segment_count=len(parsed[r.id].segments),
            elapsed_ms=elapsed_ms,
        )
    logger.info(
        "run.files.load.completed",
        run_id=run_id,
        file_count=len(refs),
        parsed_count=len(parsed),
    )
    _emit(
        on_event,
        "run_files_load_completed",
        f"Loaded {len(refs)} files; {len(parsed)} ready for agents",
        "load_files",
        file_count=len(refs),
        parsed_count=len(parsed),
    )
    return refs, parsed


def start_run(
    db: Session,
    *,
    run_id: str,
    redo_cap: int = 1,
    revision_cap: int = 1,
    on_event=None,
) -> Blueprint | None:
    """Invoke the diagnostic graph for an existing run and persist outputs.

    Reconstructs RunContext from Run.run_context_json if present, threads it
    into build_graph and initial_state, and persists file_summaries / bundle /
    blueprint as JSON rows.

    Returns the final Blueprint (or None if the chain produced no blueprint).
    """
    clear_context()
    bind_context(run_id=run_id)
    started = time.perf_counter()
    run = db.get(Run, run_id)
    if run is None:
        logger.warning("run.start.missing")
        _emit(on_event, "run_missing", "Run was not found", "start", "warning")
        raise RunNotFoundError(f"run {run_id} not found")

    run_context: RunContext | None = None
    if run.run_context_json:
        try:
            run_context = RunContext.model_validate_json(run.run_context_json)
        except Exception as exc:
            logger.warning(
                "run.context.parse_failed",
                run_id=run_id,
                error=str(exc),
            )
            run_context = None

    logger.info(
        "run.start.started",
        redo_cap=redo_cap,
        revision_cap=revision_cap,
        user_context_chars=len(run_context.user_context) if run_context and run_context.user_context else 0,
        has_steering=run_context.has_steering() if run_context else False,
    )
    _emit(on_event, "run_started", "Diagnostic run started", "start", redo_cap=redo_cap, revision_cap=revision_cap)

    refs, parsed_files = _load_files_and_parse(db, run_id, on_event=on_event)
    run.status = "running"
    # Commit (not just flush) so Postgres releases the implicit transaction
    # before we burn minutes inside graph.invoke(). Neon — and managed Postgres
    # in general — kills idle-in-transaction connections (~5 min); holding the
    # tx across LLM-bound work made post-graph persistence reliably fail.
    db.commit()
    logger.info("run.status.updated", status=run.status)
    _emit(on_event, "run_status_updated", "Run is now active", "start", status=run.status)

    provider = get_provider()
    logger.info("run.provider.ready", provider=getattr(provider, "name", type(provider).__name__))
    _emit(
        on_event,
        "run_provider_ready",
        f"LLM provider ready: {getattr(provider, 'name', type(provider).__name__)}",
        "provider",
        provider=getattr(provider, "name", type(provider).__name__),
    )
    checkpointer = build_checkpointer()
    logger.info("run.checkpointer.ready", checkpointer=type(checkpointer).__name__ if checkpointer else None)
    graph = build_graph(
        provider=provider, parsed_files=parsed_files,
        run_context=run_context,
        redo_cap=redo_cap, revision_cap=revision_cap,
        checkpointer=checkpointer,
        on_event=on_event,
    )

    config = {"configurable": {"thread_id": run_id}}
    with trace_run(run_id) as trace:
        if trace is not None:
            run.langfuse_trace_id = run_id
            logger.info("run.trace.created", langfuse_trace_id=run_id)
        logger.info("run.graph.invoke.started", thread_id=run_id)
        _emit(on_event, "run_graph_started", "Agent graph started", "graph")
        final_state = graph.invoke(initial_state(run_id, refs, run_context=run_context), config=config)
        logger.info(
            "run.graph.invoke.completed",
            file_summary_count=len(final_state.get("file_summaries") or {}),
            redo_count=final_state.get("redo_count", 0),
            revision_count=final_state.get("revision_count", 0),
            has_bundle=final_state.get("bundle") is not None,
            has_blueprint=final_state.get("blueprint") is not None,
        )
        _emit(
            on_event,
            "run_graph_completed",
            "Agent graph completed",
            "graph",
            file_summary_count=len(final_state.get("file_summaries") or {}),
            redo_count=final_state.get("redo_count", 0),
            revision_count=final_state.get("revision_count", 0),
            has_blueprint=final_state.get("blueprint") is not None,
        )

    errors = final_state.get("errors") or []
    if errors:
        logger.warning(
            "run.errors.summary",
            error_count=len(errors),
            stages=sorted({e.stage for e in errors}),
        )
        _emit(
            on_event,
            "run_errors_summary",
            f"{len(errors)} structured error(s) recorded",
            "complete",
            "warning",
            error_count=len(errors),
            stages=sorted({e.stage for e in errors}),
        )

    # Persist file summaries.
    file_summary_count = 0
    for file_id, summary in (final_state.get("file_summaries") or {}).items():
        existing = db.get(FileSummaryRecord, file_id)
        payload = json.dumps(summary.model_dump())
        if existing:
            existing.payload_json = payload
        else:
            db.add(FileSummaryRecord(file_id=file_id, payload_json=payload))
        file_summary_count += 1
    logger.info("run.persist.file_summaries.completed", count=file_summary_count)
    _emit(
        on_event,
        "run_file_summaries_persisted",
        f"Stored {file_summary_count} file summaries",
        "persist",
        count=file_summary_count,
    )

    # Persist IntakeBundle.
    bundle = final_state.get("bundle")
    if bundle is not None:
        existing_b = db.get(IntakeBundleRecord, run_id)
        payload = json.dumps(bundle.model_dump())
        if existing_b:
            existing_b.payload_json = payload
        else:
            db.add(IntakeBundleRecord(run_id=run_id, payload_json=payload))
        logger.info(
            "run.persist.bundle.completed",
            workflow_count=len(bundle.workflows),
            pain_signal_count=len(bundle.pain_signals),
            lead_row_count=len(bundle.lead_rows),
        )
        _emit(
            on_event,
            "run_bundle_persisted",
            "Stored intake bundle",
            "persist",
            workflow_count=len(bundle.workflows),
            pain_signal_count=len(bundle.pain_signals),
            lead_row_count=len(bundle.lead_rows),
        )
    else:
        logger.warning("run.persist.bundle.skipped")
        _emit(on_event, "run_bundle_skipped", "No intake bundle was produced", "persist", "warning")

    # Persist Blueprint.
    blueprint = final_state.get("blueprint")
    if blueprint is not None:
        existing_bp = db.get(BlueprintRecord, run_id)
        payload = json.dumps(blueprint.model_dump())
        if existing_bp:
            existing_bp.payload_json = payload
        else:
            db.add(BlueprintRecord(run_id=run_id, payload_json=payload))
        logger.info("run.persist.blueprint.completed", step_count=len(blueprint.steps))
        _emit(
            on_event,
            "run_blueprint_persisted",
            "Stored final blueprint",
            "persist",
            step_count=len(blueprint.steps),
        )
    else:
        logger.warning("run.persist.blueprint.skipped")
        _emit(on_event, "run_blueprint_skipped", "No blueprint was produced", "persist", "warning")

    run.status = "complete" if blueprint is not None else "no_blueprint"
    db.flush()
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    logger.info("run.start.completed", status=run.status, elapsed_ms=elapsed_ms)
    _emit(
        on_event,
        "run_completed",
        f"Run finished with status {run.status}",
        "complete",
        status=run.status,
        elapsed_ms=elapsed_ms,
    )
    return blueprint


def get_blueprint(db: Session, *, run_id: str) -> Blueprint | None:
    """Return the persisted Blueprint for a run, or None if none was produced."""
    logger.info("run.blueprint.get.started", run_id=run_id)
    rec = db.get(BlueprintRecord, run_id)
    if rec is None:
        logger.warning("run.blueprint.get.missing", run_id=run_id)
        return None
    blueprint = Blueprint.model_validate_json(rec.payload_json)
    logger.info("run.blueprint.get.completed", run_id=run_id, step_count=len(blueprint.steps))
    return blueprint
