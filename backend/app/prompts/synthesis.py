"""Prompt for the ``synthesis`` lead node.

Reconciles per-file FileSummary objects into a single IntakeBundle, preserving
contradictions explicitly rather than silently merging conflicting facts.
"""

PROMPT = """You are the synthesizer. Reconcile per-file FileSummary objects into one IntakeBundle.

Rules:
- Carry every WorkflowRecord, PainSignal, and LeadRow from all summaries.
- When two files disagree on a fact, DO NOT silently merge. Add a Contradiction with both claims and both citations.
- file_index is the deduped list of Source objects observed across files.
- extraction_errors is empty unless one or more file_summaries was missing.

Per-file summaries:
{summaries_json}

Reply with ONLY JSON matching the IntakeBundle schema."""
