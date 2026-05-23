PROMPT = """You are the blueprint writer. Produce a Blueprint for the selected opportunity.

CRITICAL: Every claim object (summary, and each item in steps, required_systems,
success_metrics, risks) MUST be shaped exactly:
  {{"text": "<string>", "sources": [<Source object>, ...]}}

A Source is ALWAYS a JSON object — NEVER a bare string. Each Source MUST be:
  {{"file_id": "<from bundle file_index>", "file_name": "<from bundle file_index>",
    "type": "<from bundle file_index>", "locator": {{"type": "text", "line_start": <int>, "line_end": <int>}}}}

Worked example of the full Blueprint shape (repeat this exact Source structure in
EVERY claim, including steps, required_systems, success_metrics, risks):
{{
  "opportunity_ref": 0,
  "summary": {{
    "text": "Auto-route inbound leads from email to CRM",
    "sources": [{{"file_id": "f1", "file_name": "x.md", "type": "md", "locator": {{"type": "text", "line_start": 1, "line_end": 1}}}}]
  }},
  "steps": [
    {{"text": "Watch shared inbox for new leads", "sources": [{{"file_id": "f1", "file_name": "x.md", "type": "md", "locator": {{"type": "text", "line_start": 1, "line_end": 1}}}}]}},
    {{"text": "Create CRM record via API", "sources": [{{"file_id": "f1", "file_name": "x.md", "type": "md", "locator": {{"type": "text", "line_start": 1, "line_end": 1}}}}]}}
  ],
  "required_systems": [
    {{"text": "HubSpot CRM", "sources": [{{"file_id": "f1", "file_name": "x.md", "type": "md", "locator": {{"type": "text", "line_start": 1, "line_end": 1}}}}]}}
  ],
  "success_metrics": [
    {{"text": "Lead-to-CRM time under 5 minutes", "sources": [{{"file_id": "f1", "file_name": "x.md", "type": "md", "locator": {{"type": "text", "line_start": 1, "line_end": 1}}}}]}}
  ],
  "risks": [
    {{"text": "Misclassified leads need manual review", "sources": [{{"file_id": "f1", "file_name": "x.md", "type": "md", "locator": {{"type": "text", "line_start": 1, "line_end": 1}}}}]}}
  ]
}}

Use ONLY Sources whose file_id / file_name / type appear in the bundle's file_index list.

Selected opportunity index: {selected_index}

Selected opportunity payload:
{selected_json}

IntakeBundle (use file_index entries as Source values):
{bundle_json}

Reply with ONLY JSON matching the Blueprint shape above. No prose, no markdown fences."""
