"""On-disk blob store for uploaded files.

Files land under ``<blob_store_dir>/<file_id>/<file_name>`` keyed by the
generated file_id. Settings are read lazily so test isolation works without
monkey-patching this module.
"""
from pathlib import Path

from app.config import get_settings


def _blob_dir() -> Path:
    """Resolve the configured blob root at call time, not at import time."""
    return Path(get_settings().blob_store_dir)


def _sanitize_filename(file_name: str) -> str:
    """Reject filenames with directory components, NUL bytes, or non-printable chars.

    Raises ValueError on anything suspicious so the caller fails loudly at the
    HTTP boundary instead of writing outside the blob root.
    """
    if not file_name or file_name in {".", ".."}:
        raise ValueError(f"unsafe filename: {file_name!r}")
    if "\x00" in file_name:
        raise ValueError("unsafe filename: NUL byte present")
    if "/" in file_name or "\\" in file_name:
        raise ValueError(f"unsafe filename: directory separator in {file_name!r}")
    bare = Path(file_name).name
    if bare != file_name:
        raise ValueError(f"unsafe filename: {file_name!r}")
    return bare


def blob_path_for(file_id: str, file_name: str) -> Path:
    """Return the on-disk path where this file's bytes live (no I/O)."""
    return _blob_dir() / file_id / file_name


def save_blob(file_id: str, file_name: str, content: bytes) -> str:
    """Write bytes to the blob store; raises ValueError if ``file_name`` is unsafe."""
    safe_name = _sanitize_filename(file_name)
    path = blob_path_for(file_id, safe_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def load_blob(file_id: str, file_name: str) -> bytes:
    """Read the raw bytes for a previously stored file."""
    return blob_path_for(file_id, file_name).read_bytes()
