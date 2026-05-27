"""Wiring tests: lead agents pass run_context through to their prompt render."""
from unittest.mock import patch

from app.schemas import RunContext


def test_synthesis_passes_run_context_into_prompt_render():
    """The synthesis lead agent forwards run_context into synthesis_prompt.render(...)."""
    from app.agents.lead import synthesis as synth_agent

    captured: dict = {}

    def fake_render(*, run_context=None, **kwargs):
        captured["run_context"] = run_context
        captured["kwargs"] = kwargs
        return "RENDERED_PROMPT_STUB"

    class _FakeMeta:
        parsed_json = True
        retry_count = 0
        provider = "fake"
        model = "fake-model"
        prompt_name = "test"
        token_estimate = 0
        latency_ms = 0

    class _FakeProvider:
        def generate_json(self, *, prompt_name, prompt, schema):
            return (
                {
                    "workflows": [], "pain_signals": [], "lead_rows": [],
                    "contradictions": [], "file_index": [], "extraction_errors": [],
                },
                _FakeMeta(),
            )

    with patch("app.agents.lead.synthesis.synthesis_prompt.render", side_effect=fake_render):
        synth_agent.run(
            provider=_FakeProvider(),
            file_summaries={},
            run_context=RunContext(user_context="focus onboarding"),
        )

    assert captured["run_context"] is not None
    assert captured["run_context"].user_context == "focus onboarding"


def test_synthesis_passes_none_when_no_context():
    """When run_context is omitted, the prompt render receives None."""
    from app.agents.lead import synthesis as synth_agent

    captured: dict = {}

    def fake_render(*, run_context=None, **kwargs):
        captured["run_context"] = run_context
        return "RENDERED_PROMPT_STUB"

    class _FakeMeta:
        parsed_json = True
        retry_count = 0
        provider = "fake"
        model = "fake-model"
        prompt_name = "test"
        token_estimate = 0
        latency_ms = 0

    class _FakeProvider:
        def generate_json(self, *, prompt_name, prompt, schema):
            return (
                {
                    "workflows": [], "pain_signals": [], "lead_rows": [],
                    "contradictions": [], "file_index": [], "extraction_errors": [],
                },
                _FakeMeta(),
            )

    with patch("app.agents.lead.synthesis.synthesis_prompt.render", side_effect=fake_render):
        synth_agent.run(provider=_FakeProvider(), file_summaries={})

    assert captured["run_context"] is None
