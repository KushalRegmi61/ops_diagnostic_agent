"""Prompt for the ``workflow_map`` lead node.

Consolidates and de-duplicates per-file WorkflowRecord lists across the bundle.
The strict schema example is included to keep small-model output well-typed.
"""

PROMPT = """You are the workflow-mapper. Given an IntakeBundle, return list[WorkflowRecord]
that consolidates and de-duplicates workflows across files. Every workflow MUST carry
non-empty sources.

Each WorkflowRecord object MUST follow this exact structure:
{{
  "name": "<string: workflow name>",
  "actors": ["<list of actor names>"],
  "systems": ["<list of system names>"],
  "steps": ["<list of step descriptions>"],
  "manual_touchpoints": ["<list of manual touchpoint descriptions>"],
  "sources": [
    {{
      "file_id": "<string>",
      "file_name": "<string>",
      "type": "<file type, e.g. md, pdf, docx>",
      "locator": {{"type": "text", "line_start": <int>, "line_end": <int>}}
    }}
  ]
}}

IntakeBundle:
{bundle_json}

Reply with ONLY JSON: {{"workflows": [WorkflowRecord, ...]}}"""
