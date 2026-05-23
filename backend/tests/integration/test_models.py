from datetime import datetime

from app.database import Base, SessionLocal, engine
from app.models import FileRecord, Run


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_insert_and_retrieve_run():
    with SessionLocal() as s:
        run = Run(id="run_test_1", status="created")
        s.add(run)
        s.commit()
        loaded = s.get(Run, "run_test_1")
        assert loaded is not None
        assert loaded.status == "created"
        assert isinstance(loaded.created_at, datetime)


def test_insert_file_with_locator_metadata():
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
