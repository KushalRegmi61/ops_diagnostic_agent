"""JSON parser: one segment per parent object, addressed by the parent JSON pointer."""
import json as _json
from pathlib import Path

import pytest

from app.parsers.json import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "crm.json"


def test_parse_groups_leaves_by_parent_object():
    """parse() emits one segment per object; /contacts/0 carries all its fields."""
    pf = parse(file_id="f1", file_name="crm.json", path=FIXTURE)
    assert pf.type == "json"
    pointers = [seg.locator["pointer"] for seg in pf.segments]
    assert "/contacts/0" in pointers
    assert "/contacts/1" in pointers
    # Two contact objects -> two segments (not one-per-leaf).
    assert len(pf.segments) == 2
    seg0 = next(s for s in pf.segments if s.locator["pointer"] == "/contacts/0")
    assert "name: Acme Corp" in seg0.text
    assert "stage: awaiting_docs" in seg0.text


def test_excerpt_returns_grouped_object_text():
    """excerpt() resolves a parent pointer to its grouped key:value block."""
    pf = parse(file_id="f1", file_name="crm.json", path=FIXTURE)
    text = excerpt(pf, {"type": "json", "pointer": "/contacts/0"})
    assert "name: Acme Corp" in text


def test_excerpt_unknown_pointer_raises():
    """excerpt() raises ValueError for a pointer no segment carries."""
    pf = parse(file_id="f1", file_name="crm.json", path=FIXTURE)
    with pytest.raises(ValueError):
        excerpt(pf, {"type": "json", "pointer": "/contacts/9"})


def test_dict_root_groups_under_empty_pointer(tmp_path):
    """A flat dict root groups its scalar fields into one segment at pointer ''."""
    p = tmp_path / "d.json"
    p.write_text(_json.dumps({"a": 1, "b": 2}))
    pf = parse(file_id="f1", file_name="d.json", path=p)
    assert len(pf.segments) == 1
    assert pf.segments[0].locator["pointer"] == ""
    assert "a: 1" in pf.segments[0].text
    assert "b: 2" in pf.segments[0].text


def test_scalar_array_groups_under_array_pointer(tmp_path):
    """A scalar array groups its elements into one segment at the array pointer."""
    p = tmp_path / "s.json"
    p.write_text(_json.dumps({"tags": ["x", "y"]}))
    pf = parse(file_id="f1", file_name="s.json", path=p)
    seg = next(s for s in pf.segments if s.locator["pointer"] == "/tags")
    assert "0: x" in seg.text
    assert "1: y" in seg.text


def test_nested_object_segment_uses_immediate_parent(tmp_path):
    """Deeply nested leaves group under their immediate parent, not the root."""
    p = tmp_path / "n.json"
    p.write_text(_json.dumps({"a": {"b": {"c": 1, "d": 2}}}))
    pf = parse(file_id="f1", file_name="n.json", path=p)
    assert len(pf.segments) == 1
    seg = pf.segments[0]
    assert seg.locator["pointer"] == "/a/b"
    assert "c: 1" in seg.text
    assert "d: 2" in seg.text


def test_every_segment_round_trips(tmp_path):
    """Citation invariant: every emitted segment's pointer resolves to its text."""
    p = tmp_path / "r.json"
    p.write_text(_json.dumps({"contacts": [{"name": "Z"}], "tags": ["t"]}))
    pf = parse(file_id="f1", file_name="r.json", path=p)
    for seg in pf.segments:
        assert excerpt(pf, seg.locator) == seg.text
