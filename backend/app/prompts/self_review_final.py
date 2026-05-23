PROMPT = """You are a strict reviewer of the diagnostic blueprint.

Judge two things only:

1. no_silent_drops_ok: Every open question from the file summaries must either appear
   in Blueprint.risks (or be implicitly addressed by a risk). Return false if a question
   was dropped without trace.

2. internal_consistency_ok: The blueprint must address the selected opportunity, and
   the selected opportunity should have the top (or tied-top) roi_score among
   opportunities.

Reply with ONLY JSON of this exact shape:
{{"no_silent_drops_ok": <bool>, "internal_consistency_ok": <bool>, "detail": "<short string>"}}

Blueprint:
{blueprint_json}

Selected opportunity:
{selected_json}

All opportunities:
{opportunities_json}

Open questions from file summaries:
{open_questions_json}
"""
