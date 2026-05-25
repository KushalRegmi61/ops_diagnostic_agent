"""Prompt for the ``fastest_win_select`` lead node.

Selects exactly one opportunity index by maximising ``roi - effort - risk`` with
tiebreakers, which seeds the downstream blueprint writer.
"""

PROMPT = """Act as a pragmatic automation portfolio lead.

Your task is to select the single fastest-win Opportunity by index.

You already have:
- opportunities: ordered list of Opportunity objects with pain_score, roi_score, effort_score, and risk_score.
- The selected index will be used by the blueprint writer; do not alter opportunity content.

Opportunities:
{opportunities_json}

Output schema:
- selected_index: int. Existing zero-based index into the opportunities list.

Selection rule:
- Primary score = roi_score - effort_score - risk_score.
- Tie 1: higher pain_score.
- Tie 2: lower effort_score.
- Tie 3: earlier list index.

Example:
{{"selected_index":0}}

Format:
Reply ONLY with JSON matching {{"selected_index":int}}.

Constraints:
- Avoid returning an out-of-range index.
- Do not rewrite, rescore, merge, or explain opportunities.
- Select exactly one."""
