"""FastAPI HTTP layer for the Ops Diagnostic Agent.

Exposes the public endpoints (/health, /api/files, /api/files/{id}/excerpt,
/api/runs, /api/runs/{id}, /api/runs/{id}/blueprint) and keeps handlers thin —
all DB writes, parsing, and graph invocation are delegated to `app.services.*`.
Sits at the top of the pipeline: HTTP -> services -> graph -> agents -> parsers.
"""
from contextlib import asynccontextmanager
import asyncio

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (register tables with Base.metadata)
from app.config import get_settings
from app.database import Base, SessionLocal, engine, get_db
from app.parsers import _MIME_ROUTES  # type: ignore[attr-defined]  # registry source of truth
from app.parsers import excerpt as parsers_excerpt
from app.models import Run
from app.run_events import run_event_hub
from app.schemas import Blueprint, FileRef
from app.services.files import get_parsed, upload_file
from app.services.runs import (
    FileNotFoundForRunError,
    RunNotFoundError,
    create_run,
    get_blueprint,
    start_run,
)
from app.structured_logging import clear_context, configure_logging, get_logger


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI lifespan: create DB tables on startup."""
    configure_logging()
    run_event_hub.bind_loop(asyncio.get_running_loop())
    logger.info("app.startup")
    Base.metadata.create_all(engine)
    yield
    logger.info("app.shutdown")


app = FastAPI(title="Ops Diagnostic Agent", version="0.1.0", lifespan=lifespan)
logger = get_logger(__name__)
_settings_for_cors = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings_for_cors.frontend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExcerptRequest(BaseModel):
    """Request body for the excerpt endpoint — carries a raw locator dict."""

    locator: dict


class ExcerptResponse(BaseModel):
    """Response body carrying the resolved excerpt text from a parser."""

    text: str


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — always returns {"status": "ok"}."""
    return {"status": "ok"}


