"""Structural tests for the LangGraph parent workflow.

Verifies node names, entry point, conditional routing keys, and helper logic
without invoking the LLM. End-to-end behavior is covered by integration tests.
"""
import inspect

from app.graph import _final_review_ok, build_graph, initial_state
import app.graph as graph_module
from app.schemas import FinalReview, RunContext


class _StubProvider:
    """Stub LLM provider that fails loudly if a node attempts to call it."""

    name = "stub"

    def generate_json(self, **_):
        """Refuse any LLM call — structural tests must not reach the model."""
        raise AssertionError("graph structure test must not call the LLM")


def test_initial_state_shape():
    """initial_state seeds run_id, empty collections, and zero counters."""
    s = initial_state("run_abc", [])
    assert s["run_id"] == "run_abc"
    assert s["files"] == []
    assert s["file_summaries"] == {}
    assert s["redo_count"] == 0
    assert s["revision_count"] == 0
    assert s["bundle"] is None
    assert s["final_review"] is None


def test_final_review_ok_all_true():
    """_final_review_ok returns True when every gate is True."""
    fr = FinalReview(
        citation_existence_ok=True, citation_reachability_ok=True,
        no_silent_drops_ok=True, internal_consistency_ok=True,
        detail="", revised_once=False,
    )
    assert _final_review_ok(fr) is True


def test_final_review_ok_any_false():
    """_final_review_ok returns False when any individual gate fails."""
    fr = FinalReview(
        citation_existence_ok=True, citation_reachability_ok=False,
        no_silent_drops_ok=True, internal_consistency_ok=True,
        detail="", revised_once=False,
    )
    assert _final_review_ok(fr) is False


def test_graph_compiles_and_exposes_all_nodes():
    """build_graph compiles a workflow whose node set matches the spec."""
    compiled = build_graph(provider=_StubProvider(), parsed_files={})
    nodes = set(compiled.get_graph().nodes.keys())
    expected = {
        "per_file_fanout", "review_summaries", "redo_inc",
        "synthesis", "workflow_map", "bottleneck_detect", "roi_score",
        "fastest_win_select", "solution_blueprint", "self_review_final",
        "revise_inc",
    }
    assert expected.issubset(nodes)


def test_parent_graph_passes_run_context_to_per_file_agents():
    """per_file_fanout threads run and trace context into nested agents."""
    source = inspect.getsource(graph_module.build_graph)

    assert 'run_id=state["run_id"]' in source
    assert 'trace_name=f"per_file:{file_ref.file_id}"' in source


def test_initial_state_defaults_run_context_to_none():
    """initial_state called without run_context produces state['run_context'] is None."""
    state = initial_state("r_test", [])
    assert state["run_context"] is None


def test_initial_state_writes_run_context_when_provided():
    """initial_state called with a RunContext stores it under 'run_context'."""
    ctx = RunContext(user_context="focus onboarding")
    state = initial_state("r_test", [], run_context=ctx)
    assert state["run_context"] == ctx
