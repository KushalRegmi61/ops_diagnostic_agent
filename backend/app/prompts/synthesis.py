"""Prompt for the ``synthesis`` lead node.

Reconciles per-file FileSummary objects into a single IntakeBundle, preserving
contradictions explicitly rather than silently merging conflicting facts.
"""

PROMPT = """Act as a cross-file evidence reconciler.

Your task is to merge reviewed FileSummary objects into one IntakeBundle.

You already have:
- FileSummary objects keyed by file_id. Each contains key_workflows, key_pain_signals, lead_rows, open_questions, and agent_notes.
- Source objects inside workflows, pain signals, and lead rows. Preserve them exactly.

Per-file summaries:
{summaries_json}

Output schema:
- workflows: list[WorkflowRecord]. Carry forward and lightly dedupe equivalent workflows.
- pain_signals: list[PainSignal]. Carry forward cited operational pain points.
- lead_rows: list[LeadRow]. Carry forward structured lead/contact/opportunity records.
- contradictions: list[Contradiction]. Use when files disagree on the same fact.
- contradictions[].topic: string. Short fact under dispute.
- contradictions[].statements: list[{{claim: str, sources: list[Source]}}]. One entry per conflicting side.
- file_index: list[Source]. Deduped Source objects observed anywhere in the summaries.
- extraction_errors: list[ExtractionError]. Empty unless an input summary is missing or unusable.

Example:
{{"workflows":[],"pain_signals":[{{"text":"Leads wait more than 24 hours.","category":"delay","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}}],"lead_rows":[],"contradictions":[],"file_index":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}],"extraction_errors":[]}}

Format:
Reply ONLY with JSON matching the IntakeBundle schema.

Constraints:
- Avoid dropping cited records from clean summaries.
- Do not score ROI, detect bottlenecks, select winners, or write blueprints.
- Do not invent extraction_errors for normal open questions."""
