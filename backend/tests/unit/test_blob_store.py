"""Blob store: write then read round-trip and path layout."""
from pathlib import Path

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
