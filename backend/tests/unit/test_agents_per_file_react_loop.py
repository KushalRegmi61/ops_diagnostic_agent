"""Prompt context helpers and loop behavior for per-file ReAct extraction."""

from typing import Type

from pydantic import BaseModel

from app.agents.per_file._react_loop import (
    _segment_index_recap,
    _state_recap,
    run_react_loop,
)
from app.agents.per_file._state import WorkingState
from app.llm.base import GenerateMetadata
from app.schemas import LeadRow, ParsedFile, ParsedSegment, PainSignal, Source, WorkflowRecord


def _parsed() -> ParsedFile:
    """Return a small markdown ParsedFile for loop tests."""
    return ParsedFile(
        file_id="f1",
        file_name="notes.md",
        type="md",
        segments=[
            ParsedSegment(
                text="Leads wait more than 24 hours before first response.",
                locator={"type": "text", "line_start": 1, "line_end": 1},
            ),
            ParsedSegment(
                text="CSR manually copies CRM notes into email.",
                locator={"type": "text", "line_start": 2, "line_end": 2},
            ),
        ],
    )


def _source() -> Source:
    """Return a Source pointing to the first test segment."""
    return Source(
        file_id="f1",
        file_name="notes.md",
        type="md",
        locator={"type": "text", "line_start": 1, "line_end": 1},
    )


def test_segment_index_recap_includes_locator_preview():
    """Segment recap exposes both segment index and locator JSON."""
    recap = _segment_index_recap(_parsed())

    assert "[0] locator=" in recap
    assert '"line_start": 1' in recap
    assert "Leads wait more than 24 hours" in recap


def test_state_recap_includes_recent_finding_snippets():
    """Working-state recap includes compact finding names to reduce duplicates."""
    ws = WorkingState(file_id="f1", file_name="notes.md")
    ws.iteration = 3
    ws.workflows.append(
        WorkflowRecord(
            name="Inbound lead follow-up",
            actors=["Producer"],
            systems=["CRM"],
            steps=["Lead arrives", "Producer follows up"],
            manual_touchpoints=["Manual CRM note copy"],
            sources=[_source()],
        )
    )
    ws.pain_signals.append(
        PainSignal(text="Leads wait more than 24 hours before response.", category="delay", sources=[_source()])
    )
    ws.lead_rows.append(
        LeadRow(raw={"name": "Acme Corp"}, normalized={"company": "Acme Corp"}, source=_source())
    )

    recap = _state_recap(ws)

    assert "iter=3" in recap
    assert "recent_workflows=[Inbound lead follow-up]" in recap
    assert "recent_pain_signals=[Leads wait more than 24 hours before response.]" in recap
    assert "recent_lead_rows=[" in recap
    assert "Acme Corp" in recap


class _FakeProvider:
    """LLMProvider test double that records prompts and returns fixed calls."""

    name = "fake"

    def __init__(self, replies: list[dict]):
        self.replies = replies
        self.prompts: list[str] = []

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> tuple[dict, GenerateMetadata]:
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        return reply, GenerateMetadata(
            provider="fake",
            model="fake-model",
            prompt_name=prompt_name,
            token_estimate=len(prompt.split()),
            parsed_json=True,
            retry_count=0,
            latency_ms=1,
        )


def test_run_react_loop_adds_validated_locator_to_next_prompt():
    """A successful cite_locator call becomes reusable source context next turn."""
    provider = _FakeProvider(
        [
            {"tool": "cite_locator", "args": {"locator": {"type": "text", "line_start": 1, "line_end": 1}}},
            {"tool": "finalize_summary", "args": {"one_paragraph_summary": "Lead response delays are present."}},
        ]
    )

    summary = run_react_loop(
        provider=provider,
        parsed=_parsed(),
        prompt_suffix="Markdown notes.",
        iteration_cap=2,
    )

    assert summary.one_paragraph_summary == "Lead response delays are present."
    assert len(provider.prompts) == 2
    assert "Validated source candidates:" in provider.prompts[1]
    assert '"file_id": "f1"' in provider.prompts[1]
    assert '"line_start": 1' in provider.prompts[1]
    assert "Leads wait more than 24 hours before first response." in provider.prompts[1]
