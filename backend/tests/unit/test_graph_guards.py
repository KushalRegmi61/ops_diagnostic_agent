"""Graph nodes raise structured errors (not assert) when bundle is malformed."""
from app.graph import build_graph, initial_state
from app.schemas import IntakeBundle


class _NullProvider:
    name = "null"
    model = "null"

    def chat_model(self, **kwargs):
        raise NotImplementedError

    def generate_json(self, **kwargs):
        raise NotImplementedError


def _node(graph, name):
    """Return the raw closure for a node by name (LangGraph internal API)."""
    spec = graph.get_graph().nodes[name].data
    # RunnableCallable exposes the underlying function as .func
    return getattr(spec, "func", spec)


def test_workflow_map_node_emits_error_when_bundle_is_none() -> None:
    graph = build_graph(provider=_NullProvider(), parsed_files={})  # type: ignore[arg-type]
    state = initial_state("r_guards_wm", [])
    state["bundle"] = None
    fn = _node(graph, "workflow_map")
    out = fn(state)
    # No more bare AssertionError; structured ExtractionError instead.
    assert "errors" in out
    assert any(e.stage == "workflow_map" for e in out["errors"]), out


def test_bottleneck_detect_node_emits_error_when_bundle_is_none() -> None:
    graph = build_graph(provider=_NullProvider(), parsed_files={})  # type: ignore[arg-type]
    state = initial_state("r_guards_bd", [])
    state["bundle"] = None
    fn = _node(graph, "bottleneck_detect")
    out = fn(state)
    assert "errors" in out
    assert any(e.stage == "bottleneck_detect" for e in out["errors"]), out


def test_roi_score_node_emits_error_when_bundle_is_none() -> None:
    graph = build_graph(provider=_NullProvider(), parsed_files={})  # type: ignore[arg-type]
    state = initial_state("r_guards_roi", [])
    state["bundle"] = None
    state["bottlenecks"] = []
    fn = _node(graph, "roi_score")
    out = fn(state)
    assert "errors" in out
    assert any(e.stage == "roi_score" for e in out["errors"]), out


def test_solution_blueprint_node_emits_error_when_bundle_is_none() -> None:
    """solution_blueprint_node must guard bundle-is-None even when selected is set."""
    from unittest.mock import MagicMock
    graph = build_graph(provider=_NullProvider(), parsed_files={})  # type: ignore[arg-type]
    state = initial_state("r_guards_sb", [])
    state["bundle"] = None
    state["selected"] = MagicMock()  # selected is present, but bundle is missing
    state["opportunities"] = [state["selected"]]
    fn = _node(graph, "solution_blueprint")
    out = fn(state)
    assert "errors" in out
    assert any(e.stage == "solution_blueprint" for e in out["errors"]), out


def test_self_review_node_emits_error_when_bundle_is_none() -> None:
    """self_review_node must guard bundle-is-None even when blueprint is set."""
    from unittest.mock import MagicMock
    graph = build_graph(provider=_NullProvider(), parsed_files={})  # type: ignore[arg-type]
    state = initial_state("r_guards_sr", [])
    state["bundle"] = None
    state["blueprint"] = MagicMock()
    state["selected"] = MagicMock()
    fn = _node(graph, "self_review_final")
    out = fn(state)
    assert "errors" in out
    assert any(e.stage == "self_review_final" for e in out["errors"]), out
