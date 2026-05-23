from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models import FileRecord
from app.services.files import upload_file


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_upload_file_persists_record_and_parses(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    fixture = Path(__file__).parent.parent / "fixtures" / "notes.md"
    content = fixture.read_bytes()

    with SessionLocal() as s:
        ref = upload_file(s, file_name="notes.md", mime_type="text/markdown", content=content)
        s.commit()

    assert ref.parser_status == "ok"
    with SessionLocal() as s:
        rec = s.get(FileRecord, ref.file_id)
        assert rec is not None
        assert rec.parser_status == "ok"
        assert rec.file_name == "notes.md"


def test_upload_file_marks_error_for_unknown_mime(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    with SessionLocal() as s:
        ref = upload_file(s, file_name="thing.bin", mime_type="application/octet-stream", content=b"\x00\x01")
        s.commit()
    assert ref.parser_status == "error"
