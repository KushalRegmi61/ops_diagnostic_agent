"""Corpus builder produces one input per manifest case, across parser families."""
import json
from pathlib import Path

from evals.corpus import build_corpus


def test_build_corpus_is_idempotent_and_covers_all_families():
    build_corpus.main()
    root = Path(build_corpus.__file__).parent
    manifest = json.loads((root / "manifest.json").read_text())

    # Every manifest case points at a file that exists on disk.
    for case in manifest:
        assert (root / "files" / case["file"]).exists(), case["file"]

    # Every parser family is represented at least once.
    families = {case["type"] for case in manifest}
    assert {"pdf", "docx", "md", "txt", "vtt", "srt", "csv", "xlsx", "mbox", "json"} <= families

    # Re-running is idempotent (no exception, same file count).
    before = sorted(p.name for p in (root / "files").iterdir())
    build_corpus.main()
    after = sorted(p.name for p in (root / "files").iterdir())
    assert before == after
