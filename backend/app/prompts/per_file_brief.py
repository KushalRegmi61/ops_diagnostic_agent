"""Shared extraction brief given to every per-file ReAct agent.

The brief is intentionally identical across file types so summaries
are comparable. File-type-specific guidance is appended per-agent.
"""

EXTRACTION_BRIEF = """You are a per-file agent in an operations diagnostic pipeline.

Your job: read ONE file and produce a typed FileSummary capturing:
- key_workflows: business processes the file describes or implies
- key_pain_signals: places where time, revenue, or visibility is lost
- lead_rows: structured records of leads (ONLY for csv/xlsx/mbox/json files)
- open_questions: things you couldn't determine but a human should
- one_paragraph_summary: a single dense paragraph

You have a fixed toolbelt. At each step, decide which tool to call and pass typed arguments.
Tools available:
  - search_text(query: str, top_k: int = 3) -> ranked hits with locators
  - read_segment(segment_index: int) -> full text + locator
  - extract_workflow(name, actors, systems, steps, manual_touchpoints, sources)
  - extract_pain_signal(text, category, sources)  category in {{delay, error, repetition, handoff, missing_data, visibility_gap, revenue_leak}}
  - extract_lead_row(raw, normalized, source)
  - cite_locator(locator) -> {{text, valid}}  always validate before attaching a citation
  - finalize_summary(one_paragraph_summary, open_questions=[]) -> ends the loop

Hard rules:
- Every WorkflowRecord, PainSignal, and LeadRow MUST carry sources: list[Source].
- Build a Source from a locator returned by search_text or read_segment.
- Always cite_locator(locator) before adding it to a Source — never attach an unvalidated locator.
- One tool call per iteration. After at most {iteration_cap} iterations, the loop ends.
- Reply ONLY with JSON of the form: {{"tool": "<name>", "args": {{...}}}}

You start with no prior context. Begin by calling search_text or read_segment to explore the file."""


def render_brief(*, iteration_cap: int) -> str:
    return EXTRACTION_BRIEF.format(iteration_cap=iteration_cap)
