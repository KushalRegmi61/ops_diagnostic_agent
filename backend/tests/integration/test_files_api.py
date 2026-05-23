from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_upload_pdf_returns_file_id_and_ok_status(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
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


def test_upload_unknown_mime_marks_error(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    client = TestClient(app)
    r = client.post(
        "/api/files",
        files={"file": ("thing.bin", b"\x00", "application/octet-stream")},
    )
    assert r.status_code == 200
    assert r.json()["parser_status"] == "error"
