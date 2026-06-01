"""AgentTurn is a flat, tolerant per-turn reasoning record."""
from app.schemas import AgentTurn


def test_agent_turn_accepts_full_reasoning():
    t = AgentTurn(open_gap="no workflows yet", plan_next="search handoffs", ready_to_finalize=False)
    assert t.open_gap == "no workflows yet"
    assert t.ready_to_finalize is False


def test_agent_turn_defaults_are_tolerant():
    # Small-model variance: a tool call that omits the fields must not crash.
    t = AgentTurn()
    assert t.open_gap == ""
    assert t.plan_next == ""
    assert t.ready_to_finalize is False
