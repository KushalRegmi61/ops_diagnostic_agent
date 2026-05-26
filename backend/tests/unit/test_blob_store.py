"""Blob store: write then read round-trip and path layout."""
from pathlib import Path

import pytest

from app.blob_store import blob_path_for, load_blob, save_blob
from app.config import get_settings


def test_save_and_load_blob(tmp_path, monkeypatch):
    """save_blob writes bytes that load_blob can read back identically."""
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
    path = save_blob("f_abc", "hello.pdf", b"binary-data")
    assert Path(path).exists()
    assert load_blob("f_abc", "hello.pdf") == b"binary-data"


def test_blob_path_includes_file_id(tmp_path, monkeypatch):
    """Blob paths place each file under a directory named for its file_id."""
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
    p = blob_path_for("f_xyz", "doc.txt")
    assert "f_xyz" in str(p)
    assert p.name == "doc.txt"


def test_save_blob_rejects_path_traversal(monkeypatch, tmp_path) -> None:
    from app import blob_store
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="unsafe filename"):
        blob_store.save_blob("f_abc", "../../etc/x", b"payload")
    # Nothing should have been written above the blob dir.
    assert not (tmp_path.parent / "etc" / "x").exists()


def test_save_blob_strips_directory_components(monkeypatch, tmp_path) -> None:
    from app import blob_store
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="unsafe filename"):
        blob_store.save_blob("f_abc", "subdir/x.txt", b"payload")


def test_save_blob_accepts_clean_filename(monkeypatch, tmp_path) -> None:
    from app import blob_store
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
    path = blob_store.save_blob("f_abc", "report.pdf", b"payload")
    assert path.endswith("f_abc/report.pdf")
    assert (tmp_path / "f_abc" / "report.pdf").read_bytes() == b"payload"
