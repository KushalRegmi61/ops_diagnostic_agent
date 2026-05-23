"""ORM smoke tests for the Run and FileRecord tables against real SQLite."""
from datetime import datetime

from app.database import Base, SessionLocal, engine
from app.models import FileRecord, Run


def setup_module():
    """Reset the production SQLite schema once before any test in this module."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_insert_and_retrieve_run():
    """A Run row inserts cleanly and exposes a default created_at timestamp."""
    with SessionLocal() as s:
        run = Run(id="run_test_1", status="created")
        s.add(run)
        s.commit()
        loaded = s.get(Run, "run_test_1")
        assert loaded is not None
        assert loaded.status == "created"
        assert isinstance(loaded.created_at, datetime)


def test_insert_file_with_locator_metadata():
    """A FileRecord persists basic file-identity columns end-to-end."""
    with SessionLocal() as s:
        f = FileRecord(
            id="f_test_1",
            run_id=None,
            file_name="hello.pdf",
            mime_type="application/pdf",
            blob_path="/tmp/hello.pdf",
            parser_status="ok",
        )
        s.add(f)
        s.commit()
        loaded = s.get(FileRecord, "f_test_1")
        assert loaded.file_name == "hello.pdf"
