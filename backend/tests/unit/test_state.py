from app.state import DiagnosticState


def test_diagnostic_state_typed_dict_keys():
    expected_keys = {
        "run_id", "files", "file_summaries", "summary_review", "redo_count",
        "bundle", "workflows", "bottlenecks", "opportunities", "selected",
        "blueprint", "final_review", "revision_count", "errors",
    }
    assert expected_keys.issubset(DiagnosticState.__annotations__.keys())


def test_diagnostic_state_construct_minimal():
    state: DiagnosticState = {
        "run_id": "r1", "files": [], "file_summaries": {}, "summary_review": None,
        "redo_count": 0, "bundle": None, "workflows": [], "bottlenecks": [],
        "opportunities": [], "selected": None, "blueprint": None,
        "final_review": None, "revision_count": 0, "errors": [],
    }
    assert state["run_id"] == "r1"
