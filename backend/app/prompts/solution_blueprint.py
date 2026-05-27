"""Prompt for the ``solution_blueprint`` lead node.

Writes the final automation Blueprint for the selected opportunity. The prompt
demands terse, scannable markdown in every BlueprintClaim.text — a bold lead
phrase followed by 1–2 short sentences — so the UI renders a clean, executive
brief instead of essay-style paragraphs.
"""

from app.prompts._steering import Role, render_priorities_block
from app.schemas import RunContext

PROMPT = """Act as a senior automation solution architect.

Your task is to write the final cited Blueprint for the selected Opportunity as a scannable, executive-ready brief.

You already have:
- selected_index: the chosen opportunity index. Use it as opportunity_ref.
- selected opportunity: the only opportunity to design for.
- IntakeBundle: source-backed workflows, pains, lead rows, contradictions, and file_index.
- Source objects: must be copied from selected opportunity sources or bundle.file_index; never use bare strings.

Selected opportunity index: {selected_index}

Selected opportunity:
{selected_json}

IntakeBundle:
{bundle_json}

Output schema:
- opportunity_ref: int. Must equal selected_index.
- summary: BlueprintClaim. ≤80 words. **Bold lead phrase.** then 1–2 sentences covering pain, automation, affected workflow, expected outcome, evidence basis.
- steps: list[BlueprintClaim]. 5–8 ordered implementation steps. Each ≤40 words: **bold action lead.** then 1–2 sentences with owner/system touchpoints and expected result.
- required_systems: list[BlueprintClaim]. Each ≤40 words: **bold system name.** then 1–2 sentences on capability, permissions, integrations.
- success_metrics: list[BlueprintClaim]. Each ≤40 words: **bold metric.** then 1–2 sentences with baseline/target when supported by inputs.
- risks: list[BlueprintClaim]. Each ≤40 words: **bold risk lead.** then 1–2 sentences with mitigation or open question.
- BlueprintClaim.text: markdown string in the bold-lead + 1–2 sentence shape above. The bold lead is 3–7 words ending with a period.
- BlueprintClaim.sources: list[Source]. Non-empty Source objects with file_id, file_name, type, locator.

Tone:
Actionable, executive-readable, scannable. Each claim is markdown: a **bold lead phrase** ending in a period, then 1–2 short sentences. No paragraphs, no essays.

Example:
{{"opportunity_ref":0,"summary":{{"text":"**Automate lead intake into CRM.** Leads wait >24h for first response because staff manually copy notes into the CRM. The blueprint parses the intake channel, writes the CRM record, assigns an owner, and logs the handoff for audit.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},"steps":[{{"text":"**Define intake trigger.** Confirm the authoritative inbox/form and pin the required fields: company, contact, email, coverage, received timestamp.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}},{{"text":"**Parse and validate.** Extract structured fields, normalize, and reject low-confidence records into a review queue with a duplicate check on email + company.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},{{"text":"**Write CRM record.** Create or update the lead via API, attach the source message, set stage, and assign the producer using existing routing rules.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"**Notify owner, expose exceptions.** Send a concise alert with CRM link; route ambiguous coverage, duplicate matches, or failed writes to a human-review task.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},{{"text":"**Instrument timing audit.** Persist received, CRM-created, assigned, and first-response timestamps so response-time reduction is measurable.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}}],"required_systems":[{{"text":"**Lead intake feed.** Shared inbox, form webhook, or CSV export with read access, polling/webhook trigger, and audit storage for the raw source.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}},{{"text":"**CRM write API.** Credentials with lead/contact/company write, owner assignment, and external-id linkage to block duplicates.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"**Exception queue + logs.** Review surface for failed validations and a log store for trigger time, parse result, CRM status, owner assignment.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}}],"success_metrics":[{{"text":"**Median first-response time.** Target ≥50% reduction from current baseline, measured weekly from CRM timestamps.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}},{{"text":"**Manual re-key volume.** Count of leads written automatically vs re-keyed by staff each week; target trending to near-zero.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"**Exception queue aging.** Stays below the agreed review threshold so ambiguous leads do not accumulate unseen.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}}],"risks":[{{"text":"**Incomplete lead messages.** Ambiguous intent or duplicate company names may misroute records; mitigate with validation + human review from day one.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},{{"text":"**CRM permissions unconfirmed.** Field mappings and duplicate rules must be verified pre-launch to avoid noisy or incorrect records.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"**SLA not in evidence.** The first-response threshold is not explicit in sources; the team must confirm it before using as a metric.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}}]}}

Format:
Reply ONLY with JSON matching the Blueprint schema.

Constraints:
- Avoid prose paragraphs; every claim follows the bold-lead + 1–2 sentence pattern.
- Avoid restating context across claims; the summary establishes context once.
- Avoid exceeding 40 words per step/system/metric/risk claim (≤80 for summary).
- Avoid uncited claims; every BlueprintClaim needs sources.
- Avoid bare source strings such as "f1"; sources must be full objects.
- Avoid hallucinating vendor names, APIs, fields, or SLAs not present in the selected opportunity or bundle.
- Keep steps implementable, sequenced, and specific enough that an engineer or operations lead can act on them."""


def render(*, run_context: RunContext | None = None, **format_kwargs) -> str:
    """Render solution_blueprint with an optional Operator priorities block (FRAMING role).

    When ``run_context`` is None or empty, output is byte-identical to
    ``PROMPT.format(**format_kwargs)`` — baseline behavior preserved.
    """
    base = PROMPT.format(**format_kwargs)
    return base + render_priorities_block(role=Role.FRAMING, run_context=run_context)
