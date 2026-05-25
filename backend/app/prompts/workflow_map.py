"""Prompt for the ``workflow_map`` lead node.

Consolidates and de-duplicates per-file WorkflowRecord lists across the bundle.
The strict schema example is included to keep small-model output well-typed.
"""

PROMPT = """Act as an operations process mapper.

Your task is to consolidate IntakeBundle workflows into a clean workflow list for bottleneck detection.

You already have:
- IntakeBundle.workflows: workflow records extracted from individual files.
- IntakeBundle.pain_signals and lead_rows: context only; use them to clarify names, not to create new pain signals.
- IntakeBundle.file_index: valid source objects available in the run.

IntakeBundle:
{bundle_json}

Output schema:
- workflows: list[WorkflowRecord].
- WorkflowRecord.name: string. Concise process name, not a department or vague topic.
- WorkflowRecord.actors: list[string]. Roles or people who perform the process.
- WorkflowRecord.systems: list[string]. Apps, documents, inboxes, portals, or data stores used.
- WorkflowRecord.steps: list[string]. Ordered observed steps; keep unknown steps out.
- WorkflowRecord.manual_touchpoints: list[string]. Human copy/paste, waiting, re-keying, chasing, reconciliation, or approvals.
- WorkflowRecord.sources: list[Source]. Non-empty; preserve input Source objects.

Example:
{{"workflows":[{{"name":"Inbound lead intake","actors":["CSR","Producer"],"systems":["Email","CRM"],"steps":["Receive lead request","Create CRM record","Assign producer"],"manual_touchpoints":["CSR manually creates record"],"sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}}]}}

Format:
Reply ONLY with JSON matching {{"workflows":[WorkflowRecord,...]}}.

Constraints:
- Avoid creating workflows not supported by IntakeBundle.workflows.
- Merge duplicates only when name, actors, systems, and steps describe the same process.
- Do not create bottlenecks, scores, opportunities, or blueprint steps."""
