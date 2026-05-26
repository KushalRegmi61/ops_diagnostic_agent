"""POST /api/files multipart uploads against the real DB + parsers + blob store."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, engine
from app.main import app


def setup_module():
    """Reset the production SQLite schema once before any test in this module."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_upload_pdf_returns_file_id_and_ok_status(tmp_path, monkeypatch):
    """Uploading a real PDF yields a file_id and parser_status=ok."""
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(app)
    fixture = Path(__file__).parent.parent / "fixtures" / "sop.pdf"
    with fixture.open("rb") as f:
        r = client.post(
            "/api/files",
            files={"file": ("sop.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["file_id"].startswith("f_")
    assert body["parser_status"] == "ok"


def test_upload_unknown_mime_returns_415(tmp_path, monkeypatch):
    """Uploading an unsupported mime is rejected at the HTTP boundary with 415."""
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(app)
    r = client.post(
        "/api/files",
        files={"file": ("thing.bin", b"\x00", "application/octet-stream")},
    )
    assert r.status_code == 415, r.text
