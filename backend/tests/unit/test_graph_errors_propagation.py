"""When the diagnostic chain produces no blueprint, the reason MUST land in state.errors."""
import pytest

from app.graph import build_graph, initial_state
from app.schemas import IntakeBundle


class _NullProvider:
    """No LLM calls happen on this path — selected=None short-circuits everything."""
    name = "null"
    model = "null"

    def chat_model(self, **kwargs):
        raise NotImplementedError("not called on this path")

    def generate_json(self, **kwargs):
        raise NotImplementedError("not called on this path")


def test_solution_blueprint_with_no_selected_records_error() -> None:
    """Invoke build_graph nodes directly to drive the no-blueprint path.

    Direct closure invocation avoids LangGraph entry-point overrides which are
    version-dependent. node.data.func gives the raw Python closure.
    """
    graph = build_graph(provider=_NullProvider(), parsed_files={})  # type: ignore[arg-type]
    # CompiledStateGraph exposes its node functions via .nodes (NodeSpec.runnable).
    nodes = graph.get_graph().nodes
    solution_blueprint_fn = None
    self_review_fn = None
    # Each LangGraph node entry has a .data attribute that holds a RunnableCallable.
    # .data.func gives the raw Python closure.
    for name, node in nodes.items():
        if name == "solution_blueprint":
            solution_blueprint_fn = node.data.func
        elif name == "self_review_final":
            self_review_fn = node.data.func
    assert solution_blueprint_fn is not None
    assert self_review_fn is not None

    state = initial_state("r_test_err", [])
    state["bundle"] = IntakeBundle(
        workflows=[], pain_signals=[], lead_rows=[],
        contradictions=[], file_index=[], extraction_errors=[],
    )
    state["selected"] = None  # forces the no-blueprint branch
    state["opportunities"] = []

    out = solution_blueprint_fn(state)
    assert out.get("blueprint") is None
    assert out.get("errors"), "solution_blueprint must append to state.errors when selected is None"
    assert any(e.stage == "solution_blueprint" for e in out["errors"])

    # Now drive self_review_final with the empty blueprint state.
    state.update(out)
    out2 = self_review_fn(state)
    assert out2.get("final_review") is None
    assert out2.get("errors"), "self_review_final must append to state.errors when blueprint is None"
    assert any(e.stage == "self_review_final" for e in out2["errors"])
