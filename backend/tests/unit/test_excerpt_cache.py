"""get_parsed caches ParsedFile by (file_id, blob_mtime); invalidates on mtime change."""
import os
import time
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.services import files as files_service
from app.services.files import get_parsed, upload_file


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    files_service.clear_parse_cache()
    yield


def test_get_parsed_hits_cache_on_second_call() -> None:
    db: Session = SessionLocal()
    try:
        ref = upload_file(
            db, file_name="notes.md", mime_type="text/markdown",
            content=b"# A\nline\n",
        )
        db.commit()
        files_service.clear_parse_cache()
        first = get_parsed(db, ref.file_id)
        hits_before = files_service.parse_cache_stats()["hits"]
        second = get_parsed(db, ref.file_id)
        hits_after = files_service.parse_cache_stats()["hits"]
        assert second is first, "cache should return the same ParsedFile object"
        assert hits_after == hits_before + 1
    finally:
        db.close()


def test_get_parsed_invalidates_when_blob_mtime_changes() -> None:
    db: Session = SessionLocal()
    try:
        ref = upload_file(
            db, file_name="notes.md", mime_type="text/markdown",
            content=b"# A\nold line\n",
        )
        db.commit()
        first = get_parsed(db, ref.file_id)
        # Mutate blob in place and bump mtime to ensure detection.
        p = Path(ref.blob_path)
        p.write_bytes(b"# A\nnew line\n")
        future = time.time() + 1
        os.utime(p, (future, future))
        second = get_parsed(db, ref.file_id)
        assert second is not first, "mtime change must invalidate the cache entry"
    finally:
        db.close()
