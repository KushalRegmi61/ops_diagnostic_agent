"""JSON parser: leaf-level segments addressed by JSON Pointer locators."""
from pathlib import Path

from app.parsers.json import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "crm.json"


def test_parse_json_emits_leaf_segments_with_pointers():
    """parse() emits one segment per JSON leaf, each with a /-prefixed pointer."""
    pf = parse(file_id="f1", file_name="crm.json", path=FIXTURE)
    assert pf.type == "json"
    pointers = [seg.locator["pointer"] for seg in pf.segments]
    assert any(p.startswith("/contacts/0") for p in pointers)
    assert any("name" in p for p in pointers)


def test_excerpt_returns_leaf_value():
    """excerpt() returns the stringified leaf value addressed by a JSON pointer."""
    pf = parse(file_id="f1", file_name="crm.json", path=FIXTURE)
    text = excerpt(pf, {"type": "json", "pointer": "/contacts/0/name"})
    assert text == "Acme Corp"
