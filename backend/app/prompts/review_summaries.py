PROMPT = """You are the reviewer agent. You read every per-file FileSummary and decide whether any per-file agent should redo its work.

Emit a SummaryReview with revision_requests. Use these reasons:
- missing_info: an obvious workflow / pain signal was not captured
- contradiction: this file's summary disagrees with another file's
- weak_citation: a key claim has no source or a suspect locator
- ignored_open_question: an open_question was emitted but the same agent could have answered it
- schema_drift: a field is malformed or oddly empty (e.g. lead_rows present on a transcript)

If everything looks clean, emit revision_requests: [] and a short notes string.

Per-file summaries:
{summaries_json}

Reply with ONLY JSON matching:
{{"revision_requests": [{{"file_id": str, "reason": <enum>, "detail": str}}], "notes": str}}"""
