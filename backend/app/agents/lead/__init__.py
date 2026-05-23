"""Lead-agent nodes for the parent LangGraph workflow.

Each module exposes a single ``run(...)`` function that calls
``provider.generate_json(prompt, schema)`` once and returns a validated
Pydantic model. The eight nodes together form the lead's diagnostic chain:
``review_summaries`` (gate per-file outputs), ``synthesis`` (merge into an
IntakeBundle), ``workflow_map`` -> ``bottleneck_detect`` -> ``roi_score`` ->
``fastest_win_select`` -> ``solution_blueprint``, then ``self_review_final``
which can request a bounded revision.
"""
