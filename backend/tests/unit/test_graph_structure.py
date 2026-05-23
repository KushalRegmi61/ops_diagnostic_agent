"""Structural tests for the LangGraph parent workflow.

Verifies node names, entry point, conditional routing keys, and helper logic
without invoking the LLM. End-to-end behavior is covered by integration tests.
"""
from app.graph import _final_review_ok, build_graph, initial_state
from app.schemas import FinalReview


class _StubProvider:
    name = "stub"

    def generate_json(self, **_):
        raise AssertionError("graph structure test must not call the LLM")


def test_initial_state_shape():
    s = initial_state("run_abc", [])
    assert s["run_id"] == "run_abc"
    assert s["files"] == []
    assert s["file_summaries"] == {}
    assert s["redo_count"] == 0
    assert s["revision_count"] == 0
    assert s["bundle"] is None
    assert s["final_review"] is None


def test_final_review_ok_all_true():
    fr = FinalReview(
        citation_existence_ok=True, citation_reachability_ok=True,
        no_silent_drops_ok=True, internal_consistency_ok=True,
        detail="", revised_once=False,
    )
    assert _final_review_ok(fr) is True


def test_final_review_ok_any_false():
    fr = FinalReview(
        citation_existence_ok=True, citation_reachability_ok=False,
        no_silent_drops_ok=True, internal_consistency_ok=True,
        detail="", revised_once=False,
    )
    assert _final_review_ok(fr) is False


def test_graph_compiles_and_exposes_all_nodes():
    compiled = build_graph(provider=_StubProvider(), parsed_files={})
    nodes = set(compiled.get_graph().nodes.keys())
    expected = {
        "per_file_fanout", "review_summaries", "redo_inc",
        "synthesis", "workflow_map", "bottleneck_detect", "roi_score",
        "fastest_win_select", "solution_blueprint", "self_review_final",
        "revise_inc",
    }
    assert expected.issubset(nodes)
