"""Prompt for the ``fastest_win_select`` lead node.

Selects exactly one opportunity index by maximising ``roi - effort - risk`` with
tiebreakers, which seeds the downstream blueprint writer.
"""

PROMPT = """Select the single best opportunity by maximizing roi_score - effort_score - risk_score.
Ties broken by higher pain_score, then by lowest effort_score.

Opportunities:
{opportunities_json}

Reply with ONLY JSON: {{"selected_index": int}}"""
