"""Tier-1 deterministic tests for the per-file ProgressState working memory."""
from app.agents.per_file._state import WorkingState


def test_progress_state_has_working_memory_fields_with_defaults():
    ws = WorkingState(file_id="f1", file_name="x.txt", total_segments=10, iteration_cap=6)
    assert ws.total_segments == 10
    assert ws.iteration_cap == 6
    assert ws.segments_visited == []
    assert ws.queries_run == []
    assert ws.coverage_frontier == 0
    assert ws.plan == []
    assert ws.last_signature is None
    assert ws.stall_count == 0
    assert ws.findings_at_turn == []


def test_steps_remaining_is_cap_minus_iteration_floored_at_zero():
    ws = WorkingState(file_id="f1", file_name="x.txt", iteration_cap=6)
    ws.iteration = 2
    assert ws.steps_remaining == 4
    ws.iteration = 9
    assert ws.steps_remaining == 0
