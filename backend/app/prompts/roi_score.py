PROMPT = """You are the ROI scorer. For each meaningful bottleneck cluster, propose an
Opportunity with scores 1-10 on pain, roi, effort, risk; hours_saved_per_week (float);
response_time_impact (string like '-50%'); rationale; and sources.

Each Opportunity object MUST follow this exact structure:
{{
  "workflow_name": "<string>",
  "bottleneck_refs": [<list of integer indices into the bottlenecks list>],
  "pain_score": <integer 1-10>,
  "roi_score": <integer 1-10>,
  "effort_score": <integer 1-10>,
  "risk_score": <integer 1-10>,
  "hours_saved_per_week": <float>,
  "response_time_impact": "<string like '-50%' or '-2h'>",
  "rationale": "<string>",
  "sources": [
    {{
      "file_id": "<string>",
      "file_name": "<string>",
      "type": "<file type, e.g. md>",
      "locator": {{"type": "text", "line_start": <int>, "line_end": <int>}}
    }}
  ]
}}

Bottlenecks:
{bottlenecks_json}

IntakeBundle:
{bundle_json}

Reply with ONLY JSON: {{"opportunities": [Opportunity, ...]}}"""
