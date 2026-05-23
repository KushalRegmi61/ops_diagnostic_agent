"""Files service — upload + parse orchestration.

Owns the DB writes for `FileRecord` rows and the blob store side effects
during upload. `get_parsed` re-parses a file from disk on demand so the
HTTP excerpt endpoint can round-trip citations without keeping ParsedFile
segments in memory between requests.
"""
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.blob_store import save_blob
from app.models import FileRecord
from app.parsers import parse as parse_file
from app.schemas import FileRef, ParsedFile


def upload_file(db: Session, *, file_name: str, mime_type: str, content: bytes) -> FileRef:
    """Mint a file_id, persist bytes to the blob store, attempt to parse, and insert a FileRecord row."""
    file_id = f"f_{uuid.uuid4().hex[:12]}"
    blob_path = save_blob(file_id, file_name, content)

    parser_status: str
    try:
        parse_file(file_id=file_id, file_name=file_name, path=Path(blob_path), mime_type=mime_type)
        parser_status = "ok"
    except Exception:
        parser_status = "error"

    record = FileRecord(
        id=file_id,
        run_id=None,
        file_name=file_name,
        mime_type=mime_type,
        blob_path=blob_path,
        parser_status=parser_status,
    )
    db.add(record)
    db.flush()

    return FileRef(
        file_id=file_id,
        file_name=file_name,
        mime_type=mime_type,
        blob_path=blob_path,
        parser_status=parser_status,
    )


def get_parsed(db: Session, file_id: str) -> ParsedFile:
    """Re-parse the stored bytes for a file_id and return the ParsedFile; raises ValueError if unknown."""
    rec = db.get(FileRecord, file_id)
    if rec is None:
        raise ValueError(f"File {file_id} not found")
    return parse_file(
        file_id=rec.id,
        file_name=rec.file_name,
        path=Path(rec.blob_path),
        mime_type=rec.mime_type,
    )
