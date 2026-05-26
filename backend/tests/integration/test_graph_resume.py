"""On worker restart, per_file_fanout must re-parse files missing from the closure.

Simulates the resumability scenario: build_graph is called with parsed_files={}
(fresh process) and a state carrying real FileRef rows whose blobs exist on disk.
The fanout node must NOT silently skip — it must re-parse and produce summaries.
Gated on Ollama because per-file agents call the real LLM.
"""
import httpx
import pytest

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.graph import build_graph, initial_state
from app.llm import get_provider
from app.schemas import FileRef
from app.services.files import upload_file


def _ollama_up() -> bool:
    try:
        return httpx.get("http://localhost:11434/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running")
def test_per_file_fanout_rehydrates_parsed_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BLOB_STORE_DIR", str(tmp_path / "blobs"))
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()
    get_provider.cache_clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        ref = upload_file(
            db,
            file_name="notes.md",
            mime_type="text/markdown",
            content=b"# Ops notes\nIngestion is manual\n",
        )
        db.commit()
        assert ref.parser_status == "ok"

        file_refs = [FileRef(
            file_id=ref.file_id, file_name=ref.file_name,
            mime_type=ref.mime_type, blob_path=ref.blob_path,
            parser_status="ok",
        )]

        # Empty parsed_files — simulates a fresh worker resuming from Redis.
        graph = build_graph(
            provider=get_provider(),
            parsed_files={},
            checkpointer=None,
        )
        final_state = graph.invoke(initial_state("r_test_resume", file_refs))
        summaries = final_state.get("file_summaries") or {}
        assert ref.file_id in summaries, (
            "per_file_fanout silently skipped the file instead of re-parsing on resume"
        )
    finally:
        db.close()
