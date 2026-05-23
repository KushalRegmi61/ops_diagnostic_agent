from pathlib import Path

from app.config import get_settings

BLOB_DIR = Path(get_settings().blob_store_dir)


def blob_path_for(file_id: str, file_name: str) -> Path:
    return BLOB_DIR / file_id / file_name


def save_blob(file_id: str, file_name: str, content: bytes) -> str:
    path = blob_path_for(file_id, file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def load_blob(file_id: str, file_name: str) -> bytes:
    return blob_path_for(file_id, file_name).read_bytes()
