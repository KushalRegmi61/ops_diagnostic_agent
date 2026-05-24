"""Tool set used by the per-file ReAct agent.

The LLM never imports or executes these functions directly. It emits a JSON
tool call such as ``{"tool": "search_text", "args": {...}}``; the router
validates that call and invokes the matching Python function.

The tools fall into four groups:
- retrieval: ``search_text`` and ``read_segment`` inspect ParsedFile segments.
- citation: ``cite_locator`` verifies that locators resolve to source text.
- extraction: ``extract_workflow``, ``extract_pain_signal``, and
  ``extract_lead_row`` append typed findings to WorkingState.
- termination: ``finalize_summary`` freezes WorkingState into FileSummary.
"""
