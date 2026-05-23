from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (register tables with Base.metadata)
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
from app.schemas import FileRef
from app.services.files import get_parsed, upload_file


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Ops Diagnostic Agent", version="0.1.0", lifespan=lifespan)


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
    locator: dict


class ExcerptResponse(BaseModel):
    text: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/files", response_model=FileRef)
def post_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> FileRef:
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
