"""Prompt for the ``bottleneck_detect`` lead node.

Pairs each consolidated workflow with PainSignals from the bundle to emit one
Bottleneck per distinct problem. Every Bottleneck must carry sources so the
downstream citation invariant holds.
"""

PROMPT = """Act as a bottleneck diagnostician.

Your task is to convert workflows and bundle pain signals into distinct Bottleneck records.

You already have:
- workflows: normalized WorkflowRecord objects from the previous node.
- IntakeBundle.pain_signals: cited evidence of delay, error, repetition, handoff, missing_data, visibility_gap, or revenue_leak.
- IntakeBundle.lead_rows and contradictions: context for impact only.

Workflows:
{workflows_json}

IntakeBundle:
{bundle_json}

Output schema:
- bottlenecks: list[Bottleneck].
- Bottleneck.workflow_name: string. Must match or clearly refer to one provided workflow name.
- Bottleneck.signal: enum string. One of delay, error, repetition, handoff, missing_data, visibility_gap, revenue_leak.
- Bottleneck.impact: string. Concrete operational consequence, not a solution.
- Bottleneck.sources: list[Source]. Non-empty; cite pain/workflow evidence from inputs.

Example:
{{"bottlenecks":[{{"workflow_name":"Inbound lead intake","signal":"delay","impact":"Slow first response can reduce lead conversion.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}}]}}

Format:
Reply ONLY with JSON matching {{"bottlenecks":[Bottleneck,...]}}.

Constraints:
- Avoid bottlenecks without a supporting pain signal or workflow source.
- Do not score ROI, estimate savings, select a winner, or propose an automation.
- Keep one bottleneck per distinct problem; do not duplicate the same signal for the same workflow."""
