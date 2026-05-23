"""Tool set for the per-file ReAct agent.

Each tool module exposes a single function that the loop's dispatcher
invokes: ``search_text`` and ``read_segment`` for exploring the ParsedFile;
``extract_workflow``, ``extract_pain_signal``, and ``extract_lead_row`` for
appending typed findings to the WorkingState; ``cite_locator`` for verifying
that a Source round-trips through ``parsers.excerpt``; and
``finalize_summary`` to terminate the loop with a FileSummary.
"""
