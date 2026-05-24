"""FastAPI HTTP layer for the Ops Diagnostic Agent.

Exposes the public endpoints (/health, /api/files, /api/files/{id}/excerpt,
/api/runs, /api/runs/{id}, /api/runs/{id}/blueprint) and keeps handlers thin —
all DB writes, parsing, and graph invocation are delegated to `app.services.*`.
Sits at the top of the pipeline: HTTP -> services -> graph -> agents -> parsers.
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (register tables with Base.metadata)
from app.config import get_settings
from app.database import Base, engine, get_db
from app.parsers import csv as _p_csv
from app.parsers import docx as _p_docx
from app.parsers import json as _p_json
from app.parsers import mbox as _p_mbox
from app.parsers import md as _p_md
from app.parsers import pdf as _p_pdf
from app.parsers import srt as _p_srt
from app.parsers import txt as _p_txt
from app.parsers import vtt as _p_vtt
from app.parsers import xlsx as _p_xlsx
from app.models import Run
from app.schemas import Blueprint, FileRef
from app.services.files import get_parsed, upload_file
from app.services.runs import (
    FileNotFoundForRunError,
    RunNotFoundError,
    create_run,
    get_blueprint,
    start_run,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI lifespan: create DB tables on startup."""
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Ops Diagnostic Agent", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_EXCERPT_MODULES = {
    "pdf": _p_pdf,
    "docx": _p_docx,
    "md": _p_md,
    "txt": _p_txt,
    "transcript_vtt": _p_vtt,
    "transcript_srt": _p_srt,
    "csv": _p_csv,
    "xlsx": _p_xlsx,
    "mbox": _p_mbox,
    "json": _p_json,
}


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
    """Upload a single file: persists bytes to blob store, parses, and inserts a FileRecord row."""
    content = file.file.read()
    ref = upload_file(
        db,
        file_name=file.filename or "unknown",
        mime_type=file.content_type or "application/octet-stream",
        content=content,
    )
    db.commit()
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

    module = _EXCERPT_MODULES.get(parsed.type)
    if module is None:
        raise HTTPException(status_code=400, detail=f"no excerpt module for type {parsed.type}")
    try:
        text = module.excerpt(parsed, body.locator)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExcerptResponse(text=text)


class CreateRunRequest(BaseModel):
    """Request body for creating a diagnostic run from previously uploaded files."""

    file_ids: list[str]


class RunResponse(BaseModel):
    """Response describing a run's id, lifecycle status, and optional Langfuse trace id."""

    run_id: str
    status: str
    langfuse_trace_id: str | None = None


@app.post("/api/runs", response_model=RunResponse)
def post_run(body: CreateRunRequest, db: Session = Depends(get_db)) -> RunResponse:
    """Create a run, link files, and invoke the diagnostic graph synchronously."""
    if not body.file_ids:
        raise HTTPException(status_code=400, detail="file_ids must be non-empty")
    try:
        run_id = create_run(db, file_ids=body.file_ids)
    except FileNotFoundForRunError as e:
        raise HTTPException(status_code=404, detail=str(e))
    db.commit()

    try:
        start_run(db, run_id=run_id)
    except RunNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    db.commit()

    run = db.get(Run, run_id)
    assert run is not None
    return RunResponse(run_id=run_id, status=run.status, langfuse_trace_id=run.langfuse_trace_id)


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
