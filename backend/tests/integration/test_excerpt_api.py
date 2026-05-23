"""POST /api/files/{id}/excerpt against the real DB + parsers + blob store.

Uploads a fixture file through the HTTP API, then round-trips a locator back to
its text via the excerpt endpoint. Touches SQLite + the on-disk blob directory.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


def setup_module():
    """Reset the production SQLite schema once before any test in this module."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_excerpt_returns_text_for_uploaded_file(tmp_path, monkeypatch):
    """Uploading a file then POSTing /excerpt returns the parser-resolved text."""
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)

    fixture = Path(__file__).parent.parent / "fixtures" / "notes.md"
    with fixture.open("rb") as f:
        upload = client.post(
            "/api/files",
            files={"file": ("notes.md", f, "text/markdown")},
        )
    file_id = upload.json()["file_id"]

    r = client.post(
        f"/api/files/{file_id}/excerpt",
        json={"locator": {"type": "text", "line_start": 1, "line_end": 1}},
    )
    assert r.status_code == 200
    assert "Producer Notes" in r.json()["text"]


def test_excerpt_returns_404_for_unknown_file(tmp_path, monkeypatch):
    """/excerpt for an unknown file_id returns 404."""
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)
    r = client.post(
        "/api/files/f_nope/excerpt",
        json={"locator": {"type": "text", "line_start": 1, "line_end": 1}},
    )
    assert r.status_code == 404