@app.post("/api/files", response_model=FileRef)
def post_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> FileRef:
    """Upload a single file. Rejects unsupported mimes (415) and oversize bodies (413)."""
    clear_context()
    settings_now = get_settings()
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in _MIME_ROUTES:
        logger.warning("http.file_upload.rejected", reason="unsupported_mime", mime_type=mime_type)
        raise HTTPException(status_code=415, detail=f"unsupported mime_type={mime_type}")

    max_bytes = settings_now.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    chunk_size = 1024 * 1024
    while True:
        chunk = file.file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            logger.warning(
                "http.file_upload.rejected",
                reason="too_large",
                limit_mb=settings_now.max_upload_mb,
            )
            raise HTTPException(
                status_code=413,
                detail=f"file too large (limit {settings_now.max_upload_mb} MB)",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    logger.info(
        "http.file_upload.started",
        file_name=file.filename or "unknown",
        mime_type=mime_type,
        byte_count=len(content),
    )
    ref = upload_file(
        db,
        file_name=file.filename or "unknown",
        mime_type=mime_type,
        content=content,
    )
    db.commit()
    logger.info("http.file_upload.completed", file_id=ref.file_id, parser_status=ref.parser_status)
    return ref


@app.post("/api/files/{file_id}/excerpt", response_model=ExcerptResponse)
def post_excerpt(
    file_id: str,
    body: ExcerptRequest,
    db: Session = Depends(get_db),
) -> ExcerptResponse:
    """Resolve a Source locator back to its excerpt text — round-trips the citation invariant."""
    try:
        parsed = get_parsed(db, file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"file {file_id} not found")
    try:
        text = parsers_excerpt(parsed, body.locator)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExcerptResponse(text=text)


class CreateRunRequest(BaseModel):
    """Request body for creating a diagnostic run from previously uploaded files."""

    file_ids: list[str]
    user_context: str | None = Field(default=None, max_length=2000)


class RunResponse(BaseModel):
    """Response describing a run's id, lifecycle status, and optional Langfuse trace id."""

    run_id: str
    status: str
    langfuse_trace_id: str | None = None


def _run_event_emitter(run_id: str):
    """Build the callback passed down to services/graph for WebSocket progress."""

    def emit(*, type: str, message: str, stage: str, level: str = "info", data: dict | None = None) -> None:
        run_event_hub.publish(
            run_id,
            type=type,
            message=message,
            stage=stage,
            level=level,
            data=data,
        )

    return emit


_run_semaphore: asyncio.Semaphore | None = None
_pending_run_tasks: set[asyncio.Task] = set()


def _get_run_semaphore() -> asyncio.Semaphore:
    """Lazily build the module-level dispatch semaphore from current Settings."""
    global _run_semaphore
    if _run_semaphore is None:
        _run_semaphore = asyncio.Semaphore(get_settings().max_concurrent_runs)
    return _run_semaphore


def _run_task_done(task: asyncio.Task) -> None:
    """Discard the dispatch task from the pending set; mark run='error' on uncaught exception.

    _start_run_sync catches all exceptions raised inside start_run and writes
    run.status='error' itself. This callback is the safety net for exceptions
    that escape _start_run_dispatch's own body (semaphore acquire,
    asyncio.to_thread machinery, threadpool exhaustion) where _start_run_sync
    is never reached.
    """
    _pending_run_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is None:
        return
    run_id = task.get_name().removeprefix("run-dispatch-")
    logger.error("run.dispatch.failed", run_id=run_id, error=str(exc), exc_info=exc)
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is not None and run.status not in {"complete", "no_blueprint", "error"}:
            run.status = "error"
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _start_run_sync(run_id: str) -> None:
    """Sync body executed inside a worker thread (acquires no event loop)."""
    db = SessionLocal()
    emit = _run_event_emitter(run_id)
    try:
        emit(type="run_background_started", message="Background worker picked up the run", stage="queued")
        start_run(db, run_id=run_id, on_event=emit)
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(Run, run_id)
        if run is not None:
            run.status = "error"
            db.commit()
        logger.error("run.background.failed", run_id=run_id, error=str(exc), exc_info=True)
        emit(
            type="run_failed",
            message=f"Run failed: {exc}",
            stage="error",
            level="error",
            data={"error": str(exc)},
        )
    finally:
        db.close()


async def _start_run_dispatch(run_id: str) -> None:
    """Acquire the concurrency semaphore and run start_run in a worker thread."""
    sem = _get_run_semaphore()
    async with sem:
        await asyncio.to_thread(_start_run_sync, run_id)


@app.post("/api/runs", response_model=RunResponse)
async def post_run(
    body: CreateRunRequest,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Create a run, link files, and start the diagnostic graph in the background.

    Dispatches work via asyncio.create_task → _start_run_dispatch, which gates
    concurrent executions with a module-level Semaphore sized by max_concurrent_runs.
    Single-process scope only; multi-worker deployments need an external queue.
    """
    clear_context()
    logger.info("http.run_create.started", file_count=len(body.file_ids), file_ids=body.file_ids)
    if not body.file_ids:
        raise HTTPException(status_code=400, detail="file_ids must be non-empty")
    try:
        run_id = create_run(db, file_ids=body.file_ids, user_context=body.user_context)
    except FileNotFoundForRunError as e:
        logger.warning("http.run_create.file_missing", error=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    run = db.get(Run, run_id)
    assert run is not None
    run.status = "queued"
    db.commit()

    run_event_hub.publish(
        run_id,
        type="run_queued",
        message="Run queued. Connect to the event stream for live progress.",
        stage="queued",
        data={"file_count": len(body.file_ids), "file_ids": body.file_ids},
    )
    task = asyncio.create_task(
        _start_run_dispatch(run_id),
        name=f"run-dispatch-{run_id}",
    )
    _pending_run_tasks.add(task)
    task.add_done_callback(_run_task_done)
    logger.info("http.run_create.queued", run_id=run_id, status=run.status)
    return RunResponse(run_id=run_id, status=run.status, langfuse_trace_id=run.langfuse_trace_id)


@app.websocket("/api/runs/{run_id}/events")
async def run_events(websocket: WebSocket, run_id: str) -> None:
    """Stream replayed and live run progress events over WebSocket."""
    await websocket.accept()
    queue, history = run_event_hub.subscribe_with_history(run_id)
    logger.info("websocket.run_events.connected", run_id=run_id)
    try:
        for event in history:
            await websocket.send_json(event)
            if event["type"] in {"run_completed", "run_failed"}:
                await websocket.close()
                return

        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["type"] in {"run_completed", "run_failed"}:
                await websocket.close()
                return
    except WebSocketDisconnect:
        logger.info("websocket.run_events.disconnected", run_id=run_id)
    finally:
        run_event_hub.unsubscribe(run_id, queue)


@app.get("/api/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunResponse:
    """Return the current status of a run by id."""
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return RunResponse(run_id=run_id, status=run.status, langfuse_trace_id=run.langfuse_trace_id)


@app.get("/api/runs/{run_id}/blueprint", response_model=Blueprint)
def get_run_blueprint(run_id: str, db: Session = Depends(get_db)) -> Blueprint:
    """Fetch the persisted Blueprint for a completed run; 404 if not yet produced."""
    if db.get(Run, run_id) is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    bp = get_blueprint(db, run_id=run_id)
    if bp is None:
        raise HTTPException(status_code=404, detail="no blueprint for this run yet")
    return bp
