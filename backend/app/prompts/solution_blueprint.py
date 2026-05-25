"""Prompt for the ``solution_blueprint`` lead node.

Writes the final automation Blueprint for the selected opportunity. The prompt
keeps the Source-object invariant explicit without carrying a bulky example.
"""

PROMPT = """Act as a senior automation solution architect.

Your task is to write the final cited Blueprint for the selected Opportunity as a detailed research-backed implementation outcome.

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
- summary: BlueprintClaim. 100-200 words describing the current pain, proposed automation, affected workflow, expected business outcome, and evidence basis.
- steps: list[BlueprintClaim]. 5-8 ordered implementation steps. Each step text should be 2-4 sentences with the concrete action, owner/system touchpoints, data handled, expected result, and dependency on prior steps.
- required_systems: list[BlueprintClaim]. Technical requirements, not just names. Include systems, APIs/integrations, data objects, auth/permissions, triggers, destinations, logging/monitoring, and human review surfaces when supported by inputs.
- success_metrics: list[BlueprintClaim]. Measurable outcomes tied to the opportunity. Include baseline/target language when inputs support it; otherwise state what must be measured.
- risks: list[BlueprintClaim]. Implementation risks, data-quality assumptions, compliance/security concerns, human adoption risks, and unresolved open questions that need handling.
- BlueprintClaim.text: string. Clear claim or action.
- BlueprintClaim.sources: list[Source]. Non-empty Source objects with file_id, file_name, type, locator.

Tone:
Actionable, executive-readable, technically specific, and source-grounded.

Example:
{{"opportunity_ref":0,"summary":{{"text":"The selected opportunity is to reduce inbound lead response delay by automating the handoff from shared email intake into the CRM assignment workflow. The evidence shows that leads wait more than 24 hours before first response and that staff manually copy notes into the CRM, which creates avoidable delay, inconsistent ownership, and low visibility into whether a producer has acted. The proposed blueprint watches the lead intake channel, extracts the minimum viable lead fields, creates or updates the CRM record, assigns the right owner, and logs the handoff so the team can audit response time. The goal is not to replace judgment; it is to remove repetitive intake work, make lead status visible, and preserve a manual review lane for ambiguous requests or incomplete data.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},"steps":[{{"text":"Define the lead intake trigger and minimum data contract. Confirm which inbox, form, or export represents the authoritative starting point, then define required fields such as company, contact, email, requested coverage, received timestamp, and source channel. This step produces the exact event payload the automation will accept and identifies which fields must route to manual review when missing.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}},{{"text":"Build the intake parser and validation layer. The automation should read each new lead message, extract structured fields, normalize names and contact details, and reject low-confidence or incomplete records into a review queue. Validation should prevent duplicate CRM records by checking email, company, and recent open opportunities before creating anything new.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},{{"text":"Create or update the CRM lead record and assign ownership. Use the CRM API or approved import mechanism to write normalized lead fields, attach the source message or note, set stage/status, and assign the producer or CSR based on routing rules. The automation should record the assignment timestamp so first-response time can be measured later.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"Notify the assigned owner and expose exceptions. Send a concise notification with the lead summary, CRM link, missing fields, and next action. Any ambiguous coverage request, duplicate match, missing contact field, or failed CRM write should create a human-review task rather than silently dropping the lead.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},{{"text":"Instrument response-time monitoring and audit logs. Store received time, CRM-created time, owner-assigned time, first-response time, exception reason, and automation status. This creates the reporting layer needed to prove whether the automation reduced delay and whether manual exceptions are shrinking over time.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}}],"required_systems":[{{"text":"Lead intake source with event access: a shared inbox, form webhook, CSV export, or equivalent feed that can expose new lead requests with timestamp, sender, body, and attachments. The automation needs read permission, a polling or webhook trigger, and a way to store the raw source reference for audit.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}},{{"text":"CRM write path: API credentials or approved import service capable of searching existing leads, creating or updating records, assigning owner, setting status/stage, and attaching notes. Required objects include lead/contact/company fields, assignment fields, timestamps, and an external source identifier to prevent duplicates.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"Exception and monitoring layer: a review queue, task list, or ticketing surface for failed validations plus logs for trigger time, parse result, CRM write status, owner assignment, and first response. This is required so ambiguous leads are visible instead of silently skipped.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}}],"success_metrics":[{{"text":"Median first-response time decreases from the current delayed state to the target defined by the team, with a minimum target of at least 50% reduction if no SLA is already documented.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}},{{"text":"Manual CRM note-copying volume decreases, measured by the count of lead records created automatically versus manually re-keyed by staff each week.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"Exception queue aging stays below the agreed review threshold, proving that ambiguous or incomplete leads are handled instead of accumulating unseen.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}}],"risks":[{{"text":"Lead messages with incomplete contact information, ambiguous intent, or duplicate company names may be misrouted unless validation and human review are part of the first release.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":2}}}}]}},{{"text":"CRM API permissions, field mappings, and duplicate-detection rules must be confirmed before implementation; otherwise the automation could create noisy or incorrect records.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":2,"line_end":2}}}}]}},{{"text":"The target first-response SLA is not explicit in the cited evidence, so the team must confirm the threshold before using it as a success metric.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}}]}}

Format:
Reply ONLY with JSON matching the Blueprint schema.

Constraints:
- Avoid designing for any unselected opportunity.
- Avoid shallow one-line claims; every field should contain enough implementation detail to be useful.
- Avoid uncited claims; every BlueprintClaim needs sources and every major assertion in a long claim should be supported by those sources.
- Avoid bare source strings such as "f1"; sources must be full objects.
- Avoid hallucinating vendor names, APIs, fields, or SLAs not present in the selected opportunity or bundle.
- Keep steps implementable, sequenced, and specific enough that an engineer or operations lead can act on them."""
