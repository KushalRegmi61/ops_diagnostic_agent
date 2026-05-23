"""Prompt for the ``bottleneck_detect`` lead node.

Pairs each consolidated workflow with PainSignals from the bundle to emit one
Bottleneck per distinct problem. Every Bottleneck must carry sources so the
downstream citation invariant holds.
"""

PROMPT = """You are the bottleneck-detector. For each workflow, identify bottlenecks
using pain signals from the bundle. Emit one Bottleneck per distinct problem.
Every Bottleneck MUST carry sources.

Each Bottleneck object MUST follow this exact structure:
{{
  "workflow_name": "<string: name of the workflow>",
  "signal": "<one of: delay, error, repetition, handoff, missing_data, visibility_gap, revenue_leak>",
  "impact": "<string: description of the impact>",
  "sources": [
    {{
      "file_id": "<string>",
      "file_name": "<string>",
      "type": "<file type, e.g. md, pdf, docx, txt, csv, xlsx, mbox, json, transcript_vtt, transcript_srt>",
      "locator": {{"type": "text", "line_start": <int>, "line_end": <int>}}
    }}
  ]
}}

Workflows:
{workflows_json}

IntakeBundle (for pain signals):
{bundle_json}

Reply with ONLY JSON: {{"bottlenecks": [Bottleneck, ...]}}"""
