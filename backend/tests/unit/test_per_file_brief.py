"""Per-file extraction prompt rendering."""

from app.prompts.per_file_brief import render_brief


REQUIRED_LABELS = [
    "Act as",
    "Your task is",
    "You already have:",
    "Tool contracts:",
    "Output schema:",
    "Example:",
    "Format:",
    "Constraints:",
]


def _assert_template_order(prompt: str) -> None:
    """Assert schema-first prompt labels appear in the requested order."""
    positions = [prompt.index(section) for section in REQUIRED_LABELS]
    assert positions == sorted(positions)


def test_render_brief_includes_prompt_stack_and_metadata():
    """render_brief emits the structured prompt stack with file context."""
    prompt = render_brief(
        file_id="f1",
        file_name="notes.md",
        file_type="md",
        segment_count=3,
        iteration_cap=6,
    )

    _assert_template_order(prompt)
    assert "file_id=f1" in prompt
    assert "file_name=notes.md" in prompt
    assert "file_type=md" in prompt
    assert "segment_count=3" in prompt
    assert "at most 6 tool calls" in prompt


def test_render_brief_includes_tools_examples_and_strict_json_rule():
    """The brief tells the model its tools, examples, and output contract."""
    prompt = render_brief(
        file_id="f1",
        file_name="leads.csv",
        file_type="csv",
        segment_count=4,
        iteration_cap=5,
    )

    assert "search_text" in prompt
    assert "read_segment" in prompt
    assert "cite_locator" in prompt
    assert "extract_workflow" in prompt
    assert "extract_pain_signal" in prompt
    assert "extract_lead_row" in prompt
    assert "finalize_summary" in prompt
    assert "Example:" in prompt
    assert '{"tool":"search_text"' in prompt
    assert '{"tool":"finalize_summary"' in prompt
    assert 'Reply ONLY with JSON' in prompt
    assert "No prose, Markdown, code fences, or chain-of-thought" in prompt


def test_brief_documents_agent_turn_fields():
    """The brief instructs the model to fill the three reasoning fields every turn."""
    brief = render_brief(file_id="f1", file_name="n.md", file_type="md", segment_count=3, iteration_cap=6)
    assert "open_gap" in brief
    assert "plan_next" in brief
    assert "ready_to_finalize" in brief
