"""Files service — upload + parse orchestration.

Owns the DB writes for `FileRecord` rows and the blob store side effects
during upload. `get_parsed` returns a cached ParsedFile keyed by
(file_id, blob_mtime_ns); re-parses only when the underlying blob changes.
Cache size is capped by settings.excerpt_cache_size (default 32).
"""
import uuid
from collections import OrderedDict
from pathlib import Path
from threading import Lock

from sqlalchemy.orm import Session

from app.blob_store import save_blob
from app.config import get_settings
from app.models import FileRecord
from app.parsers import parse as parse_file
from app.schemas import FileRef, ParsedFile
from app.structured_logging import get_logger


logger = get_logger(__name__)

_parse_cache: "OrderedDict[tuple[str, int], ParsedFile]" = OrderedDict()
_parse_cache_lock = Lock()
_parse_cache_stats = {"hits": 0, "misses": 0}


def clear_parse_cache() -> None:
    """Reset the in-process ParsedFile cache (used by tests + admin endpoints)."""
    with _parse_cache_lock:
        _parse_cache.clear()
        _parse_cache_stats["hits"] = 0
        _parse_cache_stats["misses"] = 0


def parse_cache_stats() -> dict[str, int]:
    """Return a snapshot of the cache hit/miss counters."""
    with _parse_cache_lock:
        return dict(_parse_cache_stats)


def _cache_get(key: tuple[str, int]) -> ParsedFile | None:
    """Return the cached ParsedFile for ``key`` and bump it to most-recently-used."""
    with _parse_cache_lock:
        if key in _parse_cache:
            _parse_cache.move_to_end(key)
            _parse_cache_stats["hits"] += 1
            return _parse_cache[key]
        _parse_cache_stats["misses"] += 1
        return None


def _cache_put(key: tuple[str, int], value: ParsedFile) -> None:
    """Insert ``value`` for ``key`` and evict LRU entries above the configured cap."""
    cap = max(1, get_settings().excerpt_cache_size)
    with _parse_cache_lock:
        _parse_cache[key] = value
        _parse_cache.move_to_end(key)
        while len(_parse_cache) > cap:
            _parse_cache.popitem(last=False)


def upload_file(db: Session, *, file_name: str, mime_type: str, content: bytes) -> FileRef:
    """Mint a file_id, persist bytes to the blob store, attempt to parse, and insert a FileRecord row."""
    file_id = f"f_{uuid.uuid4().hex[:12]}"
    logger.info(
        "file.upload.started",
        file_id=file_id,
        file_name=file_name,
        mime_type=mime_type,
        byte_count=len(content),
    )
    blob_path = save_blob(file_id, file_name, content)

    parser_status: str
    try:
        parsed = parse_file(file_id=file_id, file_name=file_name, path=Path(blob_path), mime_type=mime_type)
        parser_status = "ok"
        logger.info(
            "file.parse.completed",
            file_id=file_id,
            file_type=parsed.type,
            segment_count=len(parsed.segments),
        )
    except Exception as exc:
        parser_status = "error"
        logger.warning("file.parse.failed", file_id=file_id, error=str(exc), exc_info=True)

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
    logger.info("file.upload.completed", file_id=file_id, parser_status=parser_status, blob_path=blob_path)

    return FileRef(
        file_id=file_id,
        file_name=file_name,
        mime_type=mime_type,
        blob_path=blob_path,
        parser_status=parser_status,
    )


def get_parsed(db: Session, file_id: str) -> ParsedFile:
    """Return a cached ParsedFile; re-parse on cache miss or blob-mtime change."""
    rec = db.get(FileRecord, file_id)
    if rec is None:
        logger.warning("file.reparse.missing", file_id=file_id)
        raise ValueError(f"File {file_id} not found")
    mtime_ns = Path(rec.blob_path).stat().st_mtime_ns
    key = (file_id, mtime_ns)
    cached = _cache_get(key)
    if cached is not None:
        logger.info("file.reparse.cache_hit", file_id=file_id)
        return cached
    logger.info("file.reparse.started", file_id=file_id, file_name=rec.file_name, mime_type=rec.mime_type)
    parsed = parse_file(
        file_id=rec.id,
        file_name=rec.file_name,
        path=Path(rec.blob_path),
        mime_type=rec.mime_type,
    )
    _cache_put(key, parsed)
    logger.info(
        "file.reparse.completed",
        file_id=file_id,
        file_type=parsed.type,
        segment_count=len(parsed.segments),
    )
    return parsed
