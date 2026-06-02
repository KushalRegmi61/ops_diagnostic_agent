"""WorkingState carries the latest AgentTurn and an append-only turn log."""
from app.agents.per_file._state import WorkingState
from app.schemas import AgentTurn


def test_working_state_defaults_turn_fields():
    ws = WorkingState(file_id="f1", file_name="n.md")
    assert ws.last_turn is None
    assert ws.turn_log == []


def test_working_state_records_turns():
    ws = WorkingState(file_id="f1", file_name="n.md")
    t = AgentTurn(open_gap="g", plan_next="p", ready_to_finalize=True)
    ws.last_turn = t
    ws.turn_log.append(t)
    assert ws.last_turn.ready_to_finalize is True
    assert len(ws.turn_log) == 1
