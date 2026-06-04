"""Deterministic gate: corpus JSON files no longer trip the tiny_segments probe flag."""
from pathlib import Path

import pytest

from app.parsers.json import parse
from evals.structural import probe_structure

_CORPUS = Path(__file__).parent.parent.parent / "evals" / "corpus" / "files"
_JSON_FILES = ["crm_contacts.json", "pipeline_export.json"]


@pytest.mark.parametrize("name", _JSON_FILES)
def test_corpus_json_has_no_tiny_segments(name):
    """After parent-object grouping, the corpus JSON median segment is not tiny."""
    path = _CORPUS / name
    if not path.exists():
        pytest.skip(f"corpus file {name} missing")
    parsed = parse(file_id="f1", file_name=name, path=path)
    probe = probe_structure(parsed)
    assert "tiny_segments" not in probe.flags, (
        f"{name} still tiny: median={probe.seg_chars_median} flags={probe.flags}"
    )
