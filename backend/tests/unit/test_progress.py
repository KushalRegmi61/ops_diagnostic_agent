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


from app.agents.per_file._progress import (
    coverage_gaps,
    signature,
    total_findings,
    saturated,
)


def test_coverage_gaps_returns_unvisited_ranges():
    # total 10 segments, visited 0,1,5 -> gaps (2,4) and (6,9)
    assert coverage_gaps([0, 1, 5], 10) == [(2, 4), (6, 9)]


def test_coverage_gaps_full_coverage_is_empty():
    assert coverage_gaps([0, 1, 2], 3) == []


def test_coverage_gaps_nothing_visited_is_whole_doc():
    assert coverage_gaps([], 4) == [(0, 3)]


def test_signature_is_stable_under_key_order():
    assert signature("search_text", {"query": "a", "top_k": 3}) == signature(
        "search_text", {"top_k": 3, "query": "a"}
    )


def test_signature_differs_on_args():
    assert signature("search_text", {"query": "a"}) != signature("search_text", {"query": "b"})


def test_total_findings_sums_three_ledgers():
    from app.agents.per_file._state import WorkingState
    ws = WorkingState(file_id="f1", file_name="x")
    assert total_findings(ws) == 0


def test_saturated_true_when_plan_done_findings_present_and_stagnant():
    from app.agents.per_file._state import WorkingState
    ws = WorkingState(file_id="f1", file_name="x", iteration_cap=6)
    ws.plan = ["a", "b"]
    ws.iteration = 4               # >= len(plan) -> "plan exhausted" proxy
    ws.workflows = ["wf"]          # total_findings == 1
    ws.findings_at_turn = [0, 1, 1, 1]   # last window (2) deltas are zero
    assert saturated(ws, window=2) is True


def test_saturated_false_when_findings_still_growing():
    from app.agents.per_file._state import WorkingState
    ws = WorkingState(file_id="f1", file_name="x", iteration_cap=6)
    ws.plan = ["a", "b"]
    ws.iteration = 4
    ws.workflows = ["wf"]
    ws.findings_at_turn = [0, 1, 2, 3]   # growing
    assert saturated(ws, window=2) is False


def test_saturated_false_when_no_findings():
    from app.agents.per_file._state import WorkingState
    ws = WorkingState(file_id="f1", file_name="x", iteration_cap=6)
    ws.plan = ["a"]
    ws.iteration = 4
    ws.findings_at_turn = [0, 0, 0, 0]
    assert saturated(ws, window=2) is False
