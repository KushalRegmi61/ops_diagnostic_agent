"""Excerpt endpoint returns 404 when DB row exists but blob is absent on disk."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def test_excerpt_returns_404_when_blob_is_missing_on_disk(tmp_path) -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/files",
        files={"file": ("notes.md", BytesIO(b"# A\nline\n"), "text/markdown")},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    file_id = body["file_id"]
    blob_path = body["blob_path"]

    Path(blob_path).unlink()

    r = client.post(
        f"/api/files/{file_id}/excerpt",
        json={"locator": {"type": "text", "line_start": 1, "line_end": 1}},
    )
    assert r.status_code == 404, r.text
    assert "not found" in r.text.lower() or "missing" in r.text.lower()
