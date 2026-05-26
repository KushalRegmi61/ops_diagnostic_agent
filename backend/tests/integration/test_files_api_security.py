"""Upload endpoint enforces size cap and MIME allowlist (parser registry)."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def _reset_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def test_upload_rejects_unknown_mime() -> None:
    client = TestClient(app)
    files = {"file": ("x.bin", BytesIO(b"abc"), "application/x-not-a-real-type")}
    r = client.post("/api/files", files=files)
    assert r.status_code == 415, r.text
    assert "unsupported" in r.text.lower()


def test_upload_rejects_oversize(monkeypatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    client = TestClient(app)
    big = b"\x00" * (2 * 1024 * 1024)  # 2 MB under 1 MB cap
    files = {"file": ("big.pdf", BytesIO(big), "application/pdf")}
    r = client.post("/api/files", files=files)
    assert r.status_code == 413, r.text
    assert "too large" in r.text.lower()


def test_upload_accepts_known_mime() -> None:
    client = TestClient(app)
    files = {"file": ("notes.md", BytesIO(b"# title\nline\n"), "text/markdown")}
    r = client.post("/api/files", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["parser_status"] == "ok"
