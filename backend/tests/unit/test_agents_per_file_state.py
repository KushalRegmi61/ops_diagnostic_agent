"""WorkingState default initialization for the per-file ReAct loop."""
from app.agents.per_file._state import WorkingState


def test_working_state_initializes_empty():
    """A fresh WorkingState has empty lists/notes and iteration count zero."""
    ws = WorkingState(file_id="f1", file_name="x.pdf")
    assert ws.file_id == "f1"
    assert ws.workflows == []
    assert ws.pain_signals == []
    assert ws.lead_rows == []
    assert ws.open_questions == []
    assert ws.notes == ""
    assert ws.iteration == 0
