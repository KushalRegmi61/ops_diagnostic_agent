"""Run dispatch task lifecycle — held in a strong-ref set, marks run=error on uncaught."""
import time
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Run


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def test_module_holds_pending_run_tasks_set() -> None:
    """app.main._pending_run_tasks must exist and be a set[asyncio.Task]."""
    from app import main
    assert hasattr(main, "_pending_run_tasks"), (
        "main module must expose _pending_run_tasks so dispatch tasks are not GC'd"
    )
    assert isinstance(main._pending_run_tasks, set)


def test_dispatch_callback_marks_run_error_on_uncaught(monkeypatch) -> None:
    """When _start_run_dispatch raises above _start_run_sync's catch, run.status='error'."""
    from app import main as app_main

    async def _boom(run_id: str) -> None:
        raise RuntimeError("simulated dispatcher failure")

    monkeypatch.setattr(app_main, "_start_run_dispatch", _boom)

    client = TestClient(app)
    up = client.post(
        "/api/files",
        files={"file": ("a.md", BytesIO(b"# A\n"), "text/markdown")},
    )
    assert up.status_code == 200, up.text
    file_id = up.json()["file_id"]
    r = client.post("/api/runs", json={"file_ids": [file_id]})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    final_status = None
    for _ in range(80):
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run is not None and run.status == "error":
                final_status = run.status
                break
        time.sleep(0.05)
    assert final_status == "error", (
        f"expected run.status='error' after dispatcher failure; got {final_status!r}"
    )
