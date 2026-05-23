"""On-disk blob store for uploaded files.

Files land under `BLOB_DIR/<file_id>/<file_name>` keyed by the generated
file_id. Used by `app.services.files.upload_file` on intake and by parsers
when re-reading bytes for excerpt round-trips.
"""
from pathlib import Path

from app.config import get_settings

BLOB_DIR = Path(get_settings().blob_store_dir)


def blob_path_for(file_id: str, file_name: str) -> Path:
    """Return the on-disk path where this file's bytes live (no I/O)."""
    return BLOB_DIR / file_id / file_name


def save_blob(file_id: str, file_name: str, content: bytes) -> str:
    """Write bytes to the blob store, creating parent dirs; returns the path as a string."""
    path = blob_path_for(file_id, file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def load_blob(file_id: str, file_name: str) -> bytes:
    """Read the raw bytes for a previously stored file."""
    return blob_path_for(file_id, file_name).read_bytes()
