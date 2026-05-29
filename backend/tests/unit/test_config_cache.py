"""get_settings() caches a single Settings instance per process (CLAUDE.md contract)."""
import os

from app.config import get_settings


def test_get_settings_returns_same_instance_until_clear() -> None:
    a = get_settings()
    b = get_settings()
    assert a is b


def test_get_settings_reflects_env_after_cache_clear(monkeypatch, tmp_path) -> None:
    new_dir = tmp_path / "blobs2"
    new_dir.mkdir()
    monkeypatch.setenv("BLOB_STORE_DIR", str(new_dir))
    get_settings.cache_clear()
    s = get_settings()
    assert s.blob_store_dir == str(new_dir)


def test_per_file_concurrency_defaults_to_4():
    """per_file_concurrency caps parallel per-file branches; defaults to 4."""
    from app.config import Settings

    s = Settings(database_url="sqlite:///x.db", blob_store_dir="/tmp/blobs")
    assert s.per_file_concurrency == 4


def test_blob_dir_reflects_env_after_cache_clear(monkeypatch, tmp_path) -> None:
    """blob_store.blob_path_for must read Settings lazily, not at import time."""
    from app import blob_store
    new_dir = tmp_path / "blobs3"
    new_dir.mkdir()
    monkeypatch.setenv("BLOB_STORE_DIR", str(new_dir))
    get_settings.cache_clear()
    path = blob_store.blob_path_for("f_abc", "x.txt")
    assert str(path).startswith(str(new_dir))
