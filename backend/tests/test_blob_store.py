from pathlib import Path

from app.blob_store import blob_path_for, load_blob, save_blob


def test_save_and_load_blob(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    path = save_blob("f_abc", "hello.pdf", b"binary-data")
    assert Path(path).exists()
    assert load_blob("f_abc", "hello.pdf") == b"binary-data"


def test_blob_path_includes_file_id(tmp_path, monkeypatch):
    monkeypatch.setattr("app.blob_store.BLOB_DIR", tmp_path)
    p = blob_path_for("f_xyz", "doc.txt")
    assert "f_xyz" in str(p)
    assert p.name == "doc.txt"
