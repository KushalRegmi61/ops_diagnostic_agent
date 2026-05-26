"""DiagnosticState.errors must accumulate via operator.add — not OVERWRITE."""
import operator
from typing import get_args, get_origin, get_type_hints


def test_diagnostic_state_errors_uses_add_reducer() -> None:
    """state.errors must be Annotated[list[ExtractionError], operator.add]."""
    from app.state import DiagnosticState

    hints = get_type_hints(DiagnosticState, include_extras=True)
    errors_hint = hints["errors"]
    assert get_origin(errors_hint) is not None, (
        f"errors must be Annotated; got plain {errors_hint!r}"
    )
    args = get_args(errors_hint)
    assert operator.add in args, (
        f"errors must carry operator.add reducer for accumulation; got {args!r}"
    )


def test_no_manual_errors_accumulator_in_graph() -> None:
    """All 17 sites must return {'errors': [new]} — no `state.get('errors')` reads remain.

    With operator.add on the field, reading-then-appending duplicates entries
    (existing + [new] gets concatenated to existing again by the reducer).
    """
    import inspect
    import app.graph as graph_mod

    src = inspect.getsource(graph_mod)
    assert 'state.get("errors")' not in src, (
        "graph.py still references state.get('errors') — the manual accumulator "
        "boilerplate must be stripped after annotating the field with operator.add."
    )
