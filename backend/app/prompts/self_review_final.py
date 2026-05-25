"""Prompt for the ``self_review_final`` lead node.

The LLM portion of final review: judges no_silent_drops_ok and
internal_consistency_ok. Deterministic checks (citation existence and excerpt
reachability) run in code around this prompt — together they gate the bounded
revision loop back to ``solution_blueprint``.
"""

PROMPT = """Act as a strict final blueprint reviewer.

Your task is to judge silent-drop handling and internal consistency only.

You already have:
- Blueprint: final proposed automation with cited claims.
- selected opportunity: the opportunity the Blueprint should solve.
- all opportunities: context for whether the selected opportunity was reasonable.
- open questions: unresolved questions from file summaries.
- Deterministic code already checks citation existence and locator reachability.

Blueprint:
{blueprint_json}

Selected opportunity:
{selected_json}

All opportunities:
{opportunities_json}

Open questions:
{open_questions_json}

Output schema:
- no_silent_drops_ok: bool. True only if every open question is addressed in risks, design, or clearly irrelevant.
- internal_consistency_ok: bool. True only if the Blueprint solves the selected opportunity and does not contradict opportunity scores/context.
- detail: string. Short reason for any false value, or concise pass note.

Example:
{{"no_silent_drops_ok":true,"internal_consistency_ok":true,"detail":"Blueprint targets the selected opportunity and traces open questions into risks."}}

Format:
Reply ONLY with JSON matching {{"no_silent_drops_ok":bool,"internal_consistency_ok":bool,"detail":str}}.

Constraints:
- Avoid re-checking citation existence or locator reachability.
- Do not rewrite the Blueprint.
- Mark internal_consistency_ok false if the Blueprint solves a different workflow or opportunity."""
