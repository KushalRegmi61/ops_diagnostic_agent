"""Bounded background-run concurrency via module-level asyncio Semaphore."""
import pytest

from app.config import get_settings
from app.database import Base, engine


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    monkeypatch.setenv("MAX_CONCURRENT_RUNS", "1")
    get_settings.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def test_max_concurrent_runs_setting_is_respected() -> None:
    assert get_settings().max_concurrent_runs == 1


def test_run_semaphore_is_sized_from_settings() -> None:
    """The dispatch semaphore exists and reflects the configured cap."""
    # Force a fresh build under the patched env.
    from app import main
    main._run_semaphore = None  # reset module-level cached semaphore
    sem = main._get_run_semaphore()
    assert sem is not None
    # asyncio.Semaphore exposes _value reflecting current permits.
    assert sem._value == 1
