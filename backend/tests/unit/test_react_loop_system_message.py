"""Unit test: the per-file system message makes cite_locator optional under #2c."""
from app.agents.per_file._react_loop import _initial_messages
from app.agents.per_file._state import WorkingState
from app.schemas import ParsedFile, ParsedSegment


def _parsed() -> ParsedFile:
    """A minimal txt ParsedFile for building initial messages."""
    return ParsedFile(
        file_id="f1", file_name="a.txt", type="txt",
        segments=[ParsedSegment(text="x", locator={"type": "text", "line_start": 1, "line_end": 1})],
    )


def test_system_message_makes_cite_optional():
    """The old 'Call cite_locator before…' mandate is gone; extract is the commit path."""
    msgs = _initial_messages(brief="BRIEF", prompt_suffix="", parsed=_parsed(), ws=WorkingState(file_id="f1", file_name="a.txt"))
    system = msgs[0].content
    assert "Call cite_locator before using a locator as a source" not in system
    assert "validate locators automatically" in system
    assert "cite_locator is available" in system
