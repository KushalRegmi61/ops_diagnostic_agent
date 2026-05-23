PROMPT = """Select the single best opportunity by maximizing roi_score - effort_score - risk_score.
Ties broken by higher pain_score, then by lowest effort_score.

Opportunities:
{opportunities_json}

Reply with ONLY JSON: {{"selected_index": int}}"""
